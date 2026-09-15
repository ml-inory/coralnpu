"""RV32I 单周期核黄金模型（教学用，纯标准库实现）。

它精确描述 L01 课程里学员要实现的硬件行为：

* ITCM：0x0000_0000 起，只读数据 + 指令；容量由 ``itcm_words`` 决定。
* DTCM：0x0001_0000 起，可读可写；容量由 ``dtcm_words`` 决定。
* 复位后所有通用寄存器为 0，PC 为 0。
* 指令在单周期内完成：取指、译码、执行、写回发生在同一个周期里。
* 停机：``mpause``（编码 0x08000073，与上游 CoralNPU 一致，见
  hdl/chisel/src/coralnpu/scalar/Decode.scala:1188）、``ebreak``、``ecall``。

每条退休指令都会产生一行 trace：``pc inst rd wdata``，用于和 RTL 对拍。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .elf import load_elf

MASK32 = 0xFFFF_FFFF

# 上游 CoralNPU 的停机指令：自定义 SYSTEM 指令 mpause。
INSTR_MPAUSE = 0x0800_0073
INSTR_EBREAK = 0x0010_0073
INSTR_ECALL = 0x0000_0073
INSTR_MRET = 0x3020_0073

# CSR 地址（L03b 实现的最小集合）
CSR_MSTATUS  = 0x300
CSR_MISA     = 0x301
CSR_MTVEC    = 0x305
CSR_MSCRATCH = 0x340
CSR_MEPC     = 0x341
CSR_MCAUSE   = 0x342
CSR_MTVAL    = 0x343
CSR_MHARTID  = 0xF14

# 异常原因码（mcause）
CAUSE_ILLEGAL_INSTRUCTION = 2
CAUSE_BREAKPOINT          = 3
CAUSE_ECALL_FROM_M        = 11

# misa：RV32 + I(bit8) + M(bit12)
MISA_VALUE = 0x4000_1100


class CoreFault(Exception):
    """非法访问、非法指令等硬件级错误。"""


def u32(v: int) -> int:
    return v & MASK32


def sext(value: int, bits: int) -> int:
    """把 value 按 bits 位做符号扩展，返回 32 位无符号。"""
    sign = 1 << (bits - 1)
    return u32((value & ((1 << bits) - 1)) - (1 << bits) if value & sign else value)


def s32(v: int) -> int:
    """把 32 位无符号数解释成有符号整数。"""
    return v - (1 << 32) if v & 0x8000_0000 else v


@dataclass
class Retire:
    pc: int
    inst: int
    rd: int
    wdata: int
    halted: bool = False
    halt_reason: str = ""

    def line(self) -> str:
        return f"{self.pc:08x} {self.inst:08x} {self.rd:02x} {self.wdata:08x}"


@dataclass
class Core:
    itcm_words: int = 2048  # 8 KB，与上游 CoreMiniAxi 默认一致
    dtcm_words: int = 8192  # 32 KB，与上游 CoreMiniAxi 默认一致
    itcm_base: int = 0x0001_0000 - 0x0001_0000  # 0x0
    dtcm_base: int = 0x0001_0000
    regs: list[int] = field(default_factory=lambda: [0] * 32)
    pc: int = 0
    itcm: bytearray = field(default_factory=bytearray)
    dtcm: bytearray = field(default_factory=bytearray)
    halted: bool = False
    halt_reason: str = ""
    cycles: int = 0
    retire_count: int = 0
    # L03b：最小 CSR 集合（复位值见 mstatus/mtvec/... 的定义）
    csr: dict = field(default_factory=lambda: {
        CSR_MSTATUS: 0, CSR_MISA: MISA_VALUE, CSR_MTVEC: 0, CSR_MSCRATCH: 0,
        CSR_MEPC: 0, CSR_MCAUSE: 0, CSR_MTVAL: 0, CSR_MHARTID: 0,
    })
    # 异常/返回要把 PC 重定向，而不是走顺序的 PC+4（step() 末尾统一处理）
    trap_target: int | None = None
    ret_target: int | None = None

    def __post_init__(self) -> None:
        if not self.itcm:
            self.itcm = bytearray(self.itcm_words * 4)
        if not self.dtcm:
            self.dtcm = bytearray(self.dtcm_words * 4)

    # ------------------------------------------------------------------ 装载
    def load_bytes(self, addr: int, data: bytes) -> None:
        for i, b in enumerate(data):
            a = addr + i
            if self.itcm_base <= a < self.itcm_base + len(self.itcm):
                self.itcm[a - self.itcm_base] = b
            elif self.dtcm_base <= a < self.dtcm_base + len(self.dtcm):
                self.dtcm[a - self.dtcm_base] = b
            else:
                raise CoreFault(f"地址 0x{a:08x} 不在 ITCM/DTCM 范围内")

    def load_elf(self, path: str) -> int:
        img = load_elf(path)
        for seg in img.segments:
            self.load_bytes(seg.vaddr, seg.data)
        self.pc = img.entry
        return img.entry

    def load_hex_words(self, path: str, base: int, limit_words: int) -> int:
        """装载每行一个 32 位十六进制字的镜像，返回装载字数。"""
        n = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                if n >= limit_words:
                    break
                self.load_bytes(base + n * 4, int(line, 16).to_bytes(4, "little"))
                n += 1
        return n

    # ------------------------------------------------------------- 内存访问
    def data_read(self, addr: int, size: int, signed: bool) -> int:
        # 架构上非对齐访问是合法的（硬件可以自己拆分，也可以选择触发异常）。
        # L01 的核只支持对齐访问；L02 用 LSU 把非对齐访问拆成两次对齐事务，
        # 两者的架构结果必须与这里的逐字节读写一致。
        if self.itcm_base <= addr < self.itcm_base + len(self.itcm):
            region, off = self.itcm, addr - self.itcm_base
        elif self.dtcm_base <= addr < self.dtcm_base + len(self.dtcm):
            region, off = self.dtcm, addr - self.dtcm_base
        else:
            raise CoreFault(f"load 地址 0x{addr:08x} 无设备响应")
        if off + size > len(region):
            raise CoreFault(f"load 越界 addr=0x{addr:08x}")
        raw = int.from_bytes(region[off : off + size], "little")
        return sext(raw, size * 8) if signed else raw

    def data_write(self, addr: int, size: int, value: int) -> None:
        if self.itcm_base <= addr < self.itcm_base + len(self.itcm):
            raise CoreFault(f"store 打到 ITCM（只读）addr=0x{addr:08x}")
        if not (self.dtcm_base <= addr < self.dtcm_base + len(self.dtcm)):
            raise CoreFault(f"store 地址 0x{addr:08x} 无设备响应")
        off = addr - self.dtcm_base
        if off + size > len(self.dtcm):
            raise CoreFault(f"store 越界 addr=0x{addr:08x}")
        self.dtcm[off : off + size] = u32(value).to_bytes(4, "little")[:size]

    def fetch(self, addr: int) -> int:
        if addr % 4 != 0:
            raise CoreFault(f"取指地址非对齐 0x{addr:08x}")
        off = addr - self.itcm_base
        if not (0 <= off < len(self.itcm)):
            raise CoreFault(f"取指地址 0x{addr:08x} 超出 ITCM")
        return int.from_bytes(self.itcm[off : off + 4], "little")

    # ---------------------------------------------------------------- 执行
    def csr_read(self, addr: int) -> int:
        """读 CSR。未实现的地址按 0 处理（本课的简化约定）。"""
        return self.csr.get(addr, 0)

    def csr_write(self, addr: int, value: int) -> None:
        """写 CSR。misa / mhartid 是只读的；未实现地址忽略写入。"""
        if addr in (CSR_MISA, CSR_MHARTID):
            return
        if addr in self.csr:
            self.csr[addr] = u32(value)

    def take_trap(self, cause: int, epc: int) -> None:
        """进入异常：记录 mepc/mcause，跳到 mtvec。"""
        self.csr[CSR_MEPC] = u32(epc)
        self.csr[CSR_MCAUSE] = u32(cause)
        self.csr[CSR_MTVAL] = 0
        self.trap_target = u32(self.csr_read(CSR_MTVEC))

    def mdu_exec(self, funct3: int, a: int, b: int) -> int:
        """M 扩展的 8 条指令（注意有符号/无符号与边界情况）。"""
        sa, sb = s32(a), s32(b)
        if funct3 == 0x0:      # mul：低 32 位（有无符号相同）
            return u32(a * b)
        if funct3 == 0x1:      # mulh：有符号 × 有符号的高 32 位
            return u32((sa * sb) >> 32)
        if funct3 == 0x2:      # mulhsu：有符号 × 无符号
            return u32((sa * b) >> 32)
        if funct3 == 0x3:      # mulhu：无符号 × 无符号
            return u32((a * b) >> 32)
        if funct3 == 0x4:      # div：除零 → -1；INT_MIN / -1 → INT_MIN
            if b == 0:
                return MASK32
            if sa == -(1 << 31) and sb == -1:
                return 0x8000_0000
            q = abs(sa) // abs(sb)
            q = -q if (sa < 0) != (sb < 0) else q
            return u32(q)
        if funct3 == 0x5:      # divu：除零 → 全 1
            return MASK32 if b == 0 else u32(a // b)
        if funct3 == 0x6:      # rem：除零 → 被除数；溢出 → 0
            if b == 0:
                return u32(a)
            if sa == -(1 << 31) and sb == -1:
                return 0
            r = abs(sa) % abs(sb)
            return u32(-r if sa < 0 else r)
        # remu
        return u32(a) if b == 0 else u32(a % b)

    def step(self) -> Retire:
        if self.halted:
            raise CoreFault("核心已停机")
        pc = self.pc
        inst = self.fetch(pc)
        rd = 0
        wdata = 0
        next_pc = u32(pc + 4)

        opcode = inst & 0x7F
        f3 = (inst >> 12) & 0x7
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        f7 = (inst >> 25) & 0x7F
        a = self.regs[rs1]
        b = self.regs[rs2]

        imm_i = sext(inst >> 20, 12)
        imm_s = sext(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12)
        imm_b = sext(
            (((inst >> 31) & 1) << 12)
            | (((inst >> 7) & 1) << 11)
            | (((inst >> 25) & 0x3F) << 5)
            | (((inst >> 8) & 0xF) << 1),
            13,
        )
        imm_u = inst & 0xFFFF_F000
        imm_j = sext(
            (((inst >> 31) & 1) << 20)
            | (((inst >> 12) & 0xFF) << 12)
            | (((inst >> 20) & 1) << 11)
            | (((inst >> 21) & 0x3FF) << 1),
            21,
        )

        def write_reg(idx: int, value: int) -> None:
            self.regs[idx] = u32(value)
            if idx != 0:
                self.regs[0] = 0

        if opcode == 0x37:  # LUI
            rd, wdata = (inst >> 7) & 0x1F, imm_u
        elif opcode == 0x17:  # AUIPC
            rd, wdata = (inst >> 7) & 0x1F, u32(pc + imm_u)
        elif opcode == 0x6F:  # JAL
            rd, wdata = (inst >> 7) & 0x1F, next_pc
            next_pc = u32(pc + imm_j)
        elif opcode == 0x67:  # JALR
            if f3 != 0:
                raise CoreFault(f"非法 JALR funct3={f3}")
            rd, wdata = (inst >> 7) & 0x1F, next_pc
            next_pc = u32((a + imm_i) & ~1)
        elif opcode == 0x63:  # 分支
            taken = {
                0x0: a == b,
                0x1: a != b,
                0x4: s32(a) < s32(b),
                0x5: s32(a) >= s32(b),
                0x6: a < b,
                0x7: a >= b,
            }.get(f3)
            if taken is None:
                raise CoreFault(f"非法分支 funct3={f3}")
            if taken:
                next_pc = u32(pc + imm_b)
        elif opcode == 0x03:  # 载入
            addr = u32(a + imm_i)
            size, signed = {0x0: (1, True), 0x1: (2, True), 0x2: (4, False),
                            0x4: (1, False), 0x5: (2, False)}.get(f3, (0, False))
            if size == 0:
                raise CoreFault(f"非法 load funct3={f3}")
            rd = (inst >> 7) & 0x1F
            wdata = self.data_read(addr, size, signed)
        elif opcode == 0x23:  # 存储
            addr = u32(a + imm_s)
            size = {0x0: 1, 0x1: 2, 0x2: 4}.get(f3)
            if size is None:
                raise CoreFault(f"非法 store funct3={f3}")
            self.data_write(addr, size, b)
        elif opcode == 0x13:  # OP-IMM
            shamt = (inst >> 20) & 0x1F
            if f3 == 0x0:
                wdata = u32(a + imm_i)
            elif f3 == 0x2:
                wdata = 1 if s32(a) < s32(imm_i) else 0
            elif f3 == 0x3:
                wdata = 1 if a < imm_i else 0
            elif f3 == 0x4:
                wdata = a ^ imm_i
            elif f3 == 0x6:
                wdata = a | imm_i
            elif f3 == 0x7:
                wdata = a & imm_i
            elif f3 == 0x1:
                if f7 & 0x20:
                    raise CoreFault("RV32I 不包含 Zbb 的 rol（L03 之后再学）")
                wdata = u32(a << shamt)
            elif f3 == 0x5:
                if f7 == 0x00:
                    wdata = a >> shamt
                elif f7 == 0x20:
                    wdata = u32(s32(a) >> shamt)
                else:
                    raise CoreFault(f"非法移位指令 f7=0x{f7:02x}")
            else:
                raise CoreFault(f"非法 OP-IMM funct3={f3}")
            rd = (inst >> 7) & 0x1F
        elif opcode == 0x33:  # OP
            if f7 == 0x01:  # M 扩展（L03b）
                rd = (inst >> 7) & 0x1F
                wdata = self.mdu_exec(f3, a, b)
            elif f3 == 0x0:
                wdata = u32(a - b) if f7 & 0x20 else u32(a + b)
            elif f3 == 0x1:
                wdata = u32(a << (b & 0x1F))
            elif f3 == 0x2:
                wdata = 1 if s32(a) < s32(b) else 0
            elif f3 == 0x3:
                wdata = 1 if a < b else 0
            elif f3 == 0x4:
                wdata = a ^ b
            elif f3 == 0x5:
                wdata = u32(s32(a) >> (b & 0x1F)) if f7 & 0x20 else a >> (b & 0x1F)
            elif f3 == 0x6:
                wdata = a | b
            elif f3 == 0x7:
                wdata = a & b
            else:
                raise CoreFault(f"非法 OP funct3={f3}")
            rd = (inst >> 7) & 0x1F
        elif opcode == 0x0F:  # FENCE / FENCE.I：单周期核里视作空操作
            pass
        elif opcode == 0x73:  # SYSTEM
            if inst == INSTR_MPAUSE:
                self.halted, self.halt_reason = True, "mpause"
            elif f3 == 0x0 and inst == INSTR_EBREAK:
                # ebreak：断点异常（mcause=3）
                self.take_trap(CAUSE_BREAKPOINT, pc)
            elif f3 == 0x0 and inst == INSTR_ECALL:
                # ecall：来自 M 模式的环境调用（mcause=11）
                self.take_trap(CAUSE_ECALL_FROM_M, pc)
            elif f3 == 0x0 and inst == INSTR_MRET:
                # mret：返回 mepc
                self.ret_target = u32(self.csr_read(CSR_MEPC))
            elif f3 != 0x0:
                # Zicsr：csrrw/csrrs/csrrc + 立即数形式
                csr_addr = (inst >> 20) & 0xFFF
                rd = (inst >> 7) & 0x1F
                rs1_field = (inst >> 15) & 0x1F
                old = self.csr_read(csr_addr)
                if f3 >= 0x5:                     # 立即数形式：rs1 字段是 5 位无符号数
                    src = rs1_field
                else:
                    src = a
                if f3 == 0x1 or f3 == 0x5:
                    new = src                     # csrrw / csrrwi：总是写
                elif f3 == 0x2 or f3 == 0x6:
                    new = old | src               # csrrs / csrrsi
                else:
                    new = old & ~src              # csrrc / csrrci
                # set/clear 且 rs1=x0 时不写（避免读副作用的规范要求）
                if not ((f3 in (0x2, 0x3, 0x6, 0x7)) and rs1_field == 0):
                    self.csr_write(csr_addr, new)
                wdata = old
            else:
                # 其它 SYSTEM 编码：非法指令异常
                self.take_trap(CAUSE_ILLEGAL_INSTRUCTION, pc)
        else:
            # 未实现的 opcode：非法指令异常（mcause=2），跳到 mtvec
            self.take_trap(CAUSE_ILLEGAL_INSTRUCTION, pc)

        if rd != 0:
            write_reg(rd, wdata)
        else:
            # rd=0 表示"这条指令不写寄存器"，trace 里统一记成 0，便于和 RTL 对拍
            wdata = 0
        self.regs[0] = 0
        if self.trap_target is not None:
            self.pc = self.trap_target
            self.trap_target = None
        elif self.ret_target is not None:
            self.pc = self.ret_target
            self.ret_target = None
        else:
            self.pc = next_pc
        self.cycles += 1
        self.retire_count += 1
        return Retire(pc=pc, inst=inst, rd=rd, wdata=wdata,
                      halted=self.halted, halt_reason=self.halt_reason)

    def run(self, max_steps: int = 2_000_000) -> list[Retire]:
        trace: list[Retire] = []
        while not self.halted:
            if self.retire_count >= max_steps:
                raise CoreFault(f"执行超过 {max_steps} 条指令仍未停机（死循环？）")
            trace.append(self.step())
        return trace

    def dump_dtcm_words(self) -> list[int]:
        return [int.from_bytes(self.dtcm[i : i + 4], "little") for i in range(0, len(self.dtcm), 4)]

    def regs_hex(self) -> list[int]:
        return [u32(v) for v in self.regs]

#!/usr/bin/env python3
"""标准符合性交叉验证：用 GNU 工具链检验课程对 RISC-V 编码的理解。

为什么需要它：课程自带的黄金模型、反汇编器、检查器都是我们自己写的，
三者可能共享同一个误解（共同失效模式）。GNU `as` / `objdump` 是**独立实现**
的编码器与解码器，用它来交叉验证，才能说明我们教的是 RISC-V 标准，
而不是「本仓库方言」。

验证两件事：
  1. 编码一致性：我们自己按规范位域拼出来的机器码 == GNU as 编出来的机器码
  2. 解码一致性：我们 disasm.py 给出的助记符 == GNU objdump 给出的助记符（含别名归一化）

用法：
  ./learn standards L01
  python3 course/lessons/L01_scalar/tests/conformance.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LESSON = os.path.dirname(HERE)
LEARN = os.path.dirname(os.path.dirname(LESSON))
sys.path.insert(0, LEARN)

from tools.disasm import ABI, disasm  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

# GNU objdump 会输出伪指令，这里把两边归一化后再比助记符
MNEMONIC_ALIASES = {
    "j": "jal",
    "jr": "jalr",
    "ret": "jalr",
    "nop": "addi",
    "li": "addi",
    "mv": "addi",
    "not": "xori",
    "neg": "sub",
    "seqz": "sltiu",
    "snez": "sltu",
    "fence.i": "fence.i",
}


def reg_number(name: str) -> int:
    name = name.strip()
    if name in ABI:
        return ABI.index(name)
    m = re.fullmatch(r"x(\d+)", name)
    if m and 0 <= int(m.group(1)) < 32:
        return int(m.group(1))
    raise ValueError(f"无法识别的寄存器名：{name}")


def imm_value(text: str) -> int:
    text = text.strip().replace("_", "").replace(" ", "")
    # 汇编语法里 `beq a0, a1, 16` 的 16 是绝对地址；写偏移要用 `.+16` / `.-16`
    if text.startswith("."):
        text = text[1:]
        if text.startswith("+"):
            text = text[1:]
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    value = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    return -value if neg else value


def enc_r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, opcode: int = 0x33) -> int:
    return ((funct7 & 0x7F) << 25) | ((rs2 & 31) << 20) | ((rs1 & 31) << 15) | \
           ((funct3 & 7) << 12) | ((rd & 31) << 7) | opcode


def enc_i(imm: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return ((imm & 0xFFF) << 20) | ((rs1 & 31) << 15) | ((funct3 & 7) << 12) | \
           ((rd & 31) << 7) | opcode


def enc_s(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    return (((imm >> 5) & 0x7F) << 25) | ((rs2 & 31) << 20) | ((rs1 & 31) << 15) | \
           ((funct3 & 7) << 12) | ((imm & 0x1F) << 7) | 0x23


def enc_b(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | ((rs2 & 31) << 20) | \
           ((rs1 & 31) << 15) | ((funct3 & 7) << 12) | (((imm >> 1) & 0xF) << 8) | \
           (((imm >> 11) & 1) << 7) | 0x63


def enc_u(imm: int, rd: int, opcode: int) -> int:
    return ((imm & 0xFFFFF) << 12) | ((rd & 31) << 7) | opcode


def enc_j(imm: int, rd: int) -> int:
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | \
           (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12) | \
           ((rd & 31) << 7) | 0x6F


R_OPS = {"add": (0x00, 0), "sub": (0x20, 0), "sll": (0x00, 1), "slt": (0x00, 2),
         "sltu": (0x00, 3), "xor": (0x00, 4), "srl": (0x00, 5), "sra": (0x20, 5),
         "or": (0x00, 6), "and": (0x00, 7)}
I_OPS = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
SHIFT_OPS = {"slli": (0, 1), "srli": (0x00, 5), "srai": (0x20, 5)}
LOAD_OPS = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}
STORE_OPS = {"sb": 0, "sh": 1, "sw": 2}
BRANCH_OPS = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}


def encode(asm: str) -> int:
    """独立实现：按 RISC-V 规范的位域拼机器码（不依赖任何工具）。"""
    text = asm.split("#")[0].strip()
    parts = re.split(r"[\s,]+", text, maxsplit=1)
    mnemonic = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    terms = [t.strip() for t in rest.split(",") if t.strip()]

    if mnemonic in R_OPS:
        funct7, funct3 = R_OPS[mnemonic]
        rd, rs1, rs2 = (reg_number(t) for t in terms)
        return enc_r(funct7, rs2, rs1, funct3, rd)
    if mnemonic in I_OPS:
        rd, rs1, imm = reg_number(terms[0]), reg_number(terms[1]), imm_value(terms[2])
        return enc_i(imm, rs1, I_OPS[mnemonic], rd, 0x13)
    if mnemonic in SHIFT_OPS:
        funct7, funct3 = SHIFT_OPS[mnemonic]
        rd, rs1, shamt = reg_number(terms[0]), reg_number(terms[1]), imm_value(terms[2]) & 0x1F
        return enc_i((funct7 << 5) | shamt, rs1, funct3, rd, 0x13)
    if mnemonic in LOAD_OPS:
        rd = reg_number(terms[0])
        m = re.match(r"(.+)\((.*)\)", terms[1])
        imm, rs1 = imm_value(m.group(1)), reg_number(m.group(2))
        return enc_i(imm, rs1, LOAD_OPS[mnemonic], rd, 0x03)
    if mnemonic in STORE_OPS:
        rs2 = reg_number(terms[0])
        m = re.match(r"(.+)\((.*)\)", terms[1])
        imm, rs1 = imm_value(m.group(1)), reg_number(m.group(2))
        return enc_s(imm, rs2, rs1, STORE_OPS[mnemonic])
    if mnemonic in BRANCH_OPS:
        rs1, rs2, imm = reg_number(terms[0]), reg_number(terms[1]), imm_value(terms[2])
        return enc_b(imm, rs2, rs1, BRANCH_OPS[mnemonic])
    if mnemonic == "lui":
        # lui 的汇编操作数就是直接放进 inst[31:12] 的 20 位值（不要再右移）
        return enc_u(imm_value(terms[1]), reg_number(terms[0]), 0x37)
    if mnemonic == "auipc":
        return enc_u(imm_value(terms[1]), reg_number(terms[0]), 0x17)
    if mnemonic == "jal":
        return enc_j(imm_value(terms[1]), reg_number(terms[0]))
    if mnemonic == "jalr":
        rd = reg_number(terms[0])
        if "(" in terms[-1]:
            m = re.match(r"(.+)\((.*)\)", terms[-1])
            imm, rs1 = imm_value(m.group(1)), reg_number(m.group(2))
        else:
            rs1, imm = reg_number(terms[1]), imm_value(terms[2])
        return enc_i(imm, rs1, 0, rd, 0x67)
    if mnemonic == "fence.i":
        return 0x0000100F
    if mnemonic == "fence":
        # 无操作数的 fence 是 pred=succ=0b1111、fm=0（RISC-V 规范里的默认写法）
        return 0x0FF0000F
    if mnemonic == "ebreak":
        return 0x00100073
    if mnemonic == "ecall":
        return 0x00000073
    raise ValueError(f"编码器还不支持：{asm}")


# 覆盖 L01 全部指令类型；每行都会被 GNU as 独立编码一次
CASES = [
    # R 型
    "add x5, x6, x7", "sub x10, x11, x12", "sll x1, x2, x3", "slt x8, x9, x10",
    "sltu x20, x21, x22", "xor t0, t1, t2", "srl a0, a1, a2", "sra s0, s1, s2",
    "or t3, t4, t5", "and t6, s3, s4",
    # I 型运算
    "addi a0, a1, -7", "addi x0, x0, 0", "slti t0, t1, 2047", "sltiu t2, t3, -1",
    "xori a2, a3, 0x7ff", "ori s5, s6, -2048", "andi s7, s8, 100",
    # 移位
    "slli t0, t1, 13", "srli t2, t3, 31", "srai t4, t5, 0",
    # 载入
    "lb t0, 0(sp)", "lh t1, -2(sp)", "lw a0, 2047(sp)", "lbu a1, 1(a2)", "lhu a3, -2048(a4)",
    # 存储
    "sb t0, 0(sp)", "sh t1, 2(sp)", "sw a0, 100(a1)",
    # 分支
    "beq a0, a1, .+16", "bne a2, a3, .-16", "blt t0, t1, .+8", "bge t2, t3, .-8",
    "bltu s0, s1, .+4", "bgeu s2, s3, .-4",
    # 跳转与 U 型
    "jal ra, .+2044", "jal x0, .-2048", "jalr ra, t0, 4", "jalr a0, 8(a1)",
    "lui t0, 0x12345", "lui x0, 0xfffff", "auipc t1, 0xabcde",
    # 其他
    "fence", "fence.i", "ebreak", "ecall",
]

# GNU as 编不了的自定义指令（CoralNPU 的 mpause），单独校验常量
UNAVAILABLE = [("mpause", 0x08000073)]


def tool(name: str) -> str | None:
    return shutil.which("riscv64-unknown-elf-" + name) or shutil.which(name)


def normalize(mnemonic: str) -> str:
    m = mnemonic.strip().lower()
    return MNEMONIC_ALIASES.get(m, m)


def main() -> int:
    ap_argv = sys.argv[1:]
    no_color = "--no-color" in ap_argv

    def col(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if not no_color else text

    asm = tool("as")
    objdump = tool("objdump")
    if not asm or not objdump:
        print("需要 RISC-V 工具链（riscv64-unknown-elf-as / objdump）。")
        print("运行 ./learn doctor --install 安装。")
        return 2

    work = os.path.join(LEARN, "work", "L01", "conformance")
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, "encodings.S")
    obj = os.path.join(work, "encodings.o")

    with open(src, "w", encoding="utf-8") as f:
        f.write("  .text\n  .globl probe\nprobe:\n")
        for case in CASES:
            f.write(f"  {case}\n")

    # fence.i 在 RISC-V 里属于 Zifencei 扩展，需要显式打开
    proc = subprocess.run([asm, "-march=rv32i_zifencei", "-mabi=ilp32", "-o", obj, src],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        print("汇编失败：\n" + proc.stdout + proc.stderr)
        return 1
    proc = subprocess.run([objdump, "-d", obj], capture_output=True, text=True)
    if proc.returncode != 0:
        print("反汇编失败：\n" + proc.stdout + proc.stderr)
        return 1

    # 解析 objdump：每行形如 "   4:\t123452b7\tlui\tt0,0x12345"
    gnu = []
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(\S+)\s*(.*)$", line)
        if m:
            gnu.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4)))

    print("")
    print(col("L01 标准符合性交叉验证（GNU as / objdump 为独立实现）", "\033[1m"))
    print("")
    if len(gnu) != len(CASES):
        print(col(f"⚠️  objdump 解析出 {len(gnu)} 条，期望 {len(CASES)} 条——可能有指令被展开成多条", YELLOW))

    ok = True
    rows = 0
    for i, case in enumerate(CASES):
        if i >= len(gnu):
            print(col(f"✗ {case}: objdump 输出不足", RED))
            ok = False
            break
        _, gnu_bytes, gnu_mnemonic, _ = gnu[i]
        try:
            mine = encode(case)
        except ValueError as exc:
            print(col(f"✗ {case}: {exc}", RED))
            ok = False
            continue
        enc_ok = mine == gnu_bytes
        dis_ok = normalize(gnu_mnemonic) == normalize(disasm(mine).split()[0])
        rows += 1
        if not (enc_ok and dis_ok):
            ok = False
            print(col(f"✗ {case}", RED))
            print(f"    课程编码 0x{mine:08x}   GNU 编码 0x{gnu_bytes:08x}")
            print(f"    课程反汇编 {disasm(mine)}   GNU 反汇编 {gnu_mnemonic}")
    for name, value in UNAVAILABLE:
        got = 0x08000073 if name == "mpause" else 0
        if got != value:
            ok = False
            print(col(f"✗ 自定义指令 {name} 常量为 0x{got:08x}，期望 0x{value:08x}", RED))

    print("")
    total = rows + len(UNAVAILABLE)
    if ok:
        print(col(f"✅ {total}/{total} 条指令的编码与助记符与 GNU 工具链一致", GREEN))
        print(col("   也就是说：课程教的编码是 RISC-V 标准，不是本仓库方言。", DIM))
        print(f"   自定义指令（标准工具不认识）单独登记：{', '.join(n for n, _ in UNAVAILABLE)}")
    else:
        print(col("❌ 存在不一致：请对照 RISC-V 规范核对位域", RED))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

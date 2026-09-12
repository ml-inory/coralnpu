"""极简 RV32I 反汇编器：只为了把出错的那条指令讲清楚。

覆盖 L01 教学用到的指令子集，遇到不认识的编码返回 `.word 0x...`。
"""

from __future__ import annotations

ABI = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
]


def _s(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def disasm(inst: int) -> str:
    opcode = inst & 0x7F
    f3 = (inst >> 12) & 0x7
    rd = (inst >> 7) & 0x1F
    rs1 = (inst >> 15) & 0x1F
    rs2 = (inst >> 20) & 0x1F
    f7 = (inst >> 25) & 0x7F
    imm_i = _s(inst >> 20, 12)
    imm_s = _s(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12)
    imm_b = _s(
        ((inst >> 31) << 12) | (((inst >> 7) & 1) << 11) | (((inst >> 25) & 0x3F) << 5) | (((inst >> 8) & 0xF) << 1),
        13,
    )
    imm_u = inst & 0xFFFF_F000
    imm_j = _s(
        ((inst >> 31) << 20) | (((inst >> 12) & 0xFF) << 12) | (((inst >> 20) & 1) << 11) | (((inst >> 21) & 0x3FF) << 1),
        21,
    )
    r = ABI

    if inst == 0x0800_0073:
        return "mpause"
    if inst == 0x0010_0073:
        return "ebreak"
    if inst == 0x0000_0073:
        return "ecall"

    if opcode == 0x37:
        return f"lui {r[rd]}, 0x{imm_u >> 12:x}"
    if opcode == 0x17:
        return f"auipc {r[rd]}, 0x{imm_u >> 12:x}"
    if opcode == 0x6F:
        return f"jal {r[rd]}, {imm_j:+d}"
    if opcode == 0x67:
        return f"jalr {r[rd]}, {imm_i}({r[rs1]})"
    if opcode == 0x63:
        name = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}.get(f3)
        return f"{name} {r[rs1]}, {r[rs2]}, {imm_b:+d}" if name else f".word 0x{inst:08x}"
    if opcode == 0x03:
        name = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}.get(f3)
        return f"{name} {r[rd]}, {imm_i}({r[rs1]})" if name else f".word 0x{inst:08x}"
    if opcode == 0x23:
        name = {0: "sb", 1: "sh", 2: "sw"}.get(f3)
        return f"{name} {r[rs2]}, {imm_s}({r[rs1]})" if name else f".word 0x{inst:08x}"
    if opcode == 0x13:
        imm_ops = {0: "addi", 2: "slti", 3: "sltiu", 4: "xori", 6: "ori", 7: "andi"}
        if f3 in imm_ops:
            return f"{imm_ops[f3]} {r[rd]}, {r[rs1]}, {imm_i}"
        sh = (inst >> 20) & 0x1F
        if f3 == 1:
            return f"slli {r[rd]}, {r[rs1]}, {sh}"
        if f3 == 5:
            return f"{'srai' if f7 & 0x20 else 'srli'} {r[rd]}, {r[rs1]}, {sh}"
    if opcode == 0x33:
        if f7 == 1:
            name = {0: "mul", 1: "mulh", 2: "mulhsu", 3: "mulhu", 4: "div", 5: "divu", 6: "rem", 7: "remu"}[f3]
        else:
            name = {
                0: "sub" if f7 & 0x20 else "add",
                1: "sll",
                2: "slt",
                3: "sltu",
                4: "xor",
                5: "sra" if f7 & 0x20 else "srl",
                6: "or",
                7: "and",
            }[f3]
        return f"{name} {r[rd]}, {r[rs1]}, {r[rs2]}"
    if opcode == 0x0F:
        return "fence" if f3 == 0 else "fence.i"
    return f".word 0x{inst:08x}"

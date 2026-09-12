#!/usr/bin/env python3
"""L01 检查器：把学员的 RTL 和黄金模型逐指令对拍。

判定标准（两条都要满足）：
  1. trace 完全一致：每条退休指令的 pc / 机器码 / 目标寄存器 / 写回值
  2. DTCM 全量一致：8192 个字，包括栈上的临时数据

用法：
  python3 checks.py                # 检查 rtl/cpu_core.sv
  python3 checks.py --ref          # 检查 refs/cpu_core.sv（课程自检）
  python3 checks.py --only 01      # 只跑某个用例
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LESSON = os.path.dirname(HERE)
LEARN = os.path.dirname(os.path.dirname(LESSON))
ROOT = os.path.dirname(LEARN)
sys.path.insert(0, LEARN)

from golden.rv32i import Core, CoreFault  # noqa: E402
from tools import build_program, run_rtl  # noqa: E402
from tools.disasm import disasm  # noqa: E402

WORK = os.path.join(LEARN, "work", "L01")

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def color(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled else text


def record_progress(passed: int, total: int) -> None:
    """把本次自检结果写进 learn/.state/progress.json，供 ./learn list 显示。"""
    state_dir = os.path.join(LEARN, ".state")
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "progress.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data["L01"] = {
        "passed": passed,
        "total": total,
        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def list_programs() -> list[str]:
    d = os.path.join(HERE, "programs")
    files = [f for f in sorted(os.listdir(d)) if f.endswith((".S", ".c"))]
    return files


def explain_mismatch(inst: int) -> str:
    """给第一次不一致的指令配一条排查提示。"""
    opcode = inst & 0x7F
    f3 = (inst >> 12) & 0x7
    f7 = (inst >> 25) & 0x7F
    if opcode == 0x33:
        if f7 == 0x20:
            return "这是 sub/sra 一类「funct7=0100000 才取反」的指令，检查 inst[30] 是否参与控制。"
        if f7 == 0x01:
            return "这是 M 扩展指令，L01 只需要译码报错，L03 才实现乘法除法。"
        if f3 in (0x1, 0x5):
            return "移位指令：移位量只取 rs2 的低 5 位。"
        if f3 in (0x2, 0x3):
            return "比较指令：slt 用有符号比较（$signed），sltu 用无符号比较。"
        return "OP 类指令：先确认 funct3 译码表，再确认两个操作数都来自寄存器堆。"
    if opcode == 0x13:
        if f3 in (0x1, 0x5):
            return "立即数移位：移位量来自 inst[24:20]，srai 还要看 inst[30]。"
        if f3 in (0x2, 0x3):
            return "立即数比较：slti 有符号、sltiu 无符号（立即数先做符号扩展再按无符号比较）。"
        return "OP-IMM：立即数必须做符号扩展（imm[31:20]）。"
    if opcode in (0x03, 0x23):
        return "访存：检查字节偏移、写掩码（sb/sh/sw）和符号扩展（lb/lh/lbu/lhu）。"
    if opcode == 0x63:
        return "分支：检查立即数拼装（B 型不连续）和比较方向。"
    if opcode in (0x6F, 0x67):
        return "跳转：jal/jalr 都要把 PC+4 写回 rd；jalr 的目标地址最低位要清零。"
    if opcode == 0x37 or opcode == 0x17:
        return "U 型：立即数是高 20 位（低 12 位为 0），auipc 还要加上当前 PC。"
    if opcode == 0x73:
        return "SYSTEM：mpause（0x08000073）要能停机，其余指令 L01 可报非法。"
    return "对比一下黄金模型里这条指令的语义，再检查你的译码表。"


def compare_traces(gold, rtl, colorize: bool) -> tuple[bool, str]:
    if len(gold) != len(rtl):
        head = f"trace 行数不同：黄金模型 {len(gold)} 条，你的 RTL {len(rtl)} 条"
    else:
        head = ""
    n = min(len(gold), len(rtl))
    for i in range(n):
        if gold[i] != rtl[i]:
            gp, gi, gr, gw = gold[i]
            ap, ai, ar, aw = rtl[i]
            msg = [head] if head else []
            msg.append(f"第 {i + 1} 条指令不一致（pc=0x{gp:08x}）：")
            msg.append(f"  指令 : {disasm(gi)}   机器码 0x{gi:08x}")
            msg.append(f"  期望 : pc=0x{gp:08x} rd={gr:02d} wdata=0x{gw:08x}")
            msg.append(f"  实际 : pc=0x{ap:08x} rd={ar:02d} wdata=0x{aw:08x}")
            if gi != ai:
                msg.append(f"  注意：机器码也不同（你的 RTL 取到 0x{ai:08x} = {disasm(ai)}），检查取指是否落在正确地址。")
            msg.append("  提示 : " + explain_mismatch(gi))
            return False, "\n".join(msg)
    if len(gold) != len(rtl):
        extra = rtl[n] if len(rtl) > n else gold[n]
        who = "你的 RTL" if len(rtl) > n else "黄金模型"
        msg = [head, f"  第一个多出来的指令来自{who}：pc=0x{extra[0]:08x} {disasm(extra[1])}"]
        if len(rtl) > n:
            msg.append("  提示 : 检查停机条件：mpause 执行后不应再退休新指令。")
        else:
            msg.append("  提示 : 可能实现里提前停机了，检查 halted 的置位时机。")
        return False, "\n".join(msg)
    return True, ""


def compare_dmem(gold: list[int], rtl: list[int]) -> tuple[bool, str]:
    if len(rtl) != len(gold):
        return False, f"DTCM 长度不同：黄金模型 {len(gold)} 个字，你的 RTL {len(rtl)} 个字"
    bad = [i for i in range(len(gold)) if gold[i] != rtl[i]]
    if not bad:
        return True, ""
    lines = [f"DTCM 有 {len(bad)} 个字不一致，前几处："]
    for i in bad[:5]:
        addr = 0x10000 + i * 4
        lines.append(f"  0x{addr:05x}: 期望 0x{gold[i]:08x}  实际 0x{rtl[i]:08x}")
    if len(bad) > 5:
        lines.append(f"  ...（共 {len(bad)} 处）")
    return False, "\n".join(lines)


def run_one(name: str, rtl_file: str, vvp: str, colorize: bool, verbose: bool) -> tuple[bool, str]:
    src = os.path.join(HERE, "programs", name)
    build_dir = os.path.join(WORK, "build", os.path.splitext(name)[0])
    sim_dir = os.path.join(WORK, "sim", os.path.splitext(name)[0])

    try:
        built = build_program.build(src, build_dir)
    except SystemExit as exc:  # 工具链缺失等
        return False, f"编译失败（{exc}）"

    core = Core()
    try:
        core.load_elf(built.elf)
        gold_trace = core.run()
    except CoreFault as exc:
        return False, f"黄金模型执行失败：{exc}"
    gold_trace_tuples = [(r.pc, r.inst, r.rd, r.wdata) for r in gold_trace]
    gold_dmem = core.dump_dtcm_words()

    try:
        sim = run_rtl.run_sim(
            vvp, sim_dir, built.program_hex, built.data_hex,
            max_cycles=200_000, name=os.path.splitext(name)[0],
        )
    except run_rtl.RtlError as exc:
        return False, str(exc)

    if sim.timeout:
        return False, (
            "RTL 在 20 万个周期内没有停机。\n"
            "  提示 : 先确认 PC 会前进（next_pc 默认 pc+4），再确认 mpause 能置起 halted。"
        )
    if not sim.halted:
        return False, "RTL 没有报告停机。\n  提示 : o_halted 需要在执行 mpause 后拉起。"

    ok_t, msg_t = compare_traces(gold_trace_tuples, sim.trace, colorize)
    if not ok_t:
        return False, msg_t
    ok_d, msg_d = compare_dmem(gold_dmem, sim.dmem)
    if not ok_d:
        return False, msg_d
    return True, f"{len(gold_trace_tuples)} 条指令，DTCM 全量一致，{sim.cycles} 周期"


def collect_sources(main_file: str, rtl_dir: str) -> list[str]:
    """收集要编译的 RTL 文件。

    除了主文件之外，还会自动带上：
      * 同一目录下的其它 .sv（方便你把模块拆成多个文件）
      * L00 的 alu32.sv（这样 cpu_core 可以直接实例化 L00 的成果）
    同名模块只编译一次，避免「两个 cpu_core」这类重复定义。
    """
    def modules_of(path: str) -> set[str]:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return set()
        return set(re.findall(r"\bmodule\s+(\w+)", text))

    sources = [main_file]
    seen_paths = {os.path.realpath(main_file)}
    seen_modules = modules_of(main_file)

    candidates = sorted(glob.glob(os.path.join(rtl_dir, "*.sv")))
    l00_alu = os.path.join(LEARN, "lessons", "L00_setup", "rtl", "alu32.sv")
    if os.path.exists(l00_alu):
        candidates.append(l00_alu)

    for path in candidates:
        real = os.path.realpath(path)
        if real in seen_paths:
            continue
        mods = modules_of(path)
        if mods & seen_modules:
            # 已经有同名模块（例如另一个 cpu_core 参考实现），跳过
            continue
        seen_paths.add(real)
        seen_modules |= mods
        sources.append(path)
    return sources


def resolve_src(path: str, lesson_dir: str) -> str:
    """让 --from 既支持相对当前目录，也支持相对仓库根目录/课程目录的写法。"""
    if os.path.isabs(path):
        return path
    for base in (os.getcwd(), ROOT, lesson_dir):
        candidate = os.path.normpath(os.path.join(base, path))
        if os.path.exists(candidate):
            return candidate
    return os.path.normpath(os.path.join(os.getcwd(), path))


def main() -> int:
    ap = argparse.ArgumentParser(description="L01 检查器")
    ap.add_argument("--ref", action="store_true", help="检查参考实现而不是学员实现")
    ap.add_argument("--from", dest="src", default=None,
                    help="指定要检查的 cpu_core 文件，例如 refs/cpu_core_reuse.sv")
    ap.add_argument("--only", default=None, help="只跑名字包含该子串的用例")
    ap.add_argument("--list", action="store_true", help="列出用例")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    colorize = not args.no_color and sys.stdout.isatty()

    if args.list:
        for name in list_programs():
            print(name)
        return 0

    rtl_dir = os.path.join(LESSON, "refs" if args.ref else "rtl")
    rtl_file = resolve_src(args.src, LESSON) if args.src else os.path.join(rtl_dir, "cpu_core.sv")
    if not os.path.exists(rtl_file):
        print(f"找不到 {rtl_file}\n先运行 ./learn start L01 生成骨架文件。")
        return 2

    if not run_rtl.have_iverilog():
        print("找不到 iverilog，请运行 ./learn doctor --install")
        return 2

    os.makedirs(WORK, exist_ok=True)
    vvp = os.path.join(WORK, "sim.vvp")
    tb = os.path.join(HERE, "tb_cpu.sv")
    sources = collect_sources(rtl_file, os.path.dirname(os.path.abspath(rtl_file)))
    print("编译源文件：" + "、".join(os.path.relpath(p, ROOT) for p in [tb] + sources))
    print("")
    try:
        run_rtl.compile_rtl([tb] + sources, vvp)
    except run_rtl.RtlError as exc:
        print(color("RTL 编译失败", RED, colorize))
        print(exc)
        return 1

    programs = [p for p in list_programs() if not args.only or args.only in p]
    if not programs:
        print("没有匹配的用例")
        return 2

    label = "参考实现" if args.ref else "你的实现"
    print(f"L01 检查（{label}）：{rtl_file}")
    print("")
    passed = 0
    for name in programs:
        ok, msg = run_one(name, rtl_file, vvp, colorize, verbose=False)
        tag = color("通过", GREEN, colorize) if ok else color("失败", RED, colorize)
        print(f"[{tag}] {name}")
        if msg:
            for line in msg.splitlines():
                print("       " + line)
        passed += 1 if ok else 0
    print("")
    total = len(programs)
    summary = f"{passed}/{total} 个用例通过"
    print(color(summary, GREEN if passed == total else RED, colorize))
    # --from / --ref 是"对比与自检"用法，不写入学习进度
    if not args.ref and not args.only and not args.src:
        record_progress(passed, total)
    if passed != total:
        print("提示：./learn hint L01 可以按顺序拿到分级提示。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

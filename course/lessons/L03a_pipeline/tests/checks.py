#!/usr/bin/env python3
"""L03a 检查器：流水线核心的正确性 + 指令吞吐（CPI）。

正确性判定和 L01/L02 一样：trace 逐条一致 + DTCM 全量一致，
每个程序还要跑两种存储器延迟（0 / 2），一共 12 次。

另外会打印 CPI（周期数 / 退休指令数），用来和第 2 课的"单周期 + 多周期 LSU"
对比：流水线并不自动让 CPI 变好——它买的是频率，CPI 要靠冒险处理来改善。

用法：
  ./learn check L03a
  ./learn check L03a --ref
  ./learn check L03a --only 05
  ./learn check L03a --from <你的 pipeline_core.sv>
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

WORK = os.path.join(LEARN, "work", "L03a")
L01_PROGRAMS = os.path.join(LEARN, "lessons", "L01_scalar", "tests", "programs")
L02_PROGRAMS = os.path.join(LEARN, "lessons", "L02_lsu", "tests", "programs")
LATENCIES = (0, 2)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def color(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled else text


def record_progress(passed: int, total: int) -> None:
    state_dir = os.path.join(LEARN, ".state")
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, "progress.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data["L03a"] = {"passed": passed, "total": total,
                    "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def programs() -> list[tuple[str, str]]:
    out = [(n, os.path.join(L01_PROGRAMS, n)) for n in sorted(os.listdir(L01_PROGRAMS))
           if n.endswith((".S", ".c"))]
    out += [(n, os.path.join(L02_PROGRAMS, n)) for n in sorted(os.listdir(L02_PROGRAMS))
            if n.endswith((".S", ".c"))]
    return out


def explain(inst: int) -> str:
    opcode = inst & 0x7F
    if opcode == 0x03:
        return "载入结果不对：检查 load-use 停顿（TODO 3）与 MEM/WB→EX 的旁路（TODO 1）。"
    if opcode in (0x33, 0x13):
        return "运算结果不对：多半是旁路没接全（MEM→EX / WB→EX），或气泡的控制位没清零。"
    if opcode == 0x23:
        return "存储地址/数据不对：确认 store 的地址（rs1+imm_s）与数据经过了旁路。"
    if opcode in (0x63, 0x6F, 0x67):
        return ("跳转/分支之后立刻出错：检查冲刷（TODO 4）——错路指令不能退休，"
                "PC 必须重定向到目标。")
    return "这条指令出错时，先看它前面 1~2 条指令是不是还在流水线里（冒险没处理干净）。"


def run_one(name: str, src: str, vvp: str, latency: int) -> tuple[bool, str, int, int]:
    build_dir = os.path.join(WORK, "build", os.path.splitext(name)[0])
    sim_dir = os.path.join(WORK, "sim", os.path.splitext(name)[0])
    try:
        built = build_program.build(src, build_dir)
    except SystemExit as exc:
        return False, f"编译失败（{exc}）", 0, 0

    core = Core()
    try:
        core.load_elf(built.elf)
        gold = [(r.pc, r.inst, r.rd, r.wdata) for r in core.run()]
    except CoreFault as exc:
        return False, f"黄金模型执行失败：{exc}", 0, 0

    try:
        sim = run_rtl.run_sim(vvp, sim_dir, built.program_hex, built.data_hex,
                              name=f"{os.path.splitext(name)[0]}_lat{latency}",
                              plusargs={"LATENCY": latency}, max_cycles=200_000)
    except run_rtl.RtlError as exc:
        return False, str(exc), 0, len(gold)

    if sim.timeout:
        return False, ("RTL 超时：流水线可能卡在停顿条件里（例如 stall 一直为 1），"
                       "或者冲刷后没有回到正常取指。"), 0, len(gold)
    if not sim.halted:
        return False, "RTL 没有报告停机（停机指令可能被冲刷掉了？）", 0, len(gold)

    if len(gold) != len(sim.trace):
        head = f"trace 行数不同：黄金模型 {len(gold)} 条，你的 RTL {len(sim.trace)} 条"
    else:
        head = ""
    for i in range(min(len(gold), len(sim.trace))):
        if gold[i] != sim.trace[i]:
            gp, gi, gr, gw = gold[i]
            ap, ai, ar, aw = sim.trace[i]
            lines = [head] if head else []
            lines.append(f"第 {i+1} 条指令不一致（pc=0x{gp:08x}）：")
            lines.append(f"  指令 : {disasm(gi)}   机器码 0x{gi:08x}")
            lines.append(f"  期望 : rd={gr:02d} wdata=0x{gw:08x}")
            lines.append(f"  实际 : rd={ar:02d} wdata=0x{aw:08x}")
            lines.append("  提示：" + explain(gi))
            return False, "\n".join(lines), sim.cycles, len(gold)

    if core.dump_dtcm_words() != sim.dmem:
        g = core.dump_dtcm_words()
        bad = [i for i in range(min(len(g), len(sim.dmem))) if g[i] != sim.dmem[i]]
        lines = [f"trace 一致，但 DTCM 有 {len(bad)} 个字不同（前几处）："]
        for i in bad[:4]:
            lines.append(f"  0x{0x10000 + i*4:05x}: 期望 0x{g[i]:08x}  实际 0x{sim.dmem[i]:08x}")
        lines.append("  提示：store 的数据/地址走的是旁路（fwd_b / alu_y），检查它们用的是不是最新值。")
        return False, "\n".join(lines), sim.cycles, len(gold)

    return True, "", sim.cycles, len(gold)


def collect_sources(main_file: str, lsu_file: str) -> list[str]:
    def modules_of(path: str) -> set[str]:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return set()
        return set(re.findall(r"\bmodule\s+(\w+)", text))

    sources = [os.path.join(LEARN, "lessons", "L02_lsu", "tests", "tb_cpu.sv"),
               main_file, lsu_file]
    seen = set()
    for path in sources:
        seen |= modules_of(path)
    l00_alu = os.path.join(LEARN, "lessons", "L00_setup", "rtl", "alu32.sv")
    for extra in [l00_alu] + sorted(glob.glob(os.path.join(os.path.dirname(main_file), "*.sv"))):
        if not os.path.exists(extra) or extra in sources:
            continue
        mods = modules_of(extra)
        if mods & seen:
            continue
        seen |= mods
        sources.append(extra)
    return sources


def resolve_src(path: str, lesson_dir: str) -> str:
    if os.path.isabs(path):
        return path
    for base in (os.getcwd(), ROOT, lesson_dir):
        candidate = os.path.normpath(os.path.join(base, path))
        if os.path.exists(candidate):
            return candidate
    return os.path.normpath(os.path.join(os.getcwd(), path))


def main() -> int:
    ap = argparse.ArgumentParser(description="L03a 检查器（流水线与冒险）")
    ap.add_argument("--ref", action="store_true", help="检查参考实现")
    ap.add_argument("--from", dest="src", default=None, help="指定你的 pipeline_core.sv")
    ap.add_argument("--lsu", dest="lsu", default=None, help="指定用哪个 lsu.sv（默认用你 L02 的实现）")
    ap.add_argument("--only", default=None, help="只跑名字包含该子串的用例")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    colorize = not args.no_color and sys.stdout.isatty()

    if args.list:
        for name, _ in programs():
            print(name)
        return 0

    rtl_dir = os.path.join(LESSON, "refs" if args.ref else "rtl")
    core_file = resolve_src(args.src, LESSON) if args.src else os.path.join(rtl_dir, "pipeline_core.sv")
    lsu_dir = os.path.join(LEARN, "lessons", "L02_lsu", "refs" if args.ref else "rtl")
    lsu_file = resolve_src(args.lsu, LESSON) if args.lsu else os.path.join(lsu_dir, "lsu.sv")

    for path, what in ((core_file, "pipeline_core.sv"), (lsu_file, "lsu.sv")):
        if not os.path.exists(path):
            print(f"找不到{what}：{path}")
            return 2
    if not run_rtl.have_iverilog():
        print("找不到 iverilog，请运行 ./learn doctor --install")
        return 2

    os.makedirs(WORK, exist_ok=True)
    vvp = os.path.join(WORK, "sim.vvp")
    sources = collect_sources(core_file, lsu_file)
    print("编译源文件：" + "、".join(os.path.relpath(p, ROOT) for p in sources))
    print("")
    try:
        run_rtl.compile_rtl(sources, vvp, top="tb_cpu")
    except run_rtl.RtlError as exc:
        print(color("RTL 编译失败", RED, colorize))
        print(exc)
        return 1

    cases = [(n, p) for n, p in programs() if not args.only or args.only in n]
    if not cases:
        print("没有匹配的用例")
        return 2

    label = "参考实现" if args.ref else "你的实现"
    print(f"L03a 检查（{label}）：{os.path.relpath(core_file, ROOT)}")
    print("")
    passed = 0
    total = 0
    for name, src in cases:
        results = []
        for latency in LATENCIES:
            ok, msg, cycles, ninst = run_one(name, src, vvp, latency)
            results.append((latency, ok, msg, cycles, ninst))
            total += 1
            passed += 1 if ok else 0
        all_ok = all(r[1] for r in results)
        tag = color("通过", GREEN, colorize) if all_ok else color("失败", RED, colorize)
        cpi_bits = "，".join(
            f"lat{r[0]}: {r[3]} 周期/{r[4]} 条 = CPI {r[3] / max(1, r[4]):.2f}"
            for r in results if r[1]
        )
        print(f"[{tag}] {name}" + (f"   {cpi_bits}" if cpi_bits else ""))
        for latency, ok, msg, _, _ in results:
            if not ok:
                print(f"       latency={latency}:")
                for line in msg.splitlines():
                    print("         " + line)
    print("")
    print(color(f"{passed}/{total} 次运行通过（每个程序跑 {len(LATENCIES)} 种存储器延迟）",
                GREEN if passed == total else RED, colorize))
    if passed == total:
        print(color("提示：CPI 是流水线调优的起点。可以用 --only 05 单独看某个程序的 CPI，"
                    "再对照 L02 单周期核的周期数。", DIM, colorize))
    if not args.ref and not args.only and not args.src:
        record_progress(passed, total)
    if passed != total:
        print("提示：./learn hint L03a 可以按顺序拿到分级提示。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

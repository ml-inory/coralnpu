#!/usr/bin/env python3
"""L02 检查器：把学员的 LSU 放进核心，跑 L01 的 5 个程序 + 非对齐程序。

判定标准（对每个程序、每种存储器延迟都要满足）：
  1. trace 完全一致：每条退休指令的 pc / 机器码 / 目标寄存器 / 写回值
  2. DTCM 全量一致：包括非对齐访问造成的字节级修改

为什么要跑两种延迟：存储器不是永远当拍就绪的。latency=0 对应 L01 的组合读，
latency=2 表示"发出请求后要等 2 拍"。两种都要对，才说明握手逻辑写对了。

用法：
  ./learn check L02
  ./learn check L02 --ref              # 检查参考实现
  ./learn check L02 --only 06          # 只跑非对齐那个用例
  ./learn check L02 --from <lsu 文件>   # 指定你的 LSU 实现
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

WORK = os.path.join(LEARN, "work", "L02")
L01_PROGRAMS = os.path.join(LEARN, "lessons", "L01_scalar", "tests", "programs")
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
    data["L02"] = {"passed": passed, "total": total,
                   "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def programs() -> list[tuple[str, str]]:
    out = []
    for name in sorted(os.listdir(L01_PROGRAMS)):
        if name.endswith((".S", ".c")):
            out.append((name, os.path.join(L01_PROGRAMS, name)))
    for name in sorted(os.listdir(os.path.join(HERE, "programs"))):
        if name.endswith((".S", ".c")):
            out.append((name, os.path.join(HERE, "programs", name)))
    return out


def explain(inst: int) -> str:
    opcode = inst & 0x7F
    if opcode in (0x03, 0x23):
        return ("访存类指令出错：先确认地址（load 用 imm_i、store 用 imm_s）、"
                "再确认掩码与数据左移 8*addr[1:0]，最后确认载入的字节重排与扩展。")
    if opcode == 0x6F or opcode == 0x67:
        return "跳转指令出错：LSU 卡住时 PC 不能前进，检查 commit 条件。"
    return "这条指令出错时，先看它的前一条访存指令是否已经正确提交。"


def run_one(name: str, src: str, vvp: str, latency: int) -> tuple[bool, str]:
    build_dir = os.path.join(WORK, "build", os.path.splitext(name)[0])
    sim_dir = os.path.join(WORK, "sim", os.path.splitext(name)[0])
    try:
        built = build_program.build(src, build_dir)
    except SystemExit as exc:
        return False, f"编译失败（{exc}）"

    core = Core()
    try:
        core.load_elf(built.elf)
        gold_trace = [(r.pc, r.inst, r.rd, r.wdata) for r in core.run()]
    except CoreFault as exc:
        return False, f"黄金模型执行失败：{exc}"

    try:
        sim = run_rtl.run_sim(vvp, sim_dir, built.program_hex, built.data_hex,
                              name=f"{os.path.splitext(name)[0]}_lat{latency}",
                              plusargs={"LATENCY": latency})
    except run_rtl.RtlError as exc:
        return False, str(exc)

    if sim.timeout:
        return False, ("RTL 超时：LSU 可能一直 busy（等不到 ready、或忘了回 IDLE），"
                       "或者存储器请求发出后 done 从未拉起。")
    if not sim.halted:
        return False, "RTL 没有报告停机。"

    if len(gold_trace) != len(sim.trace):
        head = f"trace 行数不同：黄金模型 {len(gold_trace)} 条，你的 RTL {len(sim.trace)} 条"
    else:
        head = ""
    for i in range(min(len(gold_trace), len(sim.trace))):
        if gold_trace[i] != sim.trace[i]:
            gp, gi, gr, gw = gold_trace[i]
            ap, ai, ar, aw = sim.trace[i]
            lines = [head] if head else []
            lines.append(f"第 {i+1} 条指令不一致（pc=0x{gp:08x}）：")
            lines.append(f"  指令 : {disasm(gi)}   机器码 0x{gi:08x}")
            lines.append(f"  期望 : rd={gr:02d} wdata=0x{gw:08x}")
            lines.append(f"  实际 : rd={ar:02d} wdata=0x{aw:08x}")
            if gr == 0 and gw == 0 and aw != 0:
                lines.append("  提示：非访存/存储指令的 trace 里 wdata 必须是 0（见接口约定）。")
            lines.append("  提示：" + explain(gi))
            return False, "\n".join(lines)

    if core.dump_dtcm_words() != sim.dmem:
        gold = core.dump_dtcm_words()
        bad = [i for i in range(min(len(gold), len(sim.dmem))) if gold[i] != sim.dmem[i]]
        lines = [f"trace 一致，但 DTCM 有 {len(bad)} 个字不同（前几处）："]
        for i in bad[:5]:
            lines.append(f"  0x{0x10000 + i*4:05x}: 期望 0x{gold[i]:08x}  实际 0x{sim.dmem[i]:08x}")
        lines.append("  提示：这类差异通常是写掩码/数据对齐错（store 写错了字节），"
                     "或者非对齐拆分时漏了第二笔事务。")
        return False, "\n".join(lines)

    return True, f"{len(gold_trace)} 条指令，latency={latency}，{sim.cycles} 周期"


def collect_sources(main_file: str, rtl_dir: str) -> list[str]:
    """tb + 课程提供的核心 wrapper + 学员的 lsu.sv + L00 的 alu32.sv"""
    def modules_of(path: str) -> set[str]:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return set()
        return set(re.findall(r"\bmodule\s+(\w+)", text))

    sources = [os.path.join(HERE, "tb_cpu.sv"),
               os.path.join(HERE, "core_wrapper.sv"),
               main_file]
    seen_modules: set[str] = set()
    for path in [os.path.join(HERE, "core_wrapper.sv"), main_file]:
        seen_modules |= modules_of(path)

    l00_alu = os.path.join(LEARN, "lessons", "L00_setup", "rtl", "alu32.sv")
    for extra in [l00_alu] + sorted(glob.glob(os.path.join(rtl_dir, "*.sv"))):
        if not os.path.exists(extra) or os.path.realpath(extra) == os.path.realpath(main_file):
            continue
        mods = modules_of(extra)
        if mods & seen_modules:
            continue
        seen_modules |= mods
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
    ap = argparse.ArgumentParser(description="L02 检查器")
    ap.add_argument("--ref", action="store_true", help="检查参考实现")
    ap.add_argument("--from", dest="src", default=None, help="指定你的 lsu.sv")
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
    lsu_file = resolve_src(args.src, LESSON) if args.src else os.path.join(rtl_dir, "lsu.sv")
    if not os.path.exists(lsu_file):
        print(f"找不到 {lsu_file}")
        return 2
    if not run_rtl.have_iverilog():
        print("找不到 iverilog，请运行 ./learn doctor --install")
        return 2

    os.makedirs(WORK, exist_ok=True)
    vvp = os.path.join(WORK, "sim.vvp")
    sources = collect_sources(lsu_file, os.path.dirname(os.path.abspath(lsu_file)))
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
    print(f"L02 检查（{label}）：{os.path.relpath(lsu_file, ROOT)}")
    print("")
    passed = 0
    total = 0
    for name, src in cases:
        results = []
        for latency in LATENCIES:
            ok, msg = run_one(name, src, vvp, latency)
            results.append((latency, ok, msg))
            total += 1
            passed += 1 if ok else 0
        all_ok = all(ok for _, ok, _ in results)
        tag = color("通过", GREEN, colorize) if all_ok else color("失败", RED, colorize)
        print(f"[{tag}] {name}")
        for latency, ok, msg in results:
            if ok:
                print(f"       latency={latency}: {msg}")
            else:
                print(f"       latency={latency}:")
                for line in msg.splitlines():
                    print("         " + line)
    print("")
    print(color(f"{passed}/{total} 次运行通过（每个程序跑 {len(LATENCIES)} 种存储器延迟）",
                GREEN if passed == total else RED, colorize))
    if not args.ref and not args.only and not args.src:
        record_progress(passed, total)
    if passed != total:
        print("提示：./learn hint L02 可以按顺序拿到分级提示。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

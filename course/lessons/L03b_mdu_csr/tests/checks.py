#!/usr/bin/env python3
"""L03b 检查器：M 扩展（乘除法）+ CSR + 异常。

三组用例：
  * 07_mul_div.S     —— 8 条 M 扩展指令 + 除零/溢出边界
  * 08_csr.S         —— csrrw/csrrs/csrrc + 立即数形式、只读寄存器、x0 不写
  * 09_exception.S   —— ecall / 非法指令 → 异常入口 → mret 返回
回归：L01/L02 的程序也一起跑，确保加了新功能后旧行为没被破坏。

每个程序跑两种存储器延迟（0/2）。判定标准与前面一致：trace 逐条一致 + DTCM 全量一致。

用法：
  ./learn check L03b
  ./learn check L03b --ref
  ./learn check L03b --only 09
  ./learn check L03b --mdu <文件> --csr <文件>
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

WORK = os.path.join(LEARN, "work", "L03b")
LATENCIES = (0, 2)
L03B_PROGRAMS = os.path.join(HERE, "programs")
L01_PROGRAMS = os.path.join(LEARN, "lessons", "L01_scalar", "tests", "programs")
L02_PROGRAMS = os.path.join(LEARN, "lessons", "L02_lsu", "tests", "programs")

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
    data["L03B"] = {"passed": passed, "total": total,
                    "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def programs() -> list[tuple[str, str, str]]:
    """返回 (名字, 路径, -march)。"""
    out = [(n, os.path.join(L03B_PROGRAMS, n), "rv32im_zicsr")
           for n in sorted(os.listdir(L03B_PROGRAMS)) if n.endswith((".S", ".c"))]
    out += [(n, os.path.join(L01_PROGRAMS, n), "rv32i")
            for n in sorted(os.listdir(L01_PROGRAMS)) if n.endswith((".S", ".c"))]
    out += [(n, os.path.join(L02_PROGRAMS, n), "rv32i")
            for n in sorted(os.listdir(L02_PROGRAMS)) if n.endswith((".S", ".c"))]
    return out


def explain(inst: int) -> str:
    opcode = inst & 0x7F
    funct7 = (inst >> 25) & 0x7F
    if opcode == 0x33 and funct7 == 0x01:
        return ("M 扩展出错：检查 mulh/mulhsu/mulhu 的符号扩展，以及 div/rem 的"
                "除零与 INT_MIN/-1 边界（参考基础知识第 1 章）。")
    if opcode == 0x73:
        return ("CSR/异常指令出错：检查 CSR 的读出值、set/clear 语义、"
                "rs1=x0 不写、以及异常时的 mepc/mcause 与 mret 的返回地址。")
    if opcode == 0x03:
        return "载入结果不对：先确认前面没有被异常/CSR 打乱执行流。"
    return "这条指令出错时，先看它前面几条是不是 M 扩展或 CSR 指令。"


def run_one(name: str, src: str, march: str, vvp: str, latency: int) -> tuple[bool, str, int, int]:
    build_dir = os.path.join(WORK, "build", os.path.splitext(name)[0])
    sim_dir = os.path.join(WORK, "sim", os.path.splitext(name)[0])
    try:
        built = build_program.build(src, build_dir, march=march)
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
        return False, ("RTL 超时：检查异常入口/返回是否形成死循环"
                       "（例如 mret 返回到了触发异常的指令本身）。"), 0, len(gold)
    if not sim.halted:
        return False, "RTL 没有报告停机。", 0, len(gold)

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
        lines.append("  提示：异常处理程序写回的值不对（mepc/mcause），或 CSR 写没生效。")
        return False, "\n".join(lines), sim.cycles, len(gold)

    return True, "", sim.cycles, len(gold)


def collect_sources(mdu_file: str, csr_file: str) -> list[str]:
    def modules_of(path: str) -> set[str]:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return set()
        return set(re.findall(r"\bmodule\s+(\w+)", text))

    l02_dir = os.path.join(LEARN, "lessons", "L02_lsu", "rtl")
    l00_alu = os.path.join(LEARN, "lessons", "L00_setup", "rtl", "alu32.sv")
    sources = [os.path.join(LEARN, "lessons", "L02_lsu", "tests", "tb_cpu.sv"),
               os.path.join(HERE, "core_l03b.sv"),
               mdu_file, csr_file,
               os.path.join(l02_dir, "lsu.sv"),
               l00_alu]
    seen: set[str] = set()
    out: list[str] = []
    for path in sources:
        mods = modules_of(path)
        if mods & seen:
            continue
        seen |= mods
        out.append(path)
    return [p for p in out if os.path.exists(p)]


def resolve(path: str) -> str:
    if os.path.isabs(path):
        return path
    for base in (os.getcwd(), ROOT, LESSON):
        candidate = os.path.normpath(os.path.join(base, path))
        if os.path.exists(candidate):
            return candidate
    return os.path.normpath(os.path.join(os.getcwd(), path))


def main() -> int:
    ap = argparse.ArgumentParser(description="L03b 检查器（M 扩展 / CSR / 异常）")
    ap.add_argument("--ref", action="store_true", help="用参考实现检查")
    ap.add_argument("--mdu", default=None, help="指定你的 mdu.sv")
    ap.add_argument("--csr", default=None, help="指定你的 csr_file.sv")
    ap.add_argument("--only", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    colorize = not args.no_color and sys.stdout.isatty()

    if args.list:
        for name, _, _ in programs():
            print(name)
        return 0

    rtl_dir = os.path.join(LESSON, "refs" if args.ref else "rtl")
    mdu_file = resolve(args.mdu) if args.mdu else os.path.join(rtl_dir, "mdu.sv")
    csr_file = resolve(args.csr) if args.csr else os.path.join(rtl_dir, "csr_file.sv")
    for path, what in ((mdu_file, "mdu.sv"), (csr_file, "csr_file.sv")):
        if not os.path.exists(path):
            print(f"找不到 {what}：{path}")
            return 2
    if not run_rtl.have_iverilog():
        print("找不到 iverilog，请运行 ./learn doctor --install")
        return 2

    os.makedirs(WORK, exist_ok=True)
    vvp = os.path.join(WORK, "sim.vvp")
    sources = collect_sources(mdu_file, csr_file)
    print("编译源文件：" + "、".join(os.path.relpath(p, ROOT) for p in sources))
    print("")
    try:
        run_rtl.compile_rtl(sources, vvp, top="tb_cpu")
    except run_rtl.RtlError as exc:
        print(color("RTL 编译失败", RED, colorize))
        print(exc)
        return 1

    cases = [(n, p, m) for n, p, m in programs() if not args.only or args.only in n]
    if not cases:
        print("没有匹配的用例")
        return 2

    label = "参考实现" if args.ref else "你的实现"
    print(f"L03b 检查（{label}）：{os.path.relpath(mdu_file, ROOT)} + {os.path.relpath(csr_file, ROOT)}")
    print("")
    passed = 0
    total = 0
    for name, src, march in cases:
        results = []
        for latency in LATENCIES:
            ok, msg, cycles, ninst = run_one(name, src, march, vvp, latency)
            results.append((latency, ok, msg, cycles, ninst))
            total += 1
            passed += 1 if ok else 0
        all_ok = all(r[1] for r in results)
        tag = color("通过", GREEN, colorize) if all_ok else color("失败", RED, colorize)
        cpi = "，".join(f"lat{r[0]}: {r[3]} 周期/{r[4]} 条" for r in results if r[1])
        print(f"[{tag}] {name}" + (f"   {cpi}" if cpi else ""))
        for latency, ok, msg, _, _ in results:
            if not ok:
                print(f"       latency={latency}:")
                for line in msg.splitlines():
                    print("         " + line)
    print("")
    print(color(f"{passed}/{total} 次运行通过（每个程序跑 {len(LATENCIES)} 种存储器延迟）",
                GREEN if passed == total else RED, colorize))
    if not args.ref and not args.only and not args.mdu and not args.csr:
        record_progress(passed, total)
    if passed != total:
        print("提示：./learn hint L03b 可以按顺序拿到分级提示。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

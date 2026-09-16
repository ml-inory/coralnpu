#!/usr/bin/env python3
"""L04 检查器：AXI 外壳、控制寄存器与 5 步启动流程。

三组 L04 用例：
  * 10_boot.S     —— 5 步启动（写 ITCM → PC_START → 释放门控 → 释放复位 → 轮询 STATUS）
  * 11_data_axi.S —— 字节/半字/跨字访问，压 AXI 主接口的 WSTRB 与地址拆分
  * 12_fault.S    —— 没有处理程序的异常 → STATUS.FAULT（这条没有黄金模型对照）
再加两个回归程序（L03b 的 M 扩展、L02 的非对齐访存），确认新外壳没破坏旧行为。

每个程序跑两种总线延迟（0/2）。

判定标准 = 黄金模型逐条对拍 + 启动流程断言：
  * trace 与黄金模型逐条一致、DTCM 全量一致（同 L01～L03）；
  * 主机 5 步都走通，读回的值与写入一致；
  * trace 第一条的 pc 等于 PC_START（证明 PC_START 真的生效，而不是从 0 开始跑）；
  * 数据访问真的经过 AXI 主接口（事务计数 > 0）；
  * 未映射地址返回 SLVERR（不是悄悄返回 0）。

用法：
  ./learn check L04
  ./learn check L04 --ref
  ./learn check L04 --only 10
  ./learn check L04 --axi <axi_lite_slave.sv> --shell <axi_boot_shell.sv>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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

WORK = os.path.join(LEARN, "work", "L04")
LATENCIES = (0, 2)
WAVES = False          # --waves 时打开波形转储（./learn wave 会用）

# 失败时自动打印的信号：按通道拆开，每组都很短，避免"信号太多看麻了"
AUTO_GROUPS = [
    ("写通道", "s_awvalid,s_awready,s_wvalid,s_wready,s_bvalid,s_bready"),
    ("读通道", "s_arvalid,s_arready,s_rvalid,s_rready"),
]
WAVE_WINDOW = 40      # 看最后 40 拍（卡住的地方在尾部），只留变化行


def autopsy(name: str, latency: int, log: str) -> str:
    """失败后自动重跑一次带波形的仿真，返回"期望/实际 + 内部信号"的说明。

    默认检查只跑一次（快）；失败才做这件事，所以正常通过的用例不受影响。
    """
    stem = os.path.splitext(name)[0]
    build_dir = os.path.join(WORK, "build", stem)
    sim_dir = os.path.join(WORK, "sim", stem)
    vcd = os.path.join(WORK, "waves", f"{stem}_lat{latency}.vcd")
    os.makedirs(os.path.dirname(vcd), exist_ok=True)

    pro_hex = os.path.join(build_dir, "program.hex")
    data_hex = os.path.join(build_dir, "data.hex")
    elf = os.path.join(build_dir, stem + ".elf")
    entry = 0
    try:
        from golden.elf import load_elf
        entry = load_elf(elf).entry
    except Exception:                     # noqa: BLE001
        pass

    try:
        run_rtl.run_sim(os.path.join(WORK, "sim.vvp"), sim_dir, pro_hex, data_hex,
                        name=f"{stem}_autopsy_{latency}",
                        plusargs={"ENTRY": entry, "LATENCY": latency, "WAVES": 1, "VCD": vcd},
                        max_cycles=200_000)
    except run_rtl.RtlError as exc:
        return f"  （自动波形失败：{exc}）"

    lines = []
    host = [l.strip() for l in log.splitlines() if l.strip().startswith("HOST ")]
    if host:
        lines.append("  测试平台的观测值（resp: 0=OKAY  2=SLVERR）：")
        lines += [f"    {l}" for l in host[:6]]
        if any("resp=2" in l for l in host[:3]):
            lines.append("    期望：ITCM(0x0)/CSR(0x30000) 命中时 resp 应为 0；只有未映射地址才是 2。")

    tool = os.path.join(LEARN, "tools", "vcd.py")
    for title, signals in AUTO_GROUPS:
        proc = subprocess.run([sys.executable, tool, vcd, "--signals", signals,
                               "--cycles", str(WAVE_WINDOW), "--changes-only", "--elide", "16"],
                              capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            body = [l for l in proc.stdout.strip().splitlines()
                    if not l.startswith("说明：") and not l.startswith("（已折叠")]
            if len(body) <= 3:      # 只有表头/分隔线，说明这一路没动过
                lines.append(f"  {title}：最后 {WAVE_WINDOW} 拍没有任何变化")
                continue
            lines.append(f"  {title}（最后 {WAVE_WINDOW} 拍里发生变化的行；中间相同的重复已省略）：")
            lines += ["    " + l for l in body]
    lines.append(f"    完整波形：{os.path.relpath(vcd, ROOT)}"
                 f"（./learn wave L04 --only 10 --signals xxx 可以自己选信号）")
    return "\n".join(lines)
L04_PROGRAMS = os.path.join(HERE, "programs")
LINK_L04 = os.path.join(HERE, "link", "learn_tcm_0x100.ld")
L03B_PROGRAMS = os.path.join(LEARN, "lessons", "L03b_mdu_csr", "tests", "programs")
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
    data["L04"] = {"passed": passed, "total": total,
                   "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def programs() -> list[tuple[str, str, str, str, str | None, bool]]:
    """返回 (名字, 路径, -march, 模式, 链接脚本, 是否需要读事务)。

    模式：
      golden —— 有黄金模型，逐条对拍
      fault  —— 没有处理程序的异常，只校验主机观察到的 FAULT 与证据

    是否需要读事务：程序里必须有 load 才能要求 m_axi 上有读事务，
    07_mul_div.S 这类只写不读的回归程序不要求。
    """
    out = [
        ("10_boot.S", os.path.join(L04_PROGRAMS, "10_boot.S"), "rv32im_zicsr", "golden", LINK_L04, True),
        ("11_data_axi.S", os.path.join(L04_PROGRAMS, "11_data_axi.S"), "rv32im_zicsr", "golden", LINK_L04, True),
        ("12_fault.S", os.path.join(L04_PROGRAMS, "12_fault.S"), "rv32im_zicsr", "fault", LINK_L04, False),
        # 回归：这两个程序用默认链接脚本（入口 0x0），顺带验证 PC_START=0 也能跑
        ("07_mul_div.S", os.path.join(L03B_PROGRAMS, "07_mul_div.S"), "rv32im_zicsr", "golden", None, False),
        ("06_unaligned.S", os.path.join(L02_PROGRAMS, "06_unaligned.S"), "rv32i", "golden", None, True),
    ]
    return out


def explain(inst: int) -> str:
    if inst == 0x0800_0073:
        return "mpause：停机指令，核心应该已经置位 o_halted。"
    return "AXI 外壳出错：检查地址译码、CSR 读写、核心数据访问是否真的走了 m_axi 主接口。"


def boot_flow_problems(log: str, entry: int, mode: str, need_rd: bool) -> list[str]:
    """从测试平台日志里核对 5 步启动流程。"""
    bad: list[str] = []
    if "主机/总线卡住" in log:
        bad.append("AXI 握手卡住了：从接口迟迟没有响应主机的读写请求。"
                   "先查 s_awready / s_wready / s_arready 什么时候才会拉高。")
        return bad

    m = re.search(r"HOST step1_words=(\d+) entry=0x([0-9a-f]+) first=0x[0-9a-f]+ resp=(\d+)", log)
    if not m:
        bad.append("主机的第 1 步（通过 s_axi 写 ITCM）没有完成。")
    else:
        if int(m.group(1)) == 0:
            bad.append("第 1 步写了 0 个字——程序镜像没有送进 ITCM。")
        if int(m.group(2), 16) != entry:
            bad.append(f"第 1 步读回的入口地址错误：期望 0x{entry:08x}，实际 {m.group(2)}。")
        if m.group(3) != "0":
            bad.append("第 1 步里出现过非 OKAY 的写响应（s_axi 的写路径有问题）。")
    if "itcm_write_err" in log:
        bad.append("写 ITCM 时从接口返回了错误响应——地址译码范围不对。")

    m = re.search(r"HOST step2_pc_start=0x([0-9a-f]+) resp=(\d+)", log)
    if not m:
        bad.append("主机的第 2 步（写 PC_START 并读回）没有完成。")
    else:
        if int(m.group(1), 16) != entry:
            bad.append(f"PC_START 读回值不对：期望 0x{entry:08x}，实际 0x{m.group(1)}。")
        if m.group(2) != "0":
            bad.append("读 PC_START 返回了错误响应。")

    m = re.search(r"HOST step3_reset_control=0x([0-9a-f]+)", log)
    if not m or int(m.group(1), 16) != 0x1:
        bad.append("第 3 步（RESET=1 + 释放时钟门控）读回的 RESET_CONTROL 不是 0x1。")
    m = re.search(r"HOST step4_reset_control=0x([0-9a-f]+)", log)
    if not m or int(m.group(1), 16) != 0x0:
        bad.append("第 4 步（释放复位）读回的 RESET_CONTROL 不是 0x0。")

    m = re.search(r"HOST probe_unmapped=0x00000000 resp=(\d+)", log)
    if not m or m.group(1) != "2":
        bad.append("未映射地址没有返回 SLVERR(2)——地址译码的错误响应没接出来。")

    if mode == "golden":
        m = re.search(r"HOST halted=1 status=0x([0-9a-f]+)", log)
        if not m:
            bad.append("主机没有观察到 HALTED（STATUS.bit0）——STATUS 没接对，或者核心没跑起来。")
        elif not (int(m.group(1), 16) & 0x1):
            bad.append("STATUS.HALTED 位不为 1。")
    else:
        if "HOST fault=1" not in log:
            bad.append("主机没有观察到 FAULT（STATUS.bit1）——核心的 o_fault 没接进 STATUS。")

    m = re.search(r"HOST axi_txns rd=(\d+) wr=(\d+)", log)
    if not m:
        bad.append("测试平台没有统计到 AXI 主接口的事务。")
    else:
        rd_n, wr_n = int(m.group(1)), int(m.group(2))
        if wr_n < 1:
            bad.append("m_axi 上没有写事务——核心的 store 没有走主接口。")
        if need_rd and rd_n < 1:
            bad.append("m_axi 上没有读事务——核心的 load 没有走主接口。")
    return bad


def run_case(name: str, path: str, march: str, mode: str, linker: str | None,
             need_rd: bool, vvp: str, latency: int):
    build_dir = os.path.join(WORK, f"{os.path.splitext(name)[0]}_lat{latency}")
    try:
        built = build_program.build(path, build_dir, linker=linker, march=march)
    except SystemExit as exc:
        return False, f"编译失败（{exc}）", 0, 0

    core = None
    gold: list[tuple[int, int, int, int]] = []
    if mode == "golden":
        core = Core()
        try:
            core.load_elf(built.elf)
            gold = [(r.pc, r.inst, r.rd, r.wdata) for r in core.run()]
        except CoreFault as exc:
            return False, f"黄金模型执行失败：{exc}", 0, 0

    try:
        extra = {"ENTRY": built.entry, "LATENCY": latency}
        if WAVES:
            wave_dir = os.path.join(WORK, "waves")
            os.makedirs(wave_dir, exist_ok=True)
            extra["WAVES"] = 1
            extra["VCD"] = os.path.join(wave_dir, f"{os.path.splitext(name)[0]}_lat{latency}.vcd")
        sim = run_rtl.run_sim(vvp, build_dir, built.program_hex, built.data_hex,
                              name=f"{os.path.splitext(name)[0]}_lat{latency}",
                              plusargs=extra,
                              max_cycles=200_000)
    except run_rtl.RtlError as exc:
        return False, str(exc), 0, len(gold)

    problems = boot_flow_problems(sim.log, built.entry, mode, need_rd)
    if problems:
        msg = "\n".join("  " + p for p in problems)
        msg += "\n" + autopsy(name, latency, sim.log)
        return False, msg, sim.cycles, len(gold)

    if sim.timeout:
        msg = "RTL 超时：核心没有停机（检查 STATUS 与 5 步启动顺序）。"
        msg += "\n" + autopsy(name, latency, sim.log)
        return False, msg, sim.cycles, len(gold)

    if mode == "golden":
        if not sim.halted:
            return False, "RTL 没有报告停机。", 0, len(gold)
        if not sim.trace:
            return False, "trace 是空的：核心一条指令都没有执行。", sim.cycles, len(gold)
        if sim.trace[0][0] != built.entry:
            return False, (f"trace 第一条的 pc 是 0x{sim.trace[0][0]:08x}，"
                           f"而 PC_START 写的是 0x{built.entry:08x}——核心没有从 PC_START 启动。"), \
                sim.cycles, len(gold)

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

        if core is not None and core.dump_dtcm_words() != sim.dmem:
            g = core.dump_dtcm_words()
            bad = [i for i in range(min(len(g), len(sim.dmem))) if g[i] != sim.dmem[i]]
            lines = [f"trace 一致，但 DTCM 有 {len(bad)} 个字不同（前几处）："]
            for i in bad[:4]:
                lines.append(f"  0x{0x10000 + i*4:05x}: 期望 0x{g[i]:08x}  实际 0x{sim.dmem[i]:08x}")
            lines.append("  提示：经过 AXI 主接口的 store 丢数据了（检查 AW/W/B 握手与 WSTRB 掩码）。")
            return False, "\n".join(lines), sim.cycles, len(gold)
    else:
        # fault 用例：核心停住了，DTCM 里应该有故障前的"证据"
        if sim.dmem and sim.dmem[0] != 0x1BADB002:
            return False, (f"DTCM[0] = 0x{sim.dmem[0]:08x}，期望 0x1badb002："
                           "故障前的 store 没有经 m_axi 写进存储器。"), sim.cycles, 0

    return True, "", sim.cycles, len(gold)


def resolve(path: str) -> str:
    for base in (os.getcwd(), ROOT, LESSON):
        candidate = os.path.normpath(os.path.join(base, path))
        if os.path.exists(candidate):
            return candidate
    return os.path.normpath(os.path.join(os.getcwd(), path))


def collect_sources(axi_file: str, shell_file: str) -> list[str]:
    def modules_of(path: str) -> set[str]:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return set()
        return set(re.findall(r"\bmodule\s+(\w+)", text))

    l03b = os.path.join(LEARN, "lessons", "L03b_mdu_csr", "refs")
    l02 = os.path.join(LEARN, "lessons", "L02_lsu", "rtl")
    l00 = os.path.join(LEARN, "lessons", "L00_setup", "rtl", "alu32.sv")
    sources = [
        os.path.join(HERE, "tb_axi.sv"),
        os.path.join(HERE, "core_l04.sv"),
        os.path.join(HERE, "tcm.sv"),
        axi_file, shell_file,
        # 核心内部用课程提供的参考实现（L04 只考核 AXI 外壳与启动流程）
        os.path.join(l03b, "mdu.sv"),
        os.path.join(l03b, "csr_file.sv"),
        os.path.join(l02, "lsu.sv"),
        l00,
    ]
    seen: set[str] = set()
    out: list[str] = []
    for path in sources:
        mods = modules_of(path)
        if mods & seen:
            continue
        seen |= mods
        out.append(path)
    return [p for p in out if os.path.exists(p)]


def main() -> int:
    ap = argparse.ArgumentParser(description="L04 检查器（AXI 外壳 / 控制寄存器 / 启动流程）")
    ap.add_argument("--ref", action="store_true", help="用参考实现检查")
    ap.add_argument("--axi", default=None, help="指定你的 axi_lite_slave.sv")
    ap.add_argument("--shell", default=None, help="指定你的 axi_boot_shell.sv")
    ap.add_argument("--only", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--waves", action="store_true", help="转储 VCD 波形（配合 ./learn wave）")
    args = ap.parse_args()
    global WAVES
    WAVES = args.waves
    colorize = not args.no_color and sys.stdout.isatty()

    if args.list:
        for name, _, _, mode, _, need_rd in programs():
            print(f"{name}   ({mode}{'，含 load' if need_rd else ''})")
        return 0

    rtl_dir = os.path.join(LESSON, "refs" if args.ref else "rtl")
    axi_file = resolve(args.axi) if args.axi else os.path.join(rtl_dir, "axi_lite_slave.sv")
    shell_file = resolve(args.shell) if args.shell else os.path.join(rtl_dir, "axi_boot_shell.sv")
    for path, what in ((axi_file, "axi_lite_slave.sv"), (shell_file, "axi_boot_shell.sv")):
        if not os.path.exists(path):
            print(f"找不到 {what}：{path}")
            return 2
    if not run_rtl.have_iverilog():
        print("找不到 iverilog，请运行 ./learn doctor --install")
        return 2

    os.makedirs(WORK, exist_ok=True)
    vvp = os.path.join(WORK, "sim.vvp")
    sources = collect_sources(axi_file, shell_file)
    print("编译源文件：" + "、".join(os.path.relpath(p, ROOT) for p in sources))
    print("")
    try:
        run_rtl.compile_rtl(sources, vvp, top="tb_axi")
    except run_rtl.RtlError as exc:
        print(color("RTL 编译失败", RED, colorize))
        print(exc)
        return 1

    cases = [(n, p, m, mode, lk, nr) for n, p, m, mode, lk, nr in programs()
             if not args.only or args.only in n]
    if not cases:
        print("没有匹配的用例")
        return 2

    label = "参考实现" if args.ref else "你的实现"
    print(f"L04 检查（{label}）：{os.path.relpath(axi_file, ROOT)} + {os.path.relpath(shell_file, ROOT)}")
    print("")
    passed = 0
    total = 0
    for name, path, march, mode, linker, need_rd in cases:
        results = []
        for latency in LATENCIES:
            ok, msg, cycles, ninst = run_case(name, path, march, mode, linker, need_rd, vvp, latency)
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
    print(color(f"{passed}/{total} 次运行通过（每个程序跑 {len(LATENCIES)} 种总线延迟）",
                GREEN if passed == total else RED, colorize))
    if not args.ref and not args.only and not args.axi and not args.shell:
        record_progress(passed, total)
    if passed != total:
        print("提示：./learn hint L04 可以按顺序拿到分级提示。")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

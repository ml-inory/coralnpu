#!/usr/bin/env python3
"""P0 预备课检查器：五个模块逐一验收。

  A 命令行：把命令输出存成文件（检查文件内容）
  B 编译流程：编译 C 程序，从 ELF 里找出符号地址与一条指令的机器码
  C 数字逻辑：多数表决器（组合逻辑）与随机向量对拍
  D Verilog：4 选 1 多路选择器 + 带复位/使能的计数器
  E 指令执行：手工填出 addi 的机器码与字段，与 GNU 汇编器对照
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LESSON = os.path.dirname(HERE)
LEARN = os.path.dirname(os.path.dirname(LESSON))
ROOT = os.path.dirname(LEARN)
sys.path.insert(0, LEARN)

from golden.elf import load_elf, parse_symbols  # noqa: E402
from tools import build_program, run_rtl  # noqa: E402

WORK = os.path.join(LEARN, "work", "P0")
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
    data["P0"] = {"passed": passed, "total": total,
                  "when": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    return open(path, encoding="utf-8").read()


def as_int(text: str) -> int | None:
    text = text.strip().replace("_", "")
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        return None


# ---------------------------------------------------------------- 模块 A
def check_a() -> tuple[bool, str]:
    path = os.path.join(WORK, "A_terminal.txt")
    text = read_text(path)
    if not text:
        return False, (
            f"找不到 {os.path.relpath(path, ROOT)}\n"
            "把《作业说明》模块 A 里的四条命令原样跑一遍即可。"
        )
    problems = []
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if not first.endswith("coralnpu"):
        problems.append(f"第一行应该是仓库根目录（以 coralnpu 结尾），实际是：{first}")
    if "hello-from-file" not in text:
        problems.append("缺少 `echo` 追加进去的那一行 hello-from-file")
    if "P0_prep" not in text or "L00_setup" not in text:
        problems.append("缺少 `ls course/lessons` 的输出（应能看到 P0_prep 与 L00_setup）")
    if "exit=1" not in text:
        problems.append("缺少 `false` 之后的 exit=1（用来体验退出码）")
    if problems:
        return False, "\n".join(problems)
    return True, "四条命令的输出都记录正确（含退出码）"


# ---------------------------------------------------------------- 模块 B
def build_hello() -> tuple[str, dict]:
    src = os.path.join(LEARN, "lessons", "L00_setup", "tests", "programs", "hello.c")
    out = os.path.join(WORK, "hello_checker")
    built = build_program.build(src, out)
    with open(built.elf, "rb") as f:
        blob = f.read()
    return built.elf, {"symbols": parse_symbols(blob), "blob": blob}


def first_sw_machine_code(elf: str) -> int | None:
    objdump = "riscv64-unknown-elf-objdump"
    proc = subprocess.run([objdump, "-d", elf], capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*[0-9a-f]+:\s+([0-9a-f]{8})\s+sw\s", line)
        if m:
            return int(m.group(1), 16)
    return None


def check_b() -> tuple[bool, str]:
    path = os.path.join(WORK, "B_notes.txt")
    text = read_text(path)
    if not text:
        return False, (
            f"找不到 {os.path.relpath(path, ROOT)}\n"
            "按《作业说明》模块 B 生成 hello.elf，再把三个值写进 B_notes.txt。"
        )
    try:
        elf, info = build_hello()
    except SystemExit as exc:
        return False, f"编译 hello.c 失败：{exc}"
    symbols = info["symbols"]
    expect = {
        "main": symbols.get("main"),
        "answer": symbols.get("answer"),
        "first_sw": first_sw_machine_code(elf),
    }
    got = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", line)
        if m:
            got[m.group(1)] = as_int(m.group(2))
    problems = []
    for key, want in expect.items():
        if want is None:
            problems.append(f"课程这边没能从 ELF 里取到 {key}")
            continue
        if key not in got:
            problems.append(f"B_notes.txt 里缺少 {key}=")
            continue
        if got[key] != want:
            problems.append(f"{key} 不对：你写的是 0x{got[key]:08x}，ELF 里实际是 0x{want:08x}")
    if problems:
        return False, "\n".join(problems)
    return True, f"main=0x{expect['main']:08x} answer=0x{expect['answer']:08x} first_sw=0x{expect['first_sw']:08x}"


# ------------------------------------------------------- 模块 C / D：RTL
def rtl_path(use_ref: bool, name: str) -> str:
    return os.path.join(LESSON, "refs" if use_ref else "rtl", name)


def check_majority(use_ref: bool) -> tuple[bool, str]:
    rtl = rtl_path(use_ref, "majority.sv")
    if not os.path.exists(rtl):
        return False, f"找不到 {os.path.relpath(rtl, ROOT)}"
    os.makedirs(WORK, exist_ok=True)
    vectors = os.path.join(WORK, "majority_vectors.txt")
    results = os.path.join(WORK, "majority_results.txt")
    vvp = os.path.join(WORK, "majority.vvp")

    rng = random.Random(7)
    cases = [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    cases += [(rng.randrange(2), rng.randrange(2), rng.randrange(2)) for _ in range(32)]
    with open(vectors, "w", encoding="utf-8") as f:
        for a, b, c in cases:
            f.write(f"{a} {b} {c}\n")

    try:
        run_rtl.compile_rtl([os.path.join(HERE, "tb_majority.sv"), rtl], vvp, top="tb_majority")
    except run_rtl.RtlError as exc:
        return False, f"iverilog 编译失败：\n{exc}"
    subprocess.run(["vvp", vvp, f"+VECTORS={vectors}", f"+RESULTS={results}"],
                   capture_output=True, text=True, cwd=WORK)
    if not os.path.exists(results):
        return False, "仿真没有产生结果（检查 assign 是否给 y 赋值了）"
    got = [l.strip() for l in open(results, encoding="utf-8") if l.strip()]
    if len(got) != len(cases):
        return False, f"结果行数不对：期望 {len(cases)}，实际 {len(got)}"
    for i, ((a, b, c), y) in enumerate(zip(cases, got)):
        want = "1" if a + b + c >= 2 else "0"
        if y.strip()[-1] != want:
            return False, (
                f"第 {i+1} 组输入不一致：a={a} b={b} c={c} 期望 y={want}，你的输出是 {y}\n"
                "提示：y = (a&b) | (b&c) | (a&c)"
            )
    return True, f"{len(cases)} 组向量全部一致"


def check_mux4(use_ref: bool) -> tuple[bool, str]:
    rtl = rtl_path(use_ref, "mux4.sv")
    if not os.path.exists(rtl):
        return False, f"找不到 {os.path.relpath(rtl, ROOT)}"
    results = os.path.join(WORK, "mux4_results.txt")
    vvp = os.path.join(WORK, "mux4.vvp")
    try:
        run_rtl.compile_rtl([os.path.join(HERE, "tb_mux4.sv"), rtl], vvp, top="tb_mux4")
    except run_rtl.RtlError as exc:
        return False, f"iverilog 编译失败：\n{exc}"
    subprocess.run(["vvp", vvp, f"+RESULTS={results}"], capture_output=True, text=True, cwd=WORK)
    got = [l.strip() for l in open(results, encoding="utf-8") if l.strip()] if os.path.exists(results) else []
    want = ["00000011", "00000022", "00000044", "00000088"]
    if len(got) != 4:
        return False, f"结果行数不对：期望 4 行，实际 {len(got)}"
    for i, (g, w) in enumerate(zip(got, want)):
        if g[-8:] != w:
            return False, (
                f"sel={i} 时输出不对：期望 0x{w}，你的输出是 0x{g}\n"
                "提示：case(sel) 里四个分支分别选 d0..d3，别漏 default"
            )
    return True, "sel=0..3 全部选择正确"


def check_counter(use_ref: bool) -> tuple[bool, str]:
    rtl = rtl_path(use_ref, "counter.sv")
    if not os.path.exists(rtl):
        return False, f"找不到 {os.path.relpath(rtl, ROOT)}"
    results = os.path.join(WORK, "counter_results.txt")
    vvp = os.path.join(WORK, "counter.vvp")
    try:
        run_rtl.compile_rtl([os.path.join(HERE, "tb_counter.sv"), rtl], vvp, top="tb_counter")
    except run_rtl.RtlError as exc:
        return False, f"iverilog 编译失败：\n{exc}"
    subprocess.run(["vvp", vvp, f"+RESULTS={results}"], capture_output=True, text=True, cwd=WORK)
    got = [l.strip() for l in open(results, encoding="utf-8") if l.strip()] if os.path.exists(results) else []
    want = [0] + list(range(1, 11)) + [10] * 4
    if len(got) != len(want):
        return False, f"采样行数不对：期望 {len(want)}，实际 {len(got)}（是不是没有跑完 $finish？）"
    for i, (g, w) in enumerate(zip(got, want)):
        if int(g[-2:], 16) != w:
            first_cycle = "复位后" if i == 0 else f"第 {i} 个使能周期"
            return False, (
                f"{first_cycle} 的 q 不对：期望 {w}，你的输出是 {int(g[-2:], 16)}\n"
                "提示：if (rst) q<=0; else if (en) q<=q+1;  另外确认复位优先"
            )
    return True, "复位、10 次计数、保持都正确"


# ---------------------------------------------------------------- 模块 E
def assemble_one(text: str) -> int | None:
    asm = "riscv64-unknown-elf-as"
    objdump = "riscv64-unknown-elf-objdump"
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(WORK, "e_case.S")
    obj = os.path.join(WORK, "e_case.o")
    with open(src, "w", encoding="utf-8") as f:
        f.write(f"  .text\n  {text}\n")
    if subprocess.run([asm, "-march=rv32i", "-mabi=ilp32", "-o", obj, src],
                      capture_output=True, text=True).returncode != 0:
        return None
    out = subprocess.run([objdump, "-d", obj], capture_output=True, text=True).stdout
    m = re.search(r"\s[0-9a-f]+:\s+([0-9a-f]{8})\s", out)
    return int(m.group(1), 16) if m else None


ABI = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1", "a0", "a1",
       "a2", "a3", "a4", "a5", "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
       "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"]


def parse_reg(value: str) -> int | None:
    value = value.strip().lower()
    if value in ABI:
        return ABI.index(value)
    m = re.fullmatch(r"x?(\d+)", value)
    return int(m.group(1)) if m else None


def check_e() -> tuple[bool, str]:
    path = os.path.join(WORK, "E_journey.txt")
    text = read_text(path)
    if not text:
        return False, (
            f"找不到 {os.path.relpath(path, ROOT)}\n"
            "按《作业说明》模块 E：先用 objdump 看 addi a0, a1, -7 的机器码，再填四行。"
        )
    want_code = assemble_one("addi a0, a1, -7")
    got: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\w+)\s*=\s*(.+)", line)
        if m:
            got[m.group(1)] = m.group(2).strip()
    problems = []
    if "machine" not in got or as_int(got["machine"]) is None:
        problems.append("缺少 machine=0x........（机器码）")
    elif want_code is not None and as_int(got["machine"]) != want_code:
        problems.append(f"machine 不对：你写的是 {got['machine']}，GNU as 编出来是 0x{want_code:08x}")
    if parse_reg(got.get("rd", "")) != 10:
        problems.append("rd 应该是 a0（也就是 x10）")
    if parse_reg(got.get("rs1", "")) != 11:
        problems.append("rs1 应该是 a1（也就是 x11）")
    if as_int(got.get("imm", "")) != -7:
        problems.append("imm 应该是 -7（立即数有符号）")
    if problems:
        return False, "\n".join(problems)
    return True, f"machine=0x{want_code:08x}，rd/rs1/imm 都正确"


def main() -> int:
    ap = argparse.ArgumentParser(description="P0 预备课检查器")
    ap.add_argument("--ref", action="store_true", help="用参考实现跑 RTL 部分")
    ap.add_argument("--only", nargs="*", default=None, help="a / b / c / d / e")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    colorize = not args.no_color and sys.stdout.isatty()

    tasks = [
        ("a", "模块A 命令行", check_a),
        ("b", "模块B 编译流程", check_b),
        ("c", "模块C 组合逻辑（多数表决器）", lambda: check_majority(args.ref)),
        ("d", "模块D Verilog（mux4 + counter）", lambda: check_d_and_print(args.ref)),
        ("e", "模块E 指令执行", check_e),
    ]
    if args.only:
        tasks = [t for t in tasks if t[0] in args.only]
    if not tasks:
        print("没有匹配的模块")
        return 2

    print("P0 预备课检查")
    print("")
    passed = 0
    for key, title, fn in tasks:
        ok, msg = fn()
        tag = color("通过", GREEN, colorize) if ok else color("失败", RED, colorize)
        print(f"[{tag}] {title}")
        if msg:
            for line in msg.splitlines():
                print("       " + line)
        passed += 1 if ok else 0
    print("")
    total = len(tasks)
    print(color(f"{passed}/{total} 个模块通过", GREEN if passed == total else RED, colorize))
    if not args.ref and not args.only:
        record_progress(passed, total)
    return 0 if passed == total else 1


def check_d_and_print(use_ref: bool) -> tuple[bool, str]:
    ok_mux, msg_mux = check_mux4(use_ref)
    if not ok_mux:
        return False, "mux4：\n" + msg_mux
    ok_cnt, msg_cnt = check_counter(use_ref)
    if not ok_cnt:
        return False, "counter：\n" + msg_cnt
    return True, f"mux4：{msg_mux}；counter：{msg_cnt}"


if __name__ == "__main__":
    raise SystemExit(main())

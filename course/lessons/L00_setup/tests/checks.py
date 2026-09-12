#!/usr/bin/env python3
"""L00 检查器：环境、仓库地图、第一段 RTL、第一次端到端跑通。

四道作业分别对应：
  1. 环境自检（./learn doctor 全绿）
  2. 仓库地图问答（answers.md）
  3. alu32.sv：随机向量 + 边界向量对拍
  4. 用真实交叉编译器编译 C 程序，在黄金模型上跑通并读回内存
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LESSON = os.path.dirname(HERE)
LEARN = os.path.dirname(os.path.dirname(LESSON))
sys.path.insert(0, LEARN)

from golden.rv32i import Core, CoreFault  # noqa: E402
from tools import build_program, doctor as doctor_mod, run_rtl  # noqa: E402

WORK = os.path.join(LEARN, "work", "L00")
GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


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
    data["L00"] = {
        "passed": passed,
        "total": total,
        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


# --------------------------------------------------------------------- 作业 1
def check_env() -> tuple[bool, str]:
    rows, ok = doctor_mod.check()
    bad = [f"{name}（{detail}）" for status, name, detail in rows if status == "\u274c"]
    if ok:
        return True, "工具链齐全"
    return False, "缺少必需组件：\n" + "\n".join(bad) + "\n运行 ./learn doctor --install 安装。"


# --------------------------------------------------------------------- 作业 2
QUIZ = [
    ("Q1", "三档核心的 Bazel 目标名",
     [r"core_mini_axi", r"rvv_core_mini_axi", r"vme_core_mini_axi"],
     "看 hdl/chisel/src/coralnpu/BUILD，三档分别叫 core_mini_axi / rvv_core_mini_axi / vme_core_mini_axi。"),
    ("Q2", "ITCM/DTCM 地址与大小",
     [r"0x0*0*0*0*\b|0x0\b|0x00000000", r"8\s*(kb|k|KB)", r"0x0*1_?0000", r"32\s*(kb|k|KB)"],
     "ITCM 从 0x00000000 起 8 KB，DTCM 从 0x00010000 起 32 KB（doc/integration_guide.md）。"),
    ("Q3", "停机指令",
     [r"mpause", r"0x0*800_?0073"],
     "上游用 mpause 停机，机器码 0x08000073（Decode.scala:1188、coralnpu_start.S:144）。"),
    ("Q4", "向量后端源码目录",
     [r"hdl/verilog/rvv"],
     "向量后端的 SystemVerilog 在 hdl/verilog/rvv/。"),
    ("Q5", "最小 cocotb 测试命令",
     [r"bazel\s+run\s+//tests/cocotb:core_mini_axi_sim_cocotb"],
     "README.md 的 Quick Start：bazel run //tests/cocotb:core_mini_axi_sim_cocotb。"),
]


def check_quiz() -> tuple[bool, str]:
    path = os.path.join(LESSON, "answers.md")
    if not os.path.exists(path):
        return False, "找不到 answers.md（本应在 course/lessons/L00_setup/answers.md）"
    text = open(path, encoding="utf-8").read()
    answers = {}
    for line in text.splitlines():
        m = re.match(r"\s*-\s*(Q\d)\s*[:：]\s*(.*)$", line)
        if m:
            answers[m.group(1)] = m.group(2).strip()
    problems = []
    for qid, title, patterns, hint in QUIZ:
        ans = answers.get(qid, "")
        if not ans or ans.upper().startswith("TODO"):
            problems.append(f"{qid}（{title}）还没作答")
            continue
        missing = [p for p in patterns if not re.search(p, ans, re.IGNORECASE)]
        if missing:
            problems.append(f"{qid}（{title}）答案不完整，参考：{hint}")
    if problems:
        return False, "\n".join(problems)
    return True, "5 个问题全部正确"


# --------------------------------------------------------------------- 作业 3
def alu_golden(a: int, b: int, op: int) -> tuple[int, int]:
    m = 0xFFFF_FFFF
    sh = b & 0x1F
    sgn = lambda v: v - (1 << 32) if v & 0x8000_0000 else v  # noqa: E731
    if op == 0:
        y = (a + b) & m
    elif op == 1:
        y = (a - b) & m
    elif op == 2:
        y = (a << sh) & m
    elif op == 3:
        y = 1 if sgn(a) < sgn(b) else 0
    elif op == 4:
        y = 1 if a < b else 0
    elif op == 5:
        y = a ^ b
    elif op == 6:
        y = a >> sh
    elif op == 7:
        y = (sgn(a) >> sh) & m
    elif op == 8:
        y = a | b
    else:
        y = a & b
    return y, 1 if y == 0 else 0


def make_vectors() -> list[tuple[int, int, int]]:
    rng = random.Random(42)
    vec = []
    # 边界向量：0、1、-1、符号位、移位边界
    edges = [0x0000_0000, 0x0000_0001, 0xFFFF_FFFF, 0x8000_0000, 0x7FFF_FFFF, 0x0000_001F]
    for a in edges:
        for b in edges:
            for op in range(10):
                vec.append((a, b, op))
    for _ in range(2000):
        vec.append((rng.getrandbits(32), rng.getrandbits(32), rng.randrange(10)))
    return vec


def check_alu(use_ref: bool) -> tuple[bool, str]:
    rtl = os.path.join(LESSON, "refs" if use_ref else "rtl", "alu32.sv")
    if not os.path.exists(rtl):
        return False, f"找不到 {rtl}"
    os.makedirs(WORK, exist_ok=True)
    vectors = os.path.join(WORK, "alu_vectors.txt")
    results = os.path.join(WORK, "alu_results.txt")
    vvp = os.path.join(WORK, "alu.vvp")
    vectors_list = make_vectors()
    with open(vectors, "w", encoding="utf-8") as f:
        for a, b, op in vectors_list:
            f.write(f"{a:08x} {b:08x} {op:x}\n")
    try:
        run_rtl.compile_rtl([os.path.join(HERE, "tb_alu32.sv"), rtl], vvp, top="tb_alu32")
    except run_rtl.RtlError as exc:
        return False, f"iverilog 编译失败：\n{exc}"
    import subprocess
    proc = subprocess.run(
        ["vvp", vvp, f"+VECTORS={vectors}", f"+RESULTS={results}"],
        capture_output=True, text=True, cwd=WORK,
    )
    if not os.path.exists(results):
        return False, "仿真没有产生结果文件：\n" + (proc.stdout + proc.stderr)[-800:]
    got = [line.split() for line in open(results, encoding="utf-8") if line.strip()]
    if len(got) != len(vectors_list):
        return False, f"结果行数不对：期望 {len(vectors_list)}，实际 {len(got)}"
    for i, ((a, b, op), row) in enumerate(zip(vectors_list, got)):
        y_exp, z_exp = alu_golden(a, b, op)
        try:
            y_got = int(row[0], 16)
            z_got = int(row[1], 16)
        except (ValueError, IndexError):
            return False, f"第 {i+1} 行结果无法解析：{row}（X/Z 值通常是组合逻辑没有覆盖全分支）"
        if y_exp != y_got:
            names = ["ADD", "SUB", "SLL", "SLT", "SLTU", "XOR", "SRL", "SRA", "OR", "AND"]
            hint = "检查移位量是否只取低 5 位" if op in (2, 6, 7) else "检查这个操作码的分支"
            if op == 7:
                hint = "SRA 要用符号填充，试试 (a >> shamt) | ({32{a[31]}} & ~(32'hFFFFFFFF >> shamt))"
            if op in (3, 4):
                hint = "SLT 用 $signed 比较，SLTU 用无符号比较"
            return False, (
                f"第 {i+1} 组向量不一致：a=0x{a:08x} b=0x{b:08x} op={op}({names[op]})\n"
                f"期望 y=0x{y_exp:08x}，实际 y=0x{y_got:08x}；{hint}"
            )
        if z_exp != z_got:
            return False, f"第 {i+1} 组向量 zero 标志不对：期望 {z_exp}，实际 {z_got}"
    return True, f"{len(vectors_list)} 组向量全部一致"


# --------------------------------------------------------------------- 作业 4
def check_toolchain(use_ref: bool) -> tuple[bool, str]:
    src = os.path.join(HERE, "programs", "hello.c")
    build_dir = os.path.join(WORK, "hello")
    try:
        built = build_program.build(src, build_dir)
    except SystemExit as exc:
        return False, f"编译失败：{exc}"
    core = Core()
    try:
        core.load_elf(built.elf)
        core.run(max_steps=200_000)
    except CoreFault as exc:
        return False, f"黄金模型执行失败：{exc}"
    symbols = built.symbols
    for name, expect in (("answer", 45), ("steps", 9)):
        addr = symbols.get(name)
        if addr is None:
            return False, f"符号表里找不到 {name}"
        off = addr - 0x10000
        if not 0 <= off < len(core.dtcm):
            return False, f"{name} 的地址 0x{addr:08x} 不在 DTCM 里"
        value = int.from_bytes(core.dtcm[off : off + 4], "little")
        if value != expect:
            return False, f"{name} 期望 {expect}，实际 {value}"
    return True, f"answer=45 steps=9，共 {len(core.dtcm) // 4} 个 DTCM 字已核对"


def main() -> int:
    ap = argparse.ArgumentParser(description="L00 检查器")
    ap.add_argument("--ref", action="store_true", help="用参考实现跑 RTL 部分")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--only", nargs="*", default=None,
                    help="只跑指定作业：env / quiz / alu / toolchain")
    args = ap.parse_args()
    colorize = not args.no_color and sys.stdout.isatty()

    all_tasks = [
        ("env", "作业1 环境自检", lambda: check_env()),
        ("quiz", "作业2 仓库地图", lambda: check_quiz()),
        ("alu", "作业3 alu32.sv", lambda: check_alu(args.ref)),
        ("toolchain", "作业4 端到端跑通", lambda: check_toolchain(args.ref)),
    ]
    if args.only:
        tasks = [(t, fn) for key, t, fn in all_tasks if key in args.only]
    else:
        tasks = [(t, fn) for _, t, fn in all_tasks]
    if not tasks:
        print("没有匹配的作业")
        return 2
    print("L00 检查")
    print("")
    passed = 0
    for title, fn in tasks:
        ok, msg = fn()
        tag = color("通过", GREEN, colorize) if ok else color("失败", RED, colorize)
        print(f"[{tag}] {title}")
        if msg:
            for line in msg.splitlines():
                print("       " + line)
        passed += 1 if ok else 0
    print("")
    total = len(tasks)
    print(color(f"{passed}/{total} 个作业通过", GREEN if passed == total else RED, colorize))
    # --only 是局部排查，不写进度；--ref 是课程自检，不写进度
    if not args.ref and not args.only:
        record_progress(passed, total)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

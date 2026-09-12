#!/usr/bin/env python3
"""前置知识诊断：把「我好像跟不上」变成「我缺的是第 3 层」。

25 道题分五层，每层 5 道。答完会告诉你：
  * 哪一层可以直接跳过；
  * 哪一层需要补，以及去 P0 预备课的哪一节、做哪个模块。

用法：
  ./learn diag                      # 交互式答题
  ./learn diag --answers b,c,a,...  # 一次性给答案
  ./learn diag --list               # 只看题目与答案
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)

GREEN, RED, YELLOW, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


@dataclass
class Question:
    layer: str
    text: str
    options: list[str]
    answer: int
    why: str


LAYERS = {
    "A": ("命令行与文件系统", "basics.md 第 1 章", "模块 A"),
    "B": ("C 与编译流程", "basics.md 第 2 章", "模块 B"),
    "C": ("数字逻辑", "basics.md 第 3 章", "模块 C"),
    "D": ("Verilog 语法", "basics.md 第 4 章", "模块 D"),
    "E": ("RISC-V 与指令执行", "basics.md 第 5 章", "模块 E"),
}

QUESTIONS = [
    # ---------------------------------------------------------- A 命令行
    Question("A", "想把一条命令的输出保存进文件，用哪个符号？",
             [">", "|", "&", "#"], 0, "`cmd > file` 重定向标准输出；`>>` 是追加；`|` 是管道。"),
    Question("A", "命令执行后 `echo $?` 打印 0，通常意味着什么？",
             ["命令不存在", "执行成功", "输出为空", "需要管理员权限"], 1,
             "退出码 0 表示成功，非 0 表示出错——脚本和 CI 就是靠它判断的。"),
    Question("A", "路径 `./foo/bar.sv` 里的 `.` 指的是？",
             ["根目录", "上一级目录", "当前目录", "用户主目录"], 2,
             "`.` 是当前目录，`..` 是上一级。"),
    Question("A", "环境变量 PATH 的作用是？",
             ["保存当前目录", "决定敲命令时去哪些目录找可执行文件",
              "记录历史命令", "设置文件权限"], 1,
             "所以「命令找不到」通常是 PATH 问题，而不是命令没装。"),
    Question("A", "管道 `|` 做什么？",
             ["把文件的权限复制给另一个文件", "把前一条命令的输出接到后一条命令的输入",
              "同时运行两条命令", "记录命令日志"], 1,
             "例：`objdump -d a.elf | head -20` 只看前 20 行。"),

    # ---------------------------------------------------------- B C/编译
    Question("B", "把 C 源文件编译成目标文件（.o）用哪个选项？",
             ["-o", "-c", "-E", "-S"], 1, "`-c` 只编译不链接；`-o` 是指定输出文件名。"),
    Question("B", "链接器（linker）主要做什么？",
             ["把 C 翻译成汇编", "把多个 .o 与库合并、并解析符号地址",
              "检查代码风格", "优化运行速度"], 1,
             "所以「undefined reference」是链接错误，而不是编译错误。"),
    Question("B", "ELF 文件里的符号表（symbol table）主要用途是？",
             ["压缩文件体积", "记录「名字 → 地址」的对应关系",
              "存储源代码", "记录编译时间"], 1,
             "课程检查器就是靠它按变量名找到它在内存里的地址。"),
    Question("B", "函数调用时，局部变量一般放在哪里？",
             ["寄存器里，永不入内存", "栈上（stack）", "只读数据段", "堆上"], 1,
             "所以 `sp`（栈指针）在调用前后会变化——L01 的测试 4 就在验证这件事。"),
    Question("B", "嵌入式程序为什么常常需要自定义链接脚本和 `_start` 入口？",
             ["为了加密", "为了决定代码和数据分别放在哪段内存、以及从哪开始执行",
              "为了让程序体积更小", "为了兼容操作系统"], 1,
             "裸机没有操作系统，地址布局和入口都得自己定。"),

    # ---------------------------------------------------------- C 数字逻辑
    Question("C", "组合逻辑电路的输出来自？",
             ["上一次时钟边沿的输入", "当前输入，没有任何记忆", "复位时的默认值", "随机初始值"], 1,
             "组合逻辑 = 当前输入的函数；一旦引入记忆，就是时序逻辑。"),
    Question("C", "触发器的输出什么时候改变？",
             ["输入一变就变", "时钟的有效边沿（如上升沿）", "复位之后永不改变", "每半个周期"], 1,
             "这就是为什么 Verilog 里写 `always_ff @(posedge clk)`。"),
    Question("C", "复位（reset）在电路里的作用是？",
             ["加快时钟频率", "把电路置到确定的初始状态", "清除程序代码", "关闭电源"], 1,
             "没有复位，寄存器的初值是随机的 X，仿真结果不可复现。"),
    Question("C", "一个 4 选 1 的多路选择器需要几根选择线？",
             ["1 根", "2 根", "4 根", "8 根"], 1,
             "2 根选择线可以表示 4 种组合，这正是「位宽」的意义。"),
    Question("C", "为什么组合逻辑里「漏写一个分支的赋值」很危险？",
             ["会被综合成锁存器，产生意外的记忆和时序问题", "会让代码变长",
              "只会产生警告、无实际影响", "会让时钟停止"], 0,
             "所以课程要求每个 `always_comb` 都先给默认值。"),

    # ---------------------------------------------------------- D Verilog
    Question("D", "描述组合逻辑，下面哪个写法最合适？",
             ["always_ff @(posedge clk)", "assign 或 always_comb", "initial 块", "task"], 1,
             "组合逻辑用 `assign` / `always_comb`，时序逻辑用 `always_ff`。"),
    Question("D", "`logic [7:0] data;` 里 data 的位宽是？",
             ["1 位", "7 位", "8 位", "32 位"], 2,
             "`[7:0]` 表示 8 位，最高位是 7。"),
    Question("D", "阻塞赋值 `=` 与非阻塞赋值 `<=` 的区别是？",
             ["没有区别", "`=` 立即生效；`<=` 在时钟边沿统一更新，用于时序逻辑",
              "`<=` 用于比较大小", "`=` 只能用于整数"], 1,
             "组合逻辑用 `=`，时序逻辑用 `<=`，这是 Verilog 的第一条纪律。"),
    Question("D", "`a[3:0]` 表示取 a 的？",
             ["高 4 位", "低 4 位", "第 3 位", "全部位"], 1,
             "位选是硬件里最常见的操作：字节掩码、符号扩展都靠它。"),
    Question("D", "一个模块的端口方向可以是？",
             ["只有 input 和 output", "input、output、inout", "只有 wire 和 reg", "由时钟决定"], 1,
             "`inout` 用于双向总线；本课程主要用 input/output。"),

    # ---------------------------------------------------------- E RISC-V
    Question("E", "`addi a0, a1, -7` 里三个部分依次是？",
             ["目标寄存器、源寄存器、立即数", "源、目标、立即数",
              "立即数、源、目标", "函数名、参数、返回值"], 0,
             "RISC-V 汇编格式是 `指令 目标, 源, 立即数`。"),
    Question("E", "PC（程序计数器）保存的是什么？",
             ["上一条指令的结果", "当前或下一条要取指的地址", "栈顶地址", "中断向量"], 1,
             "取指、分支、跳转都是在改 PC，或根据 PC 计算。"),
    Question("E", "RV32I 中寄存器 x0 的值是？",
             ["可读写的临时寄存器", "恒为 0，写入被忽略", "栈指针", "返回地址"], 1,
             "x0（zero）恒为 0，这让很多指令可以少设计一个操作数通路。"),
    Question("E", "一条 32 位指令在内存里占几个字节？",
             ["1", "2", "4", "8"], 2,
             "所以取指地址按 4 递增，PC+4 就是下一条指令。"),
    Question("E", "「取指 → 译码 → 执行 → 写回」描述的是？",
             ["编译器的流程", "一条指令在处理器里被执行的基本流程",
              "链接器的工作", "操作系统的调度"], 1,
             "L01 要做的就是把这条流程用硬件实现出来。"),
]


def colorize() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if colorize() else text


def ask_interactive() -> list[int]:
    answers: list[int] = []
    for i, q in enumerate(QUESTIONS, 1):
        print("")
        print(c(f"[{i}/{len(QUESTIONS)}] {LAYERS[q.layer][0]}", BOLD))
        print(f"  {q.text}")
        for j, opt in enumerate(q.options):
            print(f"    {chr(ord('a') + j)}) {opt}")
        while True:
            raw = input("  你的答案（a/b/c/d，不确定就按回车跳过）：").strip().lower()
            if raw == "":
                answers.append(-1)
                break
            if raw[0] in "abcd":
                answers.append(ord(raw[0]) - ord("a"))
                break
            print("  请输入 a、b、c 或 d")
    return answers


def report(answers: list[int]) -> int:
    per_layer: dict[str, list[tuple[Question, int]]] = {k: [] for k in LAYERS}
    for q, a in zip(QUESTIONS, answers):
        per_layer[q.layer].append((q, a))

    print("")
    print(c("前置知识诊断结果", BOLD))
    print("")
    weak: list[str] = []
    for layer, (name, section, module) in LAYERS.items():
        items = per_layer[layer]
        wrong = [q for q, a in items if a != q.answer]
        total = len(items)
        correct = total - len(wrong)
        if correct >= total - 1:
            verdict = c("可以跳过", GREEN)
        else:
            verdict = c(f"建议先补（{len(wrong)}/{total} 题没答对）", YELLOW)
            weak.append(layer)
        print(f"  {layer} {name.ljust(14)} {correct}/{total}  {verdict}")
        if wrong and correct < total - 1:
            for q in wrong[:2]:
                print(f"      · {c(q.why, DIM)}")
    print("")
    if weak:
        modules = "、".join(LAYERS[l][2] for l in weak)
        sections = "、".join(LAYERS[l][1] for l in weak)
        print(f"建议：先上预备课 P0，做 {modules}（对应 {sections}）")
        print("命令：./learn start P0")
    else:
        print("你的前置知识够用，可以直接开始 L00：./learn start L00")
    if any(a == -1 for a in answers):
        print(c("（跳过的题按「不会」处理；补完之后可以再跑 ./learn diag）", DIM))

    state_dir = os.path.join(COURSE, ".state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "diagnose.json"), "w", encoding="utf-8") as f:
        json.dump({"weak_layers": weak}, f, indent=2, ensure_ascii=False)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="前置知识诊断（25 题，5 分钟）")
    ap.add_argument("--answers", help="逗号分隔的答案，例如 b,c,a,d,a...")
    ap.add_argument("--list", action="store_true", help="只列出题目与答案")
    args = ap.parse_args()

    if args.list:
        for i, q in enumerate(QUESTIONS, 1):
            print(f"{i:2d}. [{q.layer}] {q.text}")
            print(f"    答案：{chr(ord('a') + q.answer)}) {q.options[q.answer]}")
            print(f"    说明：{q.why}")
        return 0

    if args.answers:
        raw = [x.strip().lower() for x in args.answers.split(",") if x.strip()]
        answers = [(ord(x[0]) - ord("a")) if x and x[0] in "abcd" else -1 for x in raw]
        if len(answers) != len(QUESTIONS):
            print(f"需要 {len(QUESTIONS)} 个答案，收到 {len(answers)} 个。")
            return 2
        return report(answers)

    print("前置知识诊断：25 道题，大约 5 分钟。答不上来就按回车，不要猜。")
    return report(ask_interactive())


if __name__ == "__main__":
    raise SystemExit(main())

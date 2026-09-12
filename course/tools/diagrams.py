#!/usr/bin/env python3
"""生成课程用的矢量插图（SVG）。

为什么用脚本画图而不是让模型生图：数据通路、指令格式、内存映射这类图的
文字和箭头必须精确，脚本生成可以保证「图上的地址和代码里的地址一致」，
也方便以后改课程时一键重画。

用法：
  ./learn figs            # 重新生成所有插图
  python3 course/tools/diagrams.py --list
"""

from __future__ import annotations

import argparse
import os

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)

FONT = "'Noto Sans CJK SC','Noto Sans CJK JP',sans-serif"
MONO = "'Noto Sans Mono CJK SC','DejaVu Sans Mono',monospace"

INK = "#1f2933"
MUTED = "#5b6b7b"
BLUE = "#1d4ed8"
LBLUE = "#e8effd"
GREEN = "#0f766e"
LGREEN = "#e2f4f1"
AMBER = "#b45309"
LAMBER = "#fdf1df"
PURPLE = "#6d28d9"
LPURPLE = "#f0e9fe"
GREY = "#f3f5f7"
RED = "#b91c1c"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(x: float, y: float, content: str, size: int = 14, anchor: str = "start",
         bold: bool = False, fill: str = INK, mono: bool = False, line_h: float = 1.35) -> str:
    family = MONO if mono else FONT
    weight = "700" if bold else "400"
    lines = content.split("\n")
    spans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else size * line_h
        spans.append(
            f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>'
        )
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{"".join(spans)}</text>'
    )


def box(x: float, y: float, w: float, h: float, label: str, fill: str = "#ffffff",
        stroke: str = INK, radius: int = 8, size: int = 14, bold: bool = False,
        text_fill: str = INK, mono: bool = False) -> str:
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" ry="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
    )
    if label:
        lines = label.split("\n")
        total = (len(lines) - 1) * size * 1.35
        out += text(x + w / 2, y + h / 2 + size * 0.35 - total / 2, label, size=size,
                    anchor="middle", bold=bold, fill=text_fill, mono=mono)
    return out


def arrow(x1: float, y1: float, x2: float, y2: float, label: str = "",
          dashed: bool = False, color: str = INK, size: int = 12, curve: float = 0.0) -> str:
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    if curve:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - curve
        path = f"M {x1} {y1} Q {mx} {my} {x2} {y2}"
    else:
        path = f"M {x1} {y1} L {x2} {y2}"
    out = (
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8" '
        f'marker-end="url(#arrowhead)"{dash}/>'
    )
    if label:
        out += text((x1 + x2) / 2, (y1 + y2) / 2 - 6 - curve / 2, label, size=size,
                    anchor="middle", fill=MUTED)
    return out


def svg(width: int, height: int, body: str, caption: str = "") -> str:
    cap = ""
    if caption:
        cap = text(24, height - 14, caption, size=12, fill=MUTED)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'<defs><marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{INK}"/></marker></defs>\n'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>\n'
        f"{body}\n{cap}\n</svg>\n"
    )


# --------------------------------------------------------------------- 插图

def learning_loop() -> str:
    b = []
    steps = [
        ("1. 读规格", "接口表 / 时序图 / 状态机", LBLUE, BLUE),
        ("2. 写 RTL", "在骨架的 TODO 处实现", LGREEN, GREEN),
        ("3. 跑仿真", "./learn check，秒级反馈", LAMBER, AMBER),
        ("4. 对拍修复", "trace 第一条不一致就是线索", LPURPLE, PURPLE),
    ]
    x = 30
    for i, (title, sub, fill, stroke) in enumerate(steps):
        b.append(box(x, 60, 200, 96, "", fill=fill, stroke=stroke))
        b.append(text(x + 100, 92, title, size=16, anchor="middle", bold=True, fill=stroke))
        b.append(text(x + 100, 116, sub, size=12, anchor="middle", fill=MUTED))
        if i < len(steps) - 1:
            b.append(arrow(x + 204, 108, x + 246, 108))
        x += 250
    b.append(arrow(930, 168, 130, 168, curve=40, dashed=True, color=MUTED, label="每一轮都更快"))
    b.append(text(24, 36, "学习闭环：每一课都走完这四步", size=18, bold=True))
    return svg(1010, 210, "\n".join(b), "图 1  每节课的固定节奏；check 失败信息会告诉你卡在哪一步")


def repo_map() -> str:
    b = []
    b.append(text(24, 34, "CoralNPU 仓库地图（教学仓只增加 course/ 与 ./learn，不动上游）", size=17, bold=True))
    b.append(box(24, 56, 210, 250, "", fill=GREY, stroke=MUTED))
    b.append(text(129, 84, "上游硬件设计", size=15, anchor="middle", bold=True, fill=INK))
    for i, (name, note) in enumerate([
        ("hdl/chisel/", "标量核、总线、SoC（Scala 3.5 万行）"),
        ("hdl/verilog/rvv/", "向量后端与 Zvt（SV 7.4 万行）"),
        ("doc/", "数据手册式微架构文档"),
        ("tests/cocotb/", "cocotb 验证环境"),
        ("toolchain/", "交叉编译与链接脚本"),
    ]):
        y = 100 + i * 40
        b.append(box(38, y, 182, 34, "", fill="#ffffff", stroke=BLUE))
        b.append(text(46, y + 15, name, size=12.5, bold=True, mono=True, fill=BLUE))
        b.append(text(46, y + 28, note, size=10, fill=MUTED))
    b.append(box(258, 56, 250, 250, "", fill=LGREEN, stroke=GREEN))
    b.append(text(383, 84, "教学层（本课程新增）", size=15, anchor="middle", bold=True, fill=GREEN))
    for i, (name, note) in enumerate([
        ("./learn", "统一入口：doctor / check / hint / pdf"),
        ("course/golden/", "Python 黄金模型（RV32I 起步）"),
        ("course/lessons/L00…", "每课：教材 PDF + 骨架 + 检查器"),
        ("course/tools/", "编译、仿真、对拍、出图工具"),
        ("course/work/", "你的实现产物与仿真输出"),
    ]):
        y = 100 + i * 40
        b.append(box(272, y, 222, 34, "", fill="#ffffff", stroke=GREEN))
        b.append(text(280, y + 15, name, size=12.5, bold=True, mono=True, fill=GREEN))
        b.append(text(280, y + 28, note, size=10, fill=MUTED))
    b.append(arrow(236, 180, 256, 180, color=GREEN, label="对照"))
    b.append(box(532, 56, 240, 250, "", fill=LAMBER, stroke=AMBER))
    b.append(text(652, 84, "课程阶梯（三档硬件）", size=15, anchor="middle", bold=True, fill=AMBER))
    for i, (name, note) in enumerate([
        ("L00–L04", "标量核：RV32I → 流水 → AXI 外壳"),
        ("L05–L07", "算力：浮点 → RVV 向量 → Zvt 矩阵"),
        ("L08–L09", "SoC 外设、DMA、软件栈与模型"),
        ("L10", "验证方法学与毕业项目"),
        ("对照实现", "hdl/chisel/... 与 hdl/verilog/rvv/..."),
    ]):
        y = 100 + i * 40
        b.append(box(546, y, 212, 34, "", fill="#ffffff", stroke=AMBER))
        b.append(text(554, y + 15, name, size=12.5, bold=True, mono=True, fill=AMBER))
        b.append(text(554, y + 28, note, size=10, fill=MUTED))
    return svg(796, 330, "\n".join(b), "图 2  向上游学、在 course/ 里练：两边永远可对照")


def toolchain_flow() -> str:
    b = []
    b.append(text(24, 34, "从 C 代码到仿真结果：一条命令里的六个阶段", size=17, bold=True))
    stages = [
        ("hello.c", "C / 汇编源文件", LBLUE, BLUE),
        ("riscv64-gcc", "-march=rv32i -mabi=ilp32", LGREEN, GREEN),
        ("hello.elf", "ELF32 可执行文件", LAMBER, AMBER),
        ("program.hex", "ITCM 镜像 / data.hex", LPURPLE, PURPLE),
        ("黄金模型 + RTL", "iverilog 仿真", LBLUE, BLUE),
        ("compare", "trace 与 DTCM 全量对拍", LGREEN, GREEN),
    ]
    x = 24
    for i, (title, sub, fill, stroke) in enumerate(stages):
        b.append(box(x, 70, 140, 84, "", fill=fill, stroke=stroke))
        b.append(text(x + 70, 100, title, size=13.5, anchor="middle", bold=True, fill=stroke, mono=i != 4))
        b.append(text(x + 70, 124, sub, size=10, anchor="middle", fill=MUTED))
        if i < len(stages) - 1:
            b.append(arrow(x + 144, 112, x + 168, 112))
        x += 168
    b.append(text(24, 190, "对应命令：python3 course/tools/build_program.py hello.c --out-dir out/", size=12, mono=True, fill=MUTED))
    b.append(text(24, 210, "            ./learn check L01   （编译 → 仿真 → 对拍 全自动）", size=12, mono=True, fill=MUTED))
    return svg(1040, 232, "\n".join(b), "图 3  教学仓里的工具链是上游 toolchain/ 的精简版，地址映射保持一致")


def memory_map() -> str:
    b = []
    b.append(text(24, 34, "CoralNPU 内存映射（与上游默认配置一致）", size=17, bold=True))
    rows = [
        ("0x0000_0000", "ITCM  8 KB", "指令 + 只读数据；教学核里只允许读", LBLUE, BLUE),
        ("0x0001_0000", "DTCM 32 KB", "栈、全局变量；可读可写", LGREEN, GREEN),
        ("0x0003_0000", "CSR", "外部主机读写核的控制寄存器（L04 实现）", LAMBER, AMBER),
    ]
    y = 70
    for base, name, note, fill, stroke in rows:
        b.append(box(24, y, 150, 56, base, fill="#ffffff", stroke=stroke, mono=True, size=13))
        b.append(box(174, y, 180, 56, name, fill=fill, stroke=stroke, bold=True, size=14))
        b.append(text(366, y + 34, note, size=12, fill=MUTED))
        y += 72
    b.append(text(24, y + 26, "栈指针从 DTCM 顶部往下长：__stack_top = 0x0001_0000 + 32K - 16", size=12, mono=True, fill=MUTED))
    return svg(760, y + 56, "\n".join(b), "图 4  地址写错时会直接报「无设备响应」或「store 打到 ITCM」")


def rv32i_formats() -> str:
    b = []
    b.append(text(24, 34, "RV32I 六种指令格式：位域就是硬件的接线图", size=17, bold=True))
    fields = [
        ("R", [("funct7", 7), ("rs2", 5), ("rs1", 5), ("funct3", 3), ("rd", 5), ("opcode", 7)],
         "add/sub/and… 寄存器运算"),
        ("I", [("imm[11:0]", 12), ("rs1", 5), ("funct3", 3), ("rd", 5), ("opcode", 7)],
         "addi/lw/jalr… 立即数与载入"),
        ("S", [("imm[11:5]", 7), ("rs2", 5), ("rs1", 5), ("funct3", 3), ("imm[4:0]", 5), ("opcode", 7)],
         "sb/sh/sw 存储"),
        ("B", [("imm[12|10:5]", 7), ("rs2", 5), ("rs1", 5), ("funct3", 3), ("imm[4:1|11]", 5), ("opcode", 7)],
         "beq/bne/blt… 分支"),
        ("U", [("imm[31:12]", 20), ("rd", 5), ("opcode", 7)], "lui/auipc"),
        ("J", [("imm[20|10:1|11|19:12]", 20), ("rd", 5), ("opcode", 7)], "jal 跳转"),
    ]
    y = 66
    for name, parts, note in fields:
        b.append(text(24, y + 22, name, size=15, bold=True, fill=PURPLE))
        x = 52
        scale = 13.0
        for label, width in parts:
            w = width * scale
            fill = LBLUE if "opcode" not in label else LAMBER
            stroke = BLUE if "opcode" not in label else AMBER
            b.append(box(x, y, w, 32, "", fill=fill, stroke=stroke, radius=4))
            b.append(text(x + w / 2, y + 21, label, size=9.5, anchor="middle", mono=True, fill=stroke))
            x += w
        b.append(text(x + 12, y + 21, note, size=11, fill=MUTED))
        y += 46
    return svg(1090, y + 24, "\n".join(b), "图 5  立即数位域被打散是硬件布线决定的；写成拼接表达式时按图抄即可")


def single_cycle_datapath() -> str:
    b = []
    b.append(text(24, 32, "单周期数据通路：一个周期走完取指、译码、执行、访存、写回", size=17, bold=True))
    # PC
    b.append(box(30, 96, 90, 54, "PC", fill=LBLUE, stroke=BLUE, bold=True, size=16))
    # IMEM
    b.append(box(160, 96, 130, 54, "ITCM\n指令", fill=GREY, stroke=MUTED, size=13))
    # Decode
    b.append(box(330, 76, 150, 94, "译码\n立即数生成\n控制信号", fill=LPURPLE, stroke=PURPLE, size=12.5))
    # Regfile
    b.append(box(330, 210, 150, 80, "寄存器堆\nrs1 / rs2 / rd", fill=LGREEN, stroke=GREEN, size=12.5))
    # ALU
    b.append(box(530, 130, 130, 76, "ALU", fill=LAMBER, stroke=AMBER, bold=True, size=17))
    # DMEM
    b.append(box(710, 130, 140, 76, "DTCM\n数据", fill=GREY, stroke=MUTED, size=13))
    # Writeback
    b.append(box(530, 250, 320, 56, "写回：load 数据 / ALU 结果 → rd", fill=LBLUE, stroke=BLUE, size=13))
    b.append(arrow(122, 123, 156, 123))
    b.append(arrow(292, 123, 326, 123, label="inst"))
    b.append(arrow(405, 172, 405, 206))
    b.append(arrow(482, 240, 560, 200, curve=18, label="operands"))
    b.append(arrow(664, 168, 706, 168, label="addr/wdata"))
    b.append(arrow(710, 190, 664, 190, label="rdata", dashed=True))
    b.append(arrow(595, 208, 595, 246, label="result"))
    b.append(arrow(690, 250, 690, 208, dashed=True, color=BLUE, label="load"))
    b.append(arrow(530, 278, 180, 278, dashed=True, color=BLUE, label=""))
    b.append(arrow(180, 278, 78, 155, curve=26, color=BLUE, label="下一个 PC"))
    b.append(text(24, 350, "本课先实现实线部分；分支/跳转只改变 PC 的来源（虚线回路），不影响数据流。", size=12, fill=MUTED))
    return svg(880, 372, "\n".join(b), "图 6  和 L01 骨架里的端口一一对应：io_imem_* / io_dmem_* / o_retire_*")


def trace_compare() -> str:
    b = []
    b.append(text(24, 32, "对拍：为什么它比「看波形」更快", size=17, bold=True))
    b.append(box(24, 60, 300, 150, "", fill=LGREEN, stroke=GREEN))
    b.append(text(174, 86, "Python 黄金模型", size=14, anchor="middle", bold=True, fill=GREEN))
    b.append(text(40, 112, "00000000 00018117 02 00018000", size=11, mono=True))
    b.append(text(40, 132, "00000004 ff010113 02 00017ff0", size=11, mono=True))
    b.append(text(40, 152, "00000008 00010197 03 00010008", size=11, mono=True))
    b.append(text(40, 172, "... 共 58 行", size=11, mono=True, fill=MUTED))
    b.append(box(24, 236, 300, 150, "", fill=LAMBER, stroke=AMBER))
    b.append(text(174, 262, "你的 RTL 仿真", size=14, anchor="middle", bold=True, fill=AMBER))
    b.append(text(40, 288, "00000000 00018117 00 00000000", size=11, mono=True, fill=RED))
    b.append(text(40, 308, "                            ↑", size=11, mono=True, fill=RED))
    b.append(text(40, 330, "第 1 条就不同：rd/wdata 没接", size=11, fill=RED))
    b.append(arrow(330, 135, 420, 135))
    b.append(arrow(330, 311, 420, 311))
    b.append(box(430, 60, 330, 326, "", fill="#ffffff", stroke=BLUE))
    b.append(text(595, 92, "检查器输出", size=15, anchor="middle", bold=True, fill=BLUE))
    b.append(text(452, 124, "第 1 条指令不一致（pc=0x00000000）：", size=12))
    b.append(text(452, 148, "指令 : auipc sp, 0x18   机器码 0x00018117", size=12, mono=True))
    b.append(text(452, 172, "期望 : pc=0x00000000 rd=02 wdata=0x00018000", size=12, mono=True, fill=GREEN))
    b.append(text(452, 196, "实际 : pc=0x00000000 rd=00 wdata=0x00000000", size=12, mono=True, fill=RED))
    b.append(text(452, 228, "提示 : U 型立即数是高 20 位，auipc 还要加 PC", size=12, fill=MUTED))
    b.append(text(452, 268, "它直接告诉你：", size=13, bold=True, fill=BLUE))
    b.append(text(452, 292, "• 哪条指令错了（pc + 反汇编）", size=12))
    b.append(text(452, 314, "• 期望值和你算出来的值的差异", size=12))
    b.append(text(452, 336, "• 该去查哪个知识点", size=12))
    b.append(text(452, 364, "波形只在需要看时序时再打开。", size=12, fill=MUTED))
    return svg(790, 410, "\n".join(b), "图 7  trace 对拍把「调试」变成了「读错误信息」")


def coralnpu_arch() -> str:
    b = []
    b.append(text(24, 32, "CoralNPU 的三个计算部件（本课程的最终目标）", size=17, bold=True))
    b.append(box(24, 60, 250, 210, "", fill=LBLUE, stroke=BLUE))
    b.append(text(149, 88, "标量核（L01–L04）", size=14, anchor="middle", bold=True, fill=BLUE))
    for i, t in enumerate(["RV32IMF 取指/译码/派发", "4 路派发，乱序退休", "LSU：slot 式访存", "CSR / 异常 / 中断"]):
        b.append(text(40, 118 + i * 28, "• " + t, size=11.5))
    b.append(box(300, 60, 250, 210, "", fill=LGREEN, stroke=GREEN))
    b.append(text(425, 88, "向量核（L06）", size=14, anchor="middle", bold=True, fill=GREEN))
    for i, t in enumerate(["128-bit SIMD，64 个向量寄存器", "vsetvl 控制 vl/vtype", "stripmining：1 派发 → 4 发射", "RVV 访存与 vadd/vwmul"]):
        b.append(text(316, 118 + i * 28, "• " + t, size=11.5))
    b.append(box(576, 60, 250, 210, "", fill=LAMBER, stroke=AMBER))
    b.append(text(701, 88, "矩阵引擎（L07）", size=14, anchor="middle", bold=True, fill=AMBER))
    for i, t in enumerate(["量化的外积 MAC 阵列", "8×8×32-bit 累加器", "256 MAC/cycle 的目标", "Zvt：vtmmu / vtmms / vtfmm"]):
        b.append(text(592, 118 + i * 28, "• " + t, size=11.5))
    b.append(box(24, 296, 802, 60, "ITCM 8 KB（指令）· DTCM 32 KB（数据）· AXI4 从/主接口 · TileLink-UL 内部总线（L08）",
                 fill=GREY, stroke=MUTED, size=13))
    b.append(arrow(276, 165, 296, 165))
    b.append(arrow(552, 165, 572, 165))
    b.append(text(24, 386, "资料来源：doc/overview.md、doc/microarch/、README.md（本图按仓库文档重绘）", size=11, fill=MUTED))
    return svg(850, 400, "\n".join(b))


def comb_vs_seq() -> str:
    b = []
    b.append(text(24, 34, "组合逻辑 vs 时序逻辑：有没有「记忆」是唯一的分界", size=18, bold=True))
    # 组合逻辑
    b.append(box(24, 64, 480, 150, "", fill=LBLUE, stroke=BLUE))
    b.append(text(44, 92, "组合逻辑：输出只由当前输入决定", size=14, bold=True, fill=BLUE))
    b.append(box(48, 116, 90, 50, "输入 a,b", fill="#ffffff", stroke=BLUE, size=13))
    b.append(box(180, 116, 110, 50, "与/或门", fill="#ffffff", stroke=BLUE, size=13))
    b.append(box(332, 116, 90, 50, "输出 y", fill="#ffffff", stroke=BLUE, size=13))
    b.append(arrow(140, 141, 176, 141))
    b.append(arrow(292, 141, 328, 141))
    b.append(text(48, 192, "输入一变，输出立刻跟着变（只需经过几个门延迟）。Verilog 写法：assign / always_comb", size=11.5, fill=MUTED))
    # 时序逻辑
    b.append(box(530, 64, 480, 150, "", fill=LGREEN, stroke=GREEN))
    b.append(text(550, 92, "时序逻辑：只在时钟边沿改变，有记忆", size=14, bold=True, fill=GREEN))
    b.append(box(554, 116, 90, 50, "输入 d", fill="#ffffff", stroke=GREEN, size=13))
    b.append(box(686, 116, 120, 50, "触发器", fill="#ffffff", stroke=GREEN, size=13))
    b.append(box(848, 116, 90, 50, "输出 q", fill="#ffffff", stroke=GREEN, size=13))
    b.append(arrow(646, 141, 682, 141))
    b.append(arrow(808, 141, 844, 141))
    b.append(text(686, 190, "时钟边沿", size=11, anchor="middle", fill=GREEN))
    b.append(arrow(746, 208, 746, 170, color=GREEN))
    b.append(text(554, 192, "d 变了不算数，要到下一个时钟上升沿 q 才更新。写法：always_ff @(posedge clk)", size=11.5, fill=MUTED))
    b.append(text(24, 250, "一句话：组合逻辑 = 当前输入的函数；时序逻辑 = 记住上一次的值，并在时钟边沿更新。", size=13, bold=True))
    b.append(text(24, 278, "处理器里两者都有：ALU、多路选择器是组合逻辑；PC、寄存器堆、状态机是时序逻辑。", size=12, fill=MUTED))
    return svg(1040, 300, "\n".join(b))


def clock_wave() -> str:
    b = []
    b.append(text(24, 34, "时钟、复位与触发：一个计数器的波形", size=18, bold=True))
    x0, dx, hi, lo = 150, 46, 70, 108
    # 时钟
    b.append(text(24, hi + 4, "clk", size=13, mono=True, bold=True))
    pts = []
    x = x0
    for i in range(11):
        pts.append(f"{x},{hi if i % 2 == 0 else lo} {x + dx},{hi if i % 2 == 0 else lo}")
        x += dx
    b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{BLUE}" stroke-width="1.8"/>')
    # 复位
    b.append(text(24, lo + 78, "rst", size=13, mono=True, bold=True))
    ry = lo + 74
    b.append(f'<polyline points="{x0},{ry} {x0 + 2 * dx},{ry} {x0 + 2 * dx},{ry + 14} {x0 + 10 * dx},{ry + 14}" '
             f'fill="none" stroke="{AMBER}" stroke-width="1.8"/>')
    b.append(text(x0 + 2 * dx + 6, ry - 6, "复位期间 q 被清 0", size=11, fill=MUTED))
    # en
    b.append(text(24, ry + 62, "en", size=13, mono=True, bold=True))
    ey = ry + 58
    b.append(f'<polyline points="{x0},{ey} {x0 + 3 * dx},{ey} {x0 + 3 * dx},{ey + 14} {x0 + 8 * dx},{ey + 14} '
             f'{x0 + 8 * dx},{ey} {x0 + 10 * dx},{ey}" fill="none" stroke="{GREEN}" stroke-width="1.8"/>')
    # q
    b.append(text(24, ey + 62, "q", size=13, mono=True, bold=True))
    qy = ey + 58
    steps = [(0, "0"), (3, "1"), (4, "2"), (5, "3"), (6, "4"), (7, "5"), (8, "5")]
    for i, (s, label) in enumerate(steps):
        level = qy - (10 if label != "0" else 0)
        b.append(f'<polyline points="{x0 + s * dx},{level} {x0 + (s + 1) * dx},{level}" '
                 f'fill="none" stroke="{PURPLE}" stroke-width="1.8"/>')
        b.append(text(x0 + s * dx + dx / 2, level - 8, label, size=11, anchor="middle", fill=PURPLE))
    # 边沿标记
    for i in range(3, 9):
        x = x0 + i * dx
        b.append(f'<line x1="{x}" y1="{hi - 12}" x2="{x}" y2="{qy + 6}" stroke="{MUTED}" '
                 f'stroke-width="0.8" stroke-dasharray="4 4"/>')
    b.append(text(24, qy + 34, "虚线 = 时钟上升沿：只有在这些时刻，q 才可能变化（en=1 时 +1，en=0 时保持）。", size=12, fill=MUTED))
    b.append(text(24, qy + 58, "复位是异步还是同步要看设计；本课程统一用「同步复位 + 复位优先」的写法。", size=12, fill=MUTED))
    return svg(1050, qy + 80, "\n".join(b))


def c_to_machine() -> str:
    b = []
    b.append(text(24, 34, "从 C 源码到内存里的机器码：四个阶段", size=18, bold=True))
    stages = [
        ("hello.c", "C 源文件\n（人写的）", LBLUE, BLUE),
        ("hello.o", "目标文件\n机器码 + 符号（地址未定）", LAMBER, AMBER),
        ("hello.elf", "可执行文件\n段已定位到 0x0 / 0x10000", LGREEN, GREEN),
        ("内存镜像", "program.hex → ITCM\ndata.hex → DTCM", LPURPLE, PURPLE),
    ]
    x = 24
    for i, (title, sub, fill, stroke) in enumerate(stages):
        b.append(box(x, 66, 210, 110, "", fill=fill, stroke=stroke))
        b.append(text(x + 105, 96, title, size=14.5, anchor="middle", bold=True, fill=stroke, mono=True))
        for j, line in enumerate(sub.split("\n")):
            b.append(text(x + 105, 122 + j * 20, line, size=11, anchor="middle", fill=MUTED))
        if i < len(stages) - 1:
            b.append(arrow(x + 214, 121, x + 254, 121))
        x += 258
    labels = ["编译", "汇编 + 链接", "拆段"]
    x = 24 + 214
    for label in labels:
        b.append(text(x + 20, 108, label, size=11.5, anchor="middle", fill=MUTED))
        x += 258
    b.append(text(24, 214, "每一步都可以单独执行、单独观察：", size=13, bold=True))
    for i, cmd in enumerate([
        "gcc -E 只看预处理     gcc -S 生成汇编",
        "gcc -c 只编译成 .o    gcc -T link.ld 按链接脚本定位",
        "objdump -d 反汇编     objdump -t 看符号表",
    ]):
        b.append(text(40, 240 + i * 24, cmd, size=11.5, mono=True, fill=MUTED))
    return svg(1090, 320, "\n".join(b), "图：课程脚本 course/tools/build_program.py 就是把最后一步自动化了")


def lsu_fsm() -> str:
    b = []
    b.append(text(24, 34, "LSU 状态机：一次访存指令 → 1~2 笔对齐事务", size=18, bold=True))
    # 三个状态
    b.append(box(40, 90, 180, 86, "IDLE\n空闲\nbusy=0, done=0", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(300, 90, 200, 86, "REQ\n发出事务\ndmem_valid=1\n等 dmem_ready", fill=LAMBER, stroke=AMBER, size=12.5))
    b.append(box(590, 90, 180, 86, "FINISH\n完成\ndone=1", fill=LGREEN, stroke=GREEN, size=12.5))
    b.append(box(840, 90, 170, 86, "回到 IDLE\n等下一\n条指令", fill=GREY, stroke=MUTED, size=12.5))
    b.append(arrow(224, 133, 296, 133, label="req_valid=1\n锁存请求"))
    b.append(arrow(504, 133, 586, 133, label="ready=1 且\n不需要第二笔"))
    b.append(arrow(774, 133, 836, 133))
    b.append(arrow(500, 180, 400, 236, curve=10, color=AMBER, label="ready=1 且需要第二笔\nstep=1，地址 +4"))
    b.append(box(300, 236, 200, 60, "再发一笔 REQ", fill=LAMBER, stroke=AMBER, size=13))
    b.append(arrow(500, 266, 660, 180, curve=26, color=AMBER, label="ready=1 → FINISH"))
    b.append(text(24, 330, "核心侧：busy=1 时冻结 PC 与寄存器写回；done=1 的那一拍提交这条指令（写回 / trace / PC+4）。",
                  size=12, fill=MUTED))
    b.append(text(24, 354, "存储器侧：addr/wmask/wdata 在 REQ 期间必须保持不变，直到 ready=1（valid/ready 握手的基本纪律）。",
                  size=12, fill=MUTED))
    return svg(1040, 380, "\n".join(b))


def unaligned_split() -> str:
    b = []
    b.append(text(24, 34, "非对齐字存储 sw 0xAABBCCDD, 3(s5)：拆成两笔事务", size=17, bold=True))
    # 两个字
    for wi, (label, base) in enumerate([("字 0（地址 A）", 0xA0), ("字 1（地址 A+4）", 0xE0)]):
        y = 80 + wi * 120
        b.append(text(24, y + 24, label, size=13, bold=True, mono=False,
                      fill=BLUE if wi == 0 else GREEN))
        for i in range(4):
            x = 210 + i * 120
            fill = "#ffffff"
            stroke = BLUE if wi == 0 else GREEN
            b.append(box(x, y, 120, 56, "", fill=fill, stroke=stroke))
            b.append(text(x + 60, y + 22, f"byte{wi*4+i}", size=11, anchor="middle", fill=MUTED))
            if wi == 0:
                val = {0: "44", 1: "EF", 2: "BE", 3: "DD"}[i]
            else:
                val = {0: "CC", 1: "BB", 2: "AA", 3: "55"}[i]
            b.append(text(x + 60, y + 44, val, size=15, anchor="middle", mono=True, bold=True))
    # 数据字节
    b.append(text(24, 252, "要写入的 4 个字节（从地址 A+3 开始）：", size=13, bold=True))
    for i, val in enumerate(["DD", "CC", "BB", "AA"]):
        x = 330 + i * 100
        b.append(box(x, 230, 100, 44, "", fill=LAMBER, stroke=AMBER))
        b.append(text(x + 50, 258, val, size=14, anchor="middle", mono=True, bold=True, fill=AMBER))
    b.append(arrow(360, 230, 270, 140, curve=16, color=AMBER, label=""))
    b.append(arrow(660, 230, 690, 200, curve=16, color=AMBER, label=""))
    # 两笔事务
    b.append(box(24, 320, 470, 96, "", fill=LBLUE, stroke=BLUE))
    b.append(text(40, 348, "第一笔（字 0）：addr=A, wmask=1000, wdata=0xDD000000",
                  size=12.5, bold=True, fill=BLUE))
    b.append(text(40, 372, "只改 byte3：wmask = 0b1111 << 3 的低 4 位；数据 = 原始值 << 24", size=11.5, fill=MUTED))
    b.append(text(40, 396, "剩下没写进去的 3 个字节 → 用原始值 >> 8 交给第二笔", size=11.5, fill=MUTED))
    b.append(box(520, 320, 470, 96, "", fill=LGREEN, stroke=GREEN))
    b.append(text(536, 348, "第二笔（字 1）：addr=A+4, wmask=0111, wdata=0x00AABBCC",
                  size=12.5, bold=True, fill=GREEN))
    b.append(text(536, 372, "改 byte0..byte2；wmask = 0b1111 >> (4-3) = 0111", size=11.5, fill=MUTED))
    b.append(text(536, 396, "两笔都等 ready 完成，最后一起提交指令", size=11.5, fill=MUTED))
    return svg(1020, 450, "\n".join(b), "非对齐载入方向反过来：先读两个字，拼成 64 位后右移 8*offset，再取需要的字节并扩展")


DIAGRAMS = {
    "learning_loop": learning_loop,
    "repo_map": repo_map,
    "toolchain_flow": toolchain_flow,
    "memory_map": memory_map,
    "rv32i_formats": rv32i_formats,
    "single_cycle_datapath": single_cycle_datapath,
    "trace_compare": trace_compare,
    "coralnpu_arch": coralnpu_arch,
    "comb_vs_seq": comb_vs_seq,
    "clock_wave": clock_wave,
    "c_to_machine": c_to_machine,
    "lsu_fsm": lsu_fsm,
    "unaligned_split": unaligned_split,
}

# 每张图给哪些课程用
USED_BY = {
    "L00_setup": ["learning_loop", "repo_map", "toolchain_flow", "memory_map", "coralnpu_arch"],
    "L01_scalar": ["rv32i_formats", "single_cycle_datapath", "trace_compare", "memory_map"],
    "P0_prep": ["comb_vs_seq", "clock_wave", "c_to_machine", "memory_map", "single_cycle_datapath"],
    "L02_lsu": ["lsu_fsm", "unaligned_split", "memory_map"],
}

def generate(only: list[str] | None = None, verbose: bool = True) -> list[str]:
    written = []
    for lesson_dir, names in USED_BY.items():
        out_dir = os.path.join(COURSE, "lessons", lesson_dir, "diagrams")
        os.makedirs(out_dir, exist_ok=True)
        for name in names:
            if only and name not in only:
                continue
            path = os.path.join(out_dir, name + ".svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(DIAGRAMS[name]())
            written.append(path)
            if verbose:
                print(f"  生成 {os.path.relpath(path, os.path.dirname(COURSE))}")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="生成课程插图")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    if args.list:
        for name in DIAGRAMS:
            print(name)
        return 0
    generate(args.only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

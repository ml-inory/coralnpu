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
    # PDF 里插图会被缩放到页面宽度，字号太小会看不清，这里设一个下限
    size = max(size, 13)
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
        ("对照实现", "hdl/chisel 与 hdl/verilog/rvv"),
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
    return svg(1080, 300, "\n".join(b))


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


def lsu_division() -> str:
    b = []
    b.append(text(24, 32, "L02 的分工：核心、LSU、存储器各自负责什么", size=18, bold=True))

    # ---- 核心（上）
    b.append(box(60, 60, 560, 132, "", fill=LBLUE, stroke=BLUE))
    b.append(text(80, 90, "核心  core_wrapper.sv（课程提供，不用你写）", size=14.5, bold=True, fill=BLUE))
    for i, t in enumerate([
        "取指 / 译码 / ALU / 寄存器堆",
        "算出访存地址 req_addr = rs1 + imm（load 用 imm_i，store 用 imm_s）",
        "LSU 忙时冻结自己：不写寄存器、PC 不动",
        "LSU 报 done 的那一拍提交指令（写回 / trace / PC+4）",
    ]):
        b.append(text(80, 118 + i * 22, "• " + t, size=12.5))

    # ---- 核心 → LSU 的请求
    b.append(arrow(340, 196, 340, 252, label="req_valid · req_write · req_funct3 · wdata"))
    b.append(text(352, 226, "req_addr = rs1 + imm", size=12.5, fill=MUTED))

    # ---- LSU（中）
    b.append(box(60, 256, 560, 168, "", fill=LAMBER, stroke=AMBER))
    b.append(text(80, 286, "你实现的 LSU  rtl/lsu.sv（4 个 TODO）", size=14.5, bold=True, fill=AMBER))
    b.append(text(80, 314, "状态机：IDLE → REQ →（需要第二笔就再来一轮）→ FINISH", size=12.5))
    for i, t in enumerate([
        "把一条访存指令拆成 1~2 笔对齐事务（非对齐时跨字拆分）",
        "等 dmem_ready：握手期间地址/掩码/数据保持不变",
        "载入方向：拼两个字 → 右移 8*offset → 符号/零扩展",
    ]):
        b.append(text(80, 344 + i * 22, "• " + t, size=12.5))

    # ---- LSU → 存储器
    b.append(arrow(340, 428, 340, 484, label="dmem_valid · dmem_we · addr · wmask · wdata"))

    # ---- 存储器（下）
    b.append(box(60, 488, 560, 96, "", fill=LGREEN, stroke=GREEN))
    b.append(text(80, 518, "数据存储器（测试平台的 DTCM 模型）", size=14.5, bold=True, fill=GREEN))
    b.append(text(80, 546, "• 按 32 位字组织，按 wmask 逐字节写入", size=12.5))
    b.append(text(80, 570, "• 用 dmem_ready 表示“我现在能接/数据已就绪”，+LATENCY=N 可配 0/2 拍", size=12.5))

    # ---- 两条回程
    b.append(arrow(700, 520, 700, 300, color=GREEN))
    b.append(f'<polyline points="700,300 620,300" fill="none" stroke="{GREEN}" stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(arrow(700, 300, 700, 130, color=BLUE))
    b.append(f'<polyline points="700,130 620,130" fill="none" stroke="{BLUE}" stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(712, 250, "回给 LSU", size=12, fill=GREEN))
    b.append(text(712, 190, "回给核心", size=12, fill=BLUE))

    return svg(900, 600, "\n".join(b), "分工的边界：核心只管“发命令 + 等 + 提交”，字节级别的搬运全部由 LSU 负责")


def pipeline_stages() -> str:
    b = []
    b.append(text(24, 32, "5 级流水线：每条指令依次经过五个阶段", size=18, bold=True))
    stages = [
        ("IF", "取指\npc → imem", LBLUE, BLUE, "PC 寄存器"),
        ("ID", "译码 + 读寄存器堆\nimm 生成", LGREEN, GREEN, "IF/ID"),
        ("EX", "ALU + 分支解析\n地址计算", LAMBER, AMBER, "ID/EX"),
        ("MEM", "访存（交给 LSU）", LPURPLE, PURPLE, "EX/MEM"),
        ("WB", "写回 + 退休(trace)", GREY, MUTED, "MEM/WB"),
    ]
    x = 30
    for i, (name, desc, fill, stroke, reg) in enumerate(stages):
        b.append(box(x, 70, 150, 120, "", fill=fill, stroke=stroke))
        b.append(text(x + 75, 102, name, size=20, anchor="middle", bold=True, fill=stroke))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + 75, 128 + j * 20, line, size=11.5, anchor="middle", fill=MUTED))
        if i < len(stages) - 1:
            b.append(arrow(x + 154, 130, x + 194, 130))
        x += 198
    # 阶段寄存器标注
    x = 30
    regs = ["", "IF/ID", "ID/EX", "EX/MEM", "MEM/WB"]
    for i, reg in enumerate(regs):
        if reg:
            b.append(text(x + 75, 214, reg, size=11.5, anchor="middle", fill=MUTED))
            b.append(text(x + 75, 232, "↑ 阶段寄存器", size=10.5, anchor="middle", fill=MUTED))
        x += 198
    b.append(text(24, 272, "三类冒险发生在哪里：", size=14, bold=True))
    for i, line in enumerate([
        "数据冒险（EX 要用前一条的结果）→ 旁路（EX/MEM→EX、MEM/WB→EX）+ WB→ID 写穿",
        "load-use（EX 是 load，ID 马上要用）→ 冻结 IF/ID 一拍 + 给 ID/EX 插气泡",
        "控制冒险（EX 才解析分支/跳转）→ 冲刷 IF/ID 与 ID/EX，PC 重定向到目标",
        "结构冒险（LSU 忙）→ 整条流水线冻结（含 MEM/WB，否则旁路来源会跑掉）",
    ]):
        b.append(text(40, 298 + i * 24, "• " + line, size=12))
    return svg(1080, 400, "\n".join(b), "每级之间都有一个阶段寄存器；冒险处理就是决定“谁冻结、谁插气泡、谁被冲刷”")


def hazard_timeline() -> str:
    b = []
    b.append(text(24, 32, "两种停顿与一次冲刷：周期级时序", size=18, bold=True))
    rows = [
        ("load-use 停顿", ["IF: lw", "ID: add", "EX: --", "MEM: lw", "WB: --"], BLUE),
        ("", ["IF: add", "ID: --", "EX: lw", "MEM: --", "WB: --"], MUTED),
        ("", ["IF: ...", "ID: add", "EX: --", "MEM: lw", "WB: --"], MUTED),
        ("分支冲刷", ["IF: bne", "ID: X", "EX: X", "MEM: --", "WB: --"], AMBER),
        ("", ["IF: 目标", "ID: --", "EX: bne", "MEM: --", "WB: --"], MUTED),
        ("", ["IF: 目标+4", "ID: 目标", "EX: --", "MEM: bne", "WB: --"], MUTED),
    ]
    y = 70
    for label, cells, stroke in rows:
        if label:
            b.append(text(24, y + 20, label, size=13, bold=True, fill=stroke))
        x = 190
        for cell in cells:
            fill = "#ffffff" if "X" not in cell and "--" not in cell else GREY
            if "X" in cell:
                fill = LAMBER
            b.append(box(x, y, 150, 34, cell, fill=fill, stroke=stroke, size=11.5, radius=4))
            x += 158
        y += 42
    b.append(text(24, y + 20, "X = 被冲刷的错路指令（必须不写寄存器、不产生 trace）；-- = 气泡（有效位为 0）", size=12, fill=MUTED))
    b.append(text(24, y + 44, "关键：气泡的控制位必须清零，否则它会带着上一条指令的控制信号去写寄存器堆。", size=12, fill=MUTED))
    return svg(1010, y + 70, "\n".join(b))


def trap_flow() -> str:
    b = []
    b.append(text(24, 32, "异常的进入与返回：ecall → 处理程序 → mret", size=18, bold=True))
    # 主流程
    b.append(box(40, 70, 200, 74, "正常执行\n……\necall / 非法指令", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(300, 70, 240, 74, "硬件：进入异常", fill=LAMBER, stroke=AMBER, size=13, bold=True))
    b.append(box(600, 70, 200, 74, "处理程序\n（mtvec 处的代码）", fill=LGREEN, stroke=GREEN, size=12.5))
    b.append(box(860, 70, 150, 74, "mret\n返回 mepc", fill=LPURPLE, stroke=PURPLE, size=12.5))
    b.append(arrow(244, 107, 296, 107))
    b.append(arrow(544, 107, 596, 107))
    b.append(arrow(804, 107, 856, 107))
    for i, t in enumerate([
        "mepc   ← 触发异常的指令地址",
        "mcause ← 异常原因（ecall=11 / 非法=2 / ebreak=3）",
        "PC     ← mtvec（并冲刷错路指令）",
    ]):
        b.append(text(316, 164 + i * 22, "• " + t, size=11.5))
    b.append(text(616, 164, "读 mepc/mcause 做处理；", size=11.5))
    b.append(text(616, 186, "把 mepc += 4 跳过触发指令，", size=11.5))
    b.append(text(616, 208, "然后 mret。", size=11.5))
    b.append(arrow(935, 144, 935, 250, color=PURPLE))
    b.append(f'<polyline points="935,250 140,250 140,148" fill="none" stroke="{PURPLE}" '
             f'stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(560, 242, "返回到「下一条指令」继续执行（前提是处理程序改过 mepc）", size=11.5, fill=MUTED))
    # CSR 表
    b.append(text(24, 300, "本课实现的最小 CSR 集合", size=14, bold=True))
    rows = [
        ("0x300 mstatus", "读写", "机器状态（本课当普通寄存器）"),
        ("0x301 misa", "只读", "0x4000_1100 = RV32 + I + M"),
        ("0x305 mtvec", "读写", "异常入口地址"),
        ("0x340 mscratch", "读写", "给处理程序暂存数据"),
        ("0x341 mepc", "读写", "触发异常的指令地址"),
        ("0x342 mcause", "读写", "异常原因码"),
    ]
    y = 326
    for name, access, note in rows:
        b.append(text(40, y, name, size=12, mono=True, bold=True))
        b.append(text(230, y, access, size=12, fill=MUTED))
        b.append(text(300, y, note, size=12, fill=MUTED))
        y += 24
    return svg(1040, y + 20, "\n".join(b),
               "关键细节：mepc 存的是「触发异常的那条指令」，所以处理程序必须自己 +4 才能继续往下跑")


def axi_timing() -> str:
    """AXI 的逐拍时序：读事务、写事务，以及核心侧 valid/ready 的对应关系。"""
    b = []
    x0, dx = 205, 56
    b.append(text(24, 30, "AXI 事务的逐拍时序：握手 = VALID 与 READY 同时为 1 的那一拍",
                  size=17, bold=True))

    def clk_wave(y, n=8, label="clk"):
        x, pts = x0, []
        for _ in range(n):
            pts += [f"{x},{y+18}", f"{x+dx/2},{y+18}", f"{x+dx/2},{y}", f"{x+dx},{y}"]
            x += dx
        b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{BLUE}" stroke-width="1.5"/>')
        b.append(text(x0 - 14, y + 13, label, size=11.5, mono=True, anchor="end"))

    def sig(y, levels, label, color=INK):
        pts = []
        for i, lv in enumerate(levels):
            yy = y if lv else y + 18
            pts += [f"{x0 + i*dx},{yy}", f"{x0 + (i+1)*dx},{yy}"]
        b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.8"/>')
        b.append(text(x0 - 14, y + 13, label, size=11.5, mono=True, anchor="end"))

    def bus(y, c0, c1, label, color=PURPLE, fill=LPURPLE):
        """数据总线：框宽自动按文字宽度撑开，避免框线穿过文字。"""
        xa, xb = x0 + c0 * dx, x0 + c1 * dx
        need = len(label) * 7.2 + 34                      # 中文/ASCII 混排的保守估计
        if xb - xa < need:
            mid = (xa + xb) / 2
            xa, xb = mid - need / 2, mid + need / 2
        b.append(f'<polyline points="{xa},{y} {xa+9},{y+10} {xb-9},{y+10} {xb},{y} '
                 f'{xb-9},{y-10} {xa+9},{y-10} {xa},{y}" fill="{fill}" stroke="{color}" stroke-width="1.3"/>')
        b.append(text((xa + xb) / 2, y + 4, label, size=11, anchor="middle"))

    def mark(cycle, y_top, y_bot, label, label_y=None):
        """在某个时钟沿画虚线；标注默认写在虚线下方，可显式指定行高错开。"""
        x = x0 + (cycle + 0.5) * dx
        b.append(f'<line x1="{x}" y1="{y_top}" x2="{x}" y2="{y_bot}" stroke="{AMBER}" '
                 f'stroke-width="1.2" stroke-dasharray="4 4"/>')
        b.append(text(x, label_y if label_y is not None else y_bot + 16,
                      label, size=11, fill=AMBER, anchor="middle"))
        return x

    # ---------------- 面板 1：读事务 ----------------
    y = 60
    b.append(text(24, y - 14, "① 读事务：AR 送地址，R 送数据（两条通道各自握手）", size=13.5, bold=True))
    clk_wave(y)
    sig(y + 44, [0, 1, 1, 1, 0, 0, 0, 0], "ARVALID", BLUE)
    sig(y + 74, [0, 0, 1, 1, 1, 0, 0, 0], "ARREADY", GREEN)
    sig(y + 104, [0, 0, 0, 0, 1, 1, 1, 0], "RVALID", BLUE)
    sig(y + 134, [0, 0, 0, 0, 0, 1, 1, 1], "RREADY", GREEN)
    bus(y + 172, 4, 6, "RDATA（数据）")
    mark(2, y - 16, y + 134, "① AR 握手", y + 202)
    mark(5, y - 16, y + 134, "② R 握手", y + 202)

    # ---------------- 面板 2：写事务 ----------------
    y = 330
    b.append(text(24, y - 24, "② 写事务：AW 送地址、W 送数据（两条通道独立），最后 B 回响应", size=13.5, bold=True))
    clk_wave(y)
    sig(y + 44, [0, 1, 1, 1, 0, 0, 0, 0], "AWVALID", BLUE)
    sig(y + 70, [0, 0, 1, 1, 1, 0, 0, 0], "AWREADY", GREEN)
    sig(y + 96, [0, 1, 1, 1, 1, 0, 0, 0], "WVALID", BLUE)
    sig(y + 122, [0, 0, 0, 1, 1, 1, 0, 0], "WREADY", GREEN)
    sig(y + 148, [0, 0, 0, 0, 0, 1, 1, 0], "BVALID", BLUE)
    sig(y + 174, [0, 0, 0, 0, 0, 0, 1, 1], "BREADY", GREEN)
    bus(y + 212, 3, 4, "WDATA + WSTRB", AMBER, LAMBER)
    mark(2, y - 16, y + 174, "① AW 握手", y + 242)
    mark(3, y - 16, y + 174, "② W 握手", y + 262)
    mark(6, y - 16, y + 174, "③ B 握手（写完成）", y + 242)

    # ---------------- 面板 3：核心侧 ↔ 主接口 ----------------
    y = 620
    b.append(text(24, y - 24, "③ 外壳内部：核心的 valid/ready 被拉长成 AXI 事务", size=13.5, bold=True))
    clk_wave(y, 8, "core_clk")
    sig(y + 44, [0, 1, 1, 1, 1, 1, 0, 0], "i_dmem_valid", BLUE)
    sig(y + 74, [0, 0, 0, 0, 0, 1, 0, 0], "o_dmem_ready", GREEN)
    b.append(box(x0 - 40, y + 104, 4.6 * dx, 28, "mstate: IDLE → RADDR → RDATA → IDLE",
                 fill=GREY, size=11.5))
    mark(5, y - 16, y + 90, "R 到达的那一拍才 ready", y + 152)
    b.append(text(24, y + 186,
                  "核心把请求保持到 ready 为止；外壳用 AXI 的多次握手把这段时间填满——两边语言不同，握手的含义相同。",
                  size=12, fill=MUTED))
    return svg(1120, y + 218, "\n".join(b),
               "读、写、核心侧：三种画法，同一条规则——只在 VALID 与 READY 同拍为 1 时才算完成")


def axi_system() -> str:
    b = []
    b.append(text(24, 32, "AXI 站在系统框图的哪里：主设备 — 互连 — 从设备", size=18, bold=True))

    # 主设备（能发起事务）
    b.append(box(60, 70, 220, 70, "主机 CPU\n(master)", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(320, 70, 220, 70, "DMA 引擎\n(master)", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(580, 70, 220, 70, "其它加速器\n(master)", fill=LBLUE, stroke=BLUE, size=12.5))
    # 互连
    b.append(box(60, 200, 960, 70, "AXI 互连：按地址映射转发 + 仲裁（crossbar / NoC）",
                 fill=GREY, stroke=INK, size=13, bold=True))
    # 从设备（被动响应）
    b.append(box(60, 340, 240, 78, "CoralNPU 的 s_axi\n（本课：axi_lite_slave + CSR）",
                 fill=LAMBER, stroke=AMBER, size=12))
    b.append(box(400, 340, 220, 78, "存储器\nITCM / DTCM / DDR", fill=LGREEN, stroke=GREEN, size=12))
    b.append(box(700, 340, 220, 78, "外设\nUART / SPI / GPIO", fill=LPURPLE, stroke=PURPLE, size=12))

    # 主设备 → 互连
    for x in (170, 430, 690):
        b.append(arrow(x, 144, x, 196))
    b.append(text(180, 175, "AXI", size=11.5, fill=MUTED))
    # 互连 → 从设备
    for x in (180, 510, 810):
        b.append(arrow(x, 274, x, 336))
    b.append(text(190, 308, "s_axi", size=11.5, fill=MUTED))

    # CoralNPU 的另一重身份：自己也是主设备
    b.append(f'<polyline points="300,340 300,310 980,310 980,274" fill="none" stroke="{AMBER}" '
             f'stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    b.append(text(470, 302, "m_axi：CoralNPU 作为主设备，去访问系统存储器/外设", size=11.5, fill=AMBER))
    b.append(text(24, 442, "主端口（master）能发起事务；从端口（slave）被动响应；互连按地址把请求转发给对应的从设备。",
                  size=12, fill=MUTED))
    return svg(1080, 470, "\n".join(b),
               "同一个 CoralNPU：主机通过它的从端口控制它，它通过自己的主端口替主机干活")


def axi_shell() -> str:
    b = []
    b.append(text(24, 32, "L04 的系统结构：主机启动核心，核心访存走 AXI", size=18, bold=True))

    b.append(box(30, 120, 170, 80, "主机\n(tb 里的 AXI BFM)", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(270, 70, 190, 70, "AXI4-Lite 从接口\naxi_lite_slave", fill=LAMBER, stroke=AMBER, size=12.5))
    b.append(box(270, 170, 190, 70, "控制寄存器\nRESET / PC_START / STATUS", fill=LGREEN, stroke=GREEN, size=12.5))
    b.append(box(270, 270, 190, 70, "ITCM（tcm.sv）\n组合读，主机可写", fill=LPURPLE, stroke=PURPLE, size=12.5))
    b.append(box(530, 170, 170, 70, "AXI4 主接口\nAR/R、AW+W/B", fill=LAMBER, stroke=AMBER, size=12.5))
    b.append(box(760, 70, 230, 90, "核心 core_l04\n= L03b + i_pc_start\n+ o_fault", fill=LBLUE, stroke=BLUE, size=12.5))
    b.append(box(760, 270, 230, 80, "系统存储器\nDTCM @0x0001_0000\n(测试平台)", fill=LGREEN, stroke=GREEN, size=12.5))

    b.append(arrow(204, 160, 266, 120, label="s_axi"))
    b.append(arrow(365, 144, 365, 166))
    b.append(arrow(365, 244, 365, 266))
    b.append(arrow(464, 100, 756, 100, label="o_core_rst / o_core_clk_gate / o_core_pc_start", color=GREEN))
    b.append(arrow(756, 140, 704, 172, label="imem / dmem", color=BLUE))
    b.append(arrow(704, 236, 756, 280, label="m_axi（load/store）", color=AMBER))
    b.append(arrow(756, 300, 464, 300, label="取指（组合读）", color=PURPLE))
    b.append(text(24, 380,
                  "启动：① 写 ITCM ② 写 PC_START ③ 放开时钟门控 ④ 放开复位 ⑤ 轮询 STATUS",
                  size=12, fill=MUTED))
    b.append(text(24, 402,
                  "数据：核心的每次 load/store 都变成一笔 m_axi 事务；取指走外壳内部的 ITCM",
                  size=12, fill=MUTED))
    return svg(1040, 430, "\n".join(b),
               "从接口让主机能启动核心，主接口让核心能访问系统存储器——两条通路用的都是 VALID/READY 握手")


def axi_boot_path() -> str:
    """启动通路：主机 → s_axi → 从接口/译码 → ITCM 与 CSR → 核心。"""
    b = []
    b.append(text(24, 32, "L04 启动通路：主机走 s_axi 灌程序、配寄存器，然后把核心放出来",
                  size=17, bold=True))

    b.append(box(30, 165, 170, 110, "主机 BFM\n(tb_axi.sv)\n按 5 步流程发 AXI 事务",
                 fill=LBLUE, stroke=BLUE, size=13))

    b.append(box(230, 80, 570, 450, "", fill="#fbfcfd", stroke=MUTED, radius=10))
    b.append(text(248, 108, "外壳 axi_boot_shell.sv —— 你写的两个文件都装在这一层",
                  size=14.5, bold=True))
    b.append(text(248, 130, "TODO 1 译码 · TODO 2 ITCM · TODO 3/4 CSR 与启动控制",
                  size=12.5, fill=MUTED))

    b.append(box(260, 160, 250, 115,
                 "axi_lite_slave.sv（TODO 1–5）\nAW/W/B/AR/R 五通道\n↕ 翻译成一组本地读写信号",
                 fill=LAMBER, stroke=AMBER, size=13))
    b.append(box(260, 335, 250, 120,
                 "地址译码 + 读 mux + 响应码（TODO 1）\n命中 ITCM / CSR → OKAY\n其它地址 → SLVERR\nrd_hit_* 决定读 mux 选 ITCM 还是 CSR",
                 fill=LGREEN, stroke=GREEN, size=13))
    b.append(box(570, 160, 215, 115,
                 "ITCM  tcm.sv（TODO 2）\n8 KB @ 0x0000_0000\n主机写口 + 3 个组合读口",
                 fill=LPURPLE, stroke=PURPLE, size=13))
    b.append(box(570, 335, 215, 120,
                 "三个控制寄存器（TODO 3/4）\nRESET_CONTROL @0x30000\nPC_START @0x30004\nSTATUS @0x30008",
                 fill=LGREEN, stroke=GREEN, size=13))
    b.append(box(920, 160, 235, 295,
                 "核心 core_l04\n（课程提供）\n\n= L03b 流水线核\n+ i_pc_start\n+ o_fault\n\n复位后从\nPC_START 取指",
                 fill=LBLUE, stroke=BLUE, size=13))

    # 主机 → 从接口
    b.append(arrow(202, 220, 256, 220, color=BLUE))
    b.append(text(228, 208, "s_axi", size=12.5, anchor="middle", fill=MUTED))

    # 从接口 ↔ 译码（本地读写端口）
    b.append(arrow(330, 277, 330, 331, color=INK))
    b.append(arrow(440, 331, 440, 277, color=PURPLE))
    b.append(text(340, 290, "写口：o_wr_en 单拍脉冲", size=12.5))
    b.append(text(430, 318, "读：o_rd_addr / i_rd_data", size=12.5, anchor="end", fill=PURPLE))

    # 译码 → ITCM / CSR
    b.append(arrow(512, 380, 566, 250, label="wr_hit_itcm", size=12.5, color=PURPLE))
    b.append(arrow(512, 395, 566, 395, label="wr_hit_csr", size=12.5, color=GREEN))

    # CSR → 核心：三根控制线
    b.append(arrow(785, 335, 785, 300, dashed=True, color=GREEN))
    b.append(f'<polyline points="785,300 900,300 900,240 916,240" fill="none" stroke="{GREEN}" '
             f'stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(806, 214, "启动控制 3 根", size=12.5, bold=True, fill=GREEN))
    b.append(text(806, 236, "clk_gate", size=12.5, fill=GREEN))
    b.append(text(806, 258, "rst · pc_start", size=12.5, fill=GREEN))

    # 核心 → CSR：状态回送
    b.append(f'<polyline points="1040,458 1040,505 700,505 700,458" fill="none" stroke="{AMBER}" '
             f'stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    b.append(text(710, 498, "状态回送：i_core_halted / i_core_fault → STATUS",
                  size=12.5, fill=AMBER))

    y = 570
    for line in [
        "① 写 ITCM：主机从 0x0 起逐个字写程序（wr_hit_itcm → tcm 的 host_we）",
        "② 写 PC_START：0x30004 ← 0x100，再读回确认；此刻核心还没动（复位 + 时钟门控）",
        "③ 放开时钟门控：RESET_CONTROL ← 0x1（RESET 仍为 1）——核心第一次有时钟沿，就地被复位",
        "④ 放开复位：RESET_CONTROL ← 0x0 ——下一个时钟沿把 PC ← PC_START，开始取指",
        "⑤ 轮询 STATUS：读 0x30008，HALTED=1（执行了 mpause）或 FAULT=1（跑飞了）",
    ]:
        b.append(text(30, y, line, size=12.5, fill=MUTED))
        y += 24
    return svg(1180, y + 24, "\n".join(b),
               "两条通路在 ITCM 和 CSR 上汇合：主机写 ITCM 决定核心跑什么，主机写 CSR 决定核心什么时候跑")


def axi_data_path() -> str:
    """数据通路：核心的一次 load/store 如何在 ITCM 命中与 m_axi 事务之间选择。"""
    b = []
    b.append(text(24, 32, "L04 数据通路：核心的每次 load/store，要么命中 ITCM，要么变成一笔 m_axi 事务",
                  size=17, bold=True))
    b.append(text(24, 58, "取指是另一条路：i_imem_addr → ITCM 组合读 → o_imem_rdata，永远不出外壳",
                  size=12.5, fill=PURPLE))

    b.append(box(30, 200, 230, 250, "", fill=LBLUE, stroke=BLUE))
    b.append(text(50, 230, "核心 core_l04", size=14, bold=True, fill=BLUE))
    for i, t in enumerate([
        "imem_addr →（取指）",
        "← imem_rdata",
        "",
        "dmem 请求 →",
        "valid / we / addr",
        "wdata / wmask",
        "",
        "← dmem 回执",
        "rdata / ready",
    ]):
        b.append(text(50, 258 + i * 21, t, size=12.5))

    b.append(box(340, 250, 250, 145, "", fill=LGREEN, stroke=GREEN))
    b.append(text(360, 280, "核心侧路由（TODO 5）", size=14, bold=True, fill=GREEN))
    for i, t in enumerate([
        "输入：valid / we / addr / wdata / wmask",
        "d_hit_itcm：addr < 0x2000",
        "命中 → ITCM 组合读，1 拍完成",
        "未命中 → d_go_axi = 1",
    ]):
        b.append(text(360, 308 + i * 21, t, size=12.5))

    b.append(box(680, 110, 250, 130, "", fill=LPURPLE, stroke=PURPLE))
    b.append(text(700, 140, "ITCM  tcm.sv", size=14, bold=True, fill=PURPLE))
    for i, t in enumerate([
        "组合读：给地址那一拍就出数据",
        "核心没有 ready 可以等，",
        "所以它必须留在片内",
    ]):
        b.append(text(700, 168 + i * 21, t, size=12.5))

    b.append(box(680, 330, 250, 130, "", fill=LAMBER, stroke=AMBER))
    b.append(text(700, 360, "AXI 主状态机（TODO 6）", size=14, bold=True, fill=AMBER))
    for i, t in enumerate([
        "读：IDLE→RADDR→RDATA→IDLE",
        "写：IDLE→WADDR→BRESP→IDLE",
        "o_dmem_ready 在 R/B 到达时拉高",
    ]):
        b.append(text(700, 388 + i * 21, t, size=12.5))

    b.append(box(990, 330, 160, 120, "系统存储器\nDTCM\n@0x0001_0000\n（tb 的模型）",
                 fill=LGREEN, stroke=GREEN, size=13))

    # 核心 → 路由
    b.append(arrow(262, 320, 336, 320, label="i_dmem_*", size=12.5, color=BLUE))
    # 路由 → ITCM（命中）
    b.append(f'<polyline points="500,248 500,200 676,200" fill="none" stroke="{PURPLE}" '
             f'stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(508, 240, "命中：交给 ITCM 组合读", size=12.5, fill=PURPLE))
    # 路由 → 状态机（未命中）
    b.append(arrow(590, 360, 676, 360, label="未命中", size=12.5, color=AMBER))
    # 状态机 → DTCM
    b.append(arrow(930, 395, 986, 395, label="m_axi", size=12.5, color=AMBER))
    b.append(text(1160, 474, "m_axi 上的两笔：AR/R 或 AW+W/B", size=12.5, fill=AMBER, anchor="end"))
    # 回程 1：命中当拍就有
    b.append(f'<polyline points="790,108 790,80 150,80 150,196" fill="none" stroke="{PURPLE}" '
             f'stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    b.append(text(300, 98, "命中：o_dmem_rdata / o_dmem_ready 当拍就有", size=12.5, fill=PURPLE))
    # 回程 2：未命中要等 R / B
    b.append(f'<polyline points="790,462 790,520 150,520 150,456" fill="none" stroke="{AMBER}" '
             f'stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    b.append(text(300, 512, "未命中：等 R（读）或 B（写）到达，才拉高 o_dmem_ready", size=12.5, fill=AMBER))

    return svg(1180, 600, "\n".join(b),
               "ITCM 命中是「组合读、一拍结束」，未命中才是「AR→R / AW→B 的多次握手」——两者在 o_dmem_ready 上汇合")


def axi_master_fsm() -> str:
    """主接口状态机：读 AR→R、写 AW+W→B，以及每个状态各拉高哪些信号。"""
    b = []
    b.append(text(24, 32, "主接口状态机：把核心的一次 load/store 变成 AXI 事务", size=17, bold=True))
    b.append(text(24, 58, "核心只说「valid 举着、等 ready」；AXI 那边要走好几次握手，状态机负责把两者对齐",
                  size=12.5, fill=MUTED))

    b.append(box(40, 200, 140, 80, "M_IDLE\n抓一次请求", fill=GREY, stroke=INK, size=13, bold=True))
    b.append(box(250, 100, 160, 80, "M_RADDR\n发 AR 地址", fill=LBLUE, stroke=BLUE, size=13))
    b.append(box(470, 100, 160, 80, "M_RDATA\n等 R 数据", fill=LBLUE, stroke=BLUE, size=13))
    b.append(box(250, 300, 160, 80, "M_WADDR\nAW、W 各自握手", fill=LAMBER, stroke=AMBER, size=13))
    b.append(box(470, 300, 160, 80, "M_BRESP\n等 B 响应", fill=LAMBER, stroke=AMBER, size=13))

    # 读路径
    b.append(arrow(184, 214, 246, 146, label="d_go_axi & ~i_dmem_we", size=12.5, color=BLUE))
    b.append(arrow(414, 140, 466, 140, label="m_arready", size=12.5, color=BLUE))
    b.append(f'<polyline points="550,184 550,252 186,252" fill="none" stroke="{BLUE}" '
             f'stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(560, 246, "m_rvalid：这一拍才把 o_dmem_ready 拉高，并给出 o_dmem_rdata",
                  size=12.5, fill=BLUE))
    # 写路径
    b.append(arrow(184, 266, 246, 334, label="d_go_axi & i_dmem_we", size=12.5, color=AMBER))
    b.append(arrow(414, 340, 466, 340, label="两路都握完", size=12.5, color=AMBER))
    b.append(f'<polyline points="550,384 550,452 105,452 105,286" fill="none" stroke="{AMBER}" '
             f'stroke-width="1.8" marker-end="url(#arrowhead)"/>')
    b.append(text(560, 446, "m_bvalid：这一拍才把 o_dmem_ready 拉高", size=12.5, fill=AMBER))

    # ---------------- 每个状态的输出 ----------------
    ty0, rh = 500, 34
    cols = [(30, 130), (160, 130), (290, 130), (420, 170), (590, 170), (760, 140), (900, 250)]
    header = ["状态", "m_arvalid", "m_rready", "m_awvalid", "m_wvalid", "m_bready", "o_dmem_ready"]
    rows = [
        ("M_IDLE",  "0", "0", "0", "0", "0", "命中 ITCM → 1；未命中 → 0"),
        ("M_RADDR", "1", "0", "0", "0", "0", "0"),
        ("M_RDATA", "0", "1", "0", "0", "0", "m_rvalid 那一拍 → 1"),
        ("M_WADDR", "0", "0", "aw_pending", "w_pending", "0", "0"),
        ("M_BRESP", "0", "0", "0", "0", "1", "m_bvalid 那一拍 → 1"),
    ]
    b.append(text(30, ty0 - 14, "每个状态各拉高哪些信号（没写的都是 0）：", size=13.5, bold=True))
    for i in range(7):
        b.append(f'<line x1="{cols[0][0]}" y1="{ty0 + i * rh}" x2="{cols[-1][0] + cols[-1][1]}" '
                 f'y2="{ty0 + i * rh}" stroke="#c9d2dc" stroke-width="1"/>')
    for (x, w) in cols:
        b.append(f'<line x1="{x}" y1="{ty0}" x2="{x}" y2="{ty0 + 6 * rh}" stroke="#c9d2dc" stroke-width="1"/>')
    b.append(f'<line x1="{cols[-1][0] + cols[-1][1]}" y1="{ty0}" x2="{cols[-1][0] + cols[-1][1]}" '
             f'y2="{ty0 + 6 * rh}" stroke="#c9d2dc" stroke-width="1"/>')
    for j, name in enumerate(header):
        x, w = cols[j]
        b.append(text(x + w / 2, ty0 + rh - 11, name, size=12.5, anchor="middle", bold=True))
    for i, row in enumerate(rows):
        y = ty0 + rh * (i + 1)
        for j, cell in enumerate(row):
            x, w = cols[j]
            if j == len(cols) - 1:
                b.append(text(x + 10, y + rh - 11, cell, size=12.5))
            else:
                b.append(text(x + w / 2, y + rh - 11, cell, size=12.5, anchor="middle",
                              bold=(j == 0)))

    b.append(text(30, ty0 + 6 * rh + 30,
                  "两个细节：M_RDATA 里 o_dmem_rdata 必须直接给 m_rdata（核心在 ready 那一拍就采样）；"
                  "写的时候 AW 和 W 可能不同拍，所以要用 aw_pending / w_pending 各记一笔。",
                  size=12.5, fill=MUTED))
    return svg(1180, ty0 + 6 * rh + 70, "\n".join(b),
               "5 个状态就够了：IDLE 抓一次请求 → 用 AXI 的多次握手把时间填满 → 用 o_dmem_ready 告诉核心「这笔完成了」")


def axi_boot_sequence() -> str:
    """5 步启动流程：每一步之后三个控制寄存器、时钟、复位和核心状态各是什么。"""
    b = []
    b.append(text(24, 32, "5 步启动流程：为什么必须先放开时钟、再放开复位", size=17, bold=True))
    b.append(text(24, 58, "每一列是一个阶段；上下对照着看「主机做了什么」和「核心看到了什么」",
                  size=12.5, fill=MUTED))

    x0, col = 190, 196
    steps = [
        ("① 写 ITCM", "主机把程序逐字写进\n0x0000_0000 起的 8 KB"),
        ("② 写 PC_START", "0x30004 ← 0x100\n再读回来确认"),
        ("③ 放开时钟", "RESET_CONTROL ← 0x1\n（RESET 仍然 = 1）"),
        ("④ 放开复位", "RESET_CONTROL ← 0x0\n（CLOCK_GATE = 0）"),
        ("⑤ 轮询 STATUS", "读 0x30008\n看 HALTED / FAULT"),
    ]
    for i, (title, body) in enumerate(steps):
        x = 30 + i * 228
        b.append(box(x, 80, 212, 110, title, fill=LBLUE, stroke=BLUE, size=14, bold=True))
        b.append(text(x + 12, 176, body, size=12.5, fill=MUTED))

    rows = [
        ("RESET_CONTROL", ["0x3", "0x3", "0x1", "0x0", "0x0"], INK),
        ("CLOCK_GATE", ["1（关）", "1（关）", "0（开）", "0（开）", "0（开）"], INK),
        ("core 看到的时钟", ["没有时钟沿", "没有时钟沿", "开始有时钟沿", "有时钟沿", "有时钟沿"], BLUE),
        ("o_core_rst", ["1（但没沿采样）", "1", "1（这个沿采样到）", "0", "0"], RED),
        ("核心状态", ["未初始化", "未初始化", "被复位：PC ← 0x100", "从 0x100 取指", "停机 / 跑飞"], GREEN),
        ("STATUS", ["0", "0", "0", "0", "HALTED 或 FAULT"], AMBER),
    ]
    y = 270
    for name, cells, color in rows:
        b.append(f'<line x1="30" y1="{y - 16}" x2="1160" y2="{y - 16}" stroke="#dfe4ea" stroke-width="1"/>')
        b.append(text(30, y + 4, name, size=12.5, bold=True, fill=color))
        for i, c in enumerate(cells):
            b.append(text(x0 + i * col + col / 2 - 20, y + 4, c, size=12.5, anchor="middle"))
        y += 46
    b.append(f'<line x1="30" y1="{y - 16}" x2="1160" y2="{y - 16}" stroke="#dfe4ea" stroke-width="1"/>')

    # 阶段分隔线
    for i in range(1, 5):
        x = 30 + i * 228 - 8
        b.append(f'<line x1="{x}" y1="76" x2="{x}" y2="{y - 16}" stroke="{MUTED}" '
                 f'stroke-width="1" stroke-dasharray="4 4"/>')

    # core_clk / core_rst 的波形示意
    wy = 236
    b.append(text(30, wy + 4, "core_clk", size=12.5, bold=True, fill=BLUE))
    b.append(f'<line x1="{x0}" y1="{wy}" x2="{x0 + 2 * col}" y2="{wy}" stroke="{MUTED}" '
             f'stroke-width="1.6" stroke-dasharray="5 4"/>')
    pts = []
    px = x0 + 2 * col
    for _ in range(3):
        pts += [f"{px},{wy}", f"{px + col / 2},{wy}", f"{px + col / 2},{wy - 16}",
                f"{px + col},{wy - 16}", f"{px + col},{wy}"]
        px += col
    b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{BLUE}" stroke-width="1.6"/>')
    b.append(text(x0 + col, wy - 8, "时钟被门控（没有时钟沿）", size=12.5, fill=MUTED, anchor="middle"))

    b.append(text(24, y + 44,
                  "反例：如果第 3、4 步调换——先放开复位（此时还没有时钟），等时钟来的第一个沿，rst 已经是 0，"
                  "核心从没见过「复位有效」，寄存器停在未初始化状态（仿真里就是 X，一条指令都不执行）。",
                  size=12.5, fill=RED))
    return svg(1180, y + 94, "\n".join(b),
               "顺序不是随口定的：同步复位需要「一个 rst=1 的时钟沿」才生效，所以时钟必须先开")


DIAGRAMS = {
    "axi_timing": axi_timing,
    "axi_system": axi_system,
    "axi_shell": axi_shell,
    "axi_boot_path": axi_boot_path,
    "axi_data_path": axi_data_path,
    "axi_boot_sequence": axi_boot_sequence,
    "axi_master_fsm": axi_master_fsm,
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
    "lsu_division": lsu_division,
    "pipeline_stages": pipeline_stages,
    "hazard_timeline": hazard_timeline,
    "trap_flow": trap_flow,
}

# 每张图给哪些课程用
USED_BY = {
    "L00_setup": ["learning_loop", "repo_map", "toolchain_flow", "memory_map", "coralnpu_arch"],
    "L01_scalar": ["rv32i_formats", "single_cycle_datapath", "trace_compare", "memory_map", "toolchain_flow"],
    "P0_prep": ["comb_vs_seq", "clock_wave", "c_to_machine", "memory_map", "single_cycle_datapath"],
    "L02_lsu": ["lsu_fsm", "unaligned_split", "lsu_division", "memory_map"],
    "L03a_pipeline": ["pipeline_stages", "hazard_timeline"],
    "L03b_mdu_csr": ["trap_flow"],
    "L04_axi_boot": ["axi_system", "axi_shell", "axi_boot_path", "axi_data_path",
                     "axi_boot_sequence", "axi_master_fsm", "axi_timing"],
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

#!/usr/bin/env python3
"""把 VCD 波形打印成"信号名 + 值"的文本表（不需要 GTKWave）。

检查器只会说"AXI 握手卡住了"；你想知道到底是哪根线没拉高、哪几拍的
valid/ready 对不上——这个工具把波形变成可以直接读的表格。

用法：
  ./learn wave L04 --only 10 --signals s_aw,s_w,s_b --cycles 30
  python3 course/tools/vcd.py <文件.vcd> --list          # 列出所有信号名
  python3 course/tools/vcd.py <文件.vcd> --signals clk,rst --cycles 10
"""

from __future__ import annotations

import argparse
import os
import re


class Vcd:
    def __init__(self) -> None:
        self.id_name: dict[str, str] = {}       # VCD 标识符 → 信号名
        self.id_width: dict[str, int] = {}
        self.changes: dict[str, list[tuple[int, str]]] = {}

    def load(self, path: str) -> None:
        var_re = re.compile(r"\$var\s+\S+\s+(\d+)\s+(\S+)\s+(\S+)")
        with open(path, encoding="utf-8", errors="replace") as f:
            in_header = True
            time = 0
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if in_header:
                    if line.startswith("$var"):
                        m = var_re.match(line)
                        if m:
                            width, ident, name = int(m.group(1)), m.group(2), m.group(3)
                            self.id_name[ident] = re.sub(r"\[[^\]]*\]$", "", name)
                            self.id_width[ident] = width
                    elif line.startswith("$enddefinitions"):
                        in_header = False
                    continue
                if line.startswith("#"):
                    time = int(line[1:])
                elif line[0] in "bB":
                    value, ident = line[1:].split(None, 1)
                    self.changes.setdefault(ident.strip(), []).append((time, value))
                elif line[0] in "01xXzZ":
                    self.changes.setdefault(line[1:], []).append((time, line[0]))

    def short_name(self, ident: str) -> str:
        parts = self.id_name.get(ident, ident).split(".")
        return ".".join(parts[-2:]) if len(parts) > 1 else (parts[0] if parts else ident)

    def signals(self) -> list[str]:
        return sorted(self.short_name(i) for i in self.id_name)

    def match(self, patterns: list[str]) -> list[str]:
        # 同名信号在层次里会出现多次（TB 与 DUT 端口是同一根线，VCD 里是别名）。
        # 选变化最多、路径最短的那个，表格才看得清、值才是真的。
        best: dict[str, tuple[int, int, str]] = {}
        for ident, full in self.id_name.items():
            if patterns and not any(p in self.short_name(ident) for p in patterns):
                continue
            key = self.short_name(ident).split(".")[-1]
            score = (len(self.changes.get(ident, [])), -len(full))
            if key not in best or score > best[key][:2]:
                best[key] = (score[0], score[1], ident)
        return [ident for _, _, ident in sorted(best.values(), key=lambda x: self.short_name(x[2]))]

    def sample(self, ident: str, time: int) -> str | None:
        value = None
        for t, v in self.changes.get(ident, []):
            if t <= time:
                value = v
            else:
                break
        return value

    def rising_edges(self, clk_ident: str) -> list[int]:
        edges, prev = [], None
        for t, v in self.changes.get(clk_ident, []):
            if prev == "0" and v == "1":
                edges.append(t)
            prev = v
        return edges


def fmt(value: str | None, width: int) -> str:
    if value is None:
        return "-"
    if "x" in value.lower() or "z" in value.lower():
        return value
    if width == 1:
        return value
    try:
        return f"{int(value, 2):0{(width + 3) // 4}x}"
    except ValueError:
        return value


def main() -> int:
    ap = argparse.ArgumentParser(description="把 VCD 打印成文本波形")
    ap.add_argument("vcd")
    ap.add_argument("--signals", default="", help="逗号分隔的子串，例如 s_aw,s_w,s_b")
    ap.add_argument("--cycles", type=int, default=24, help="只看最后 N 个时钟上升沿")
    ap.add_argument("--first", type=int, default=None, help="只看最开始 N 个时钟上升沿")
    ap.add_argument("--from", dest="t_from", type=int, default=None)
    ap.add_argument("--to", dest="t_to", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--max-signals", type=int, default=20)
    ap.add_argument("--changes-only", action="store_true",
                    help="只打印信号发生变化的那些拍（默认全打，容易看麻）")
    ap.add_argument("--elide", type=int, default=28,
                    help="变化的行超过 N 行时，只留开头 8 行 + 最后若干行（默认 28）")
    args = ap.parse_args()

    if not os.path.exists(args.vcd):
        print(f"找不到 VCD：{args.vcd}")
        return 2
    vcd = Vcd()
    vcd.load(args.vcd)

    if args.list:
        for name in vcd.signals():
            print(name)
        return 0

    clk_ids = [i for i in vcd.id_name if vcd.short_name(i).split(".")[-1] == "clk"]
    if not clk_ids:
        print("波形里没有 clk 信号")
        return 2
    clk = max(clk_ids, key=lambda i: len(vcd.changes.get(i, [])))
    edges = vcd.rising_edges(clk)
    if args.t_from is not None:
        edges = [e for e in edges if e >= args.t_from]
    if args.t_to is not None:
        edges = [e for e in edges if e <= args.t_to]
    if not edges:
        print("没有找到时钟上升沿")
        return 2
    if args.first is not None:
        edges = edges[: args.first]
    else:
        edges = edges[-args.cycles:]

    patterns = [p.strip() for p in args.signals.split(",") if p.strip()]
    idents = vcd.match(patterns)
    if not idents:
        print("没有匹配到信号；用 --list 看看有哪些名字")
        return 2
    if len(idents) > args.max_signals:
        print(f"（匹配到 {len(idents)} 个信号，只显示前 {args.max_signals} 个；"
              f"用 --signals 缩小范围）")
        idents = idents[:args.max_signals]

    headers = ["t"] + [vcd.short_name(i) for i in idents]
    cells_all = [[fmt(vcd.sample(i, e), vcd.id_width.get(i, 1)) for i in idents] for e in edges]
    time_cells = [str(e) for e in edges]
    widths = [max(len("t"), *(len(c) for c in time_cells))]
    widths += [max(len(h), *(len(c[k]) for c in cells_all)) for k, h in enumerate(headers[1:])]

    def row(cells):
        return "  ".join(c.rjust(w) for c, w in zip(cells, widths))

    rows = []
    prev = None
    for e, cells in zip(edges, cells_all):
        if not args.changes_only or prev is None or cells != prev:
            rows.append((e, cells))
        prev = cells

    print(row(headers))
    print("  ".join("-" * w for w in widths))
    if args.elide and len(rows) > args.elide:
        head_n, tail_n = 8, args.elide - 8
        shown = rows[:head_n]
        skipped = len(rows) - head_n - tail_n
        for e, cells in shown:
            print(row([str(e)] + cells))
        print(f"…（省略中间 {skipped} 行：大部分是同一模式的重复）")
        shown = rows[-tail_n:]
        for e, cells in shown:
            print(row([str(e)] + cells))
    else:
        for e, cells in rows:
            print(row([str(e)] + cells))
    if args.changes_only and len(rows) < len(edges):
        print(f"（已折叠 {len(edges) - len(rows)} 拍没有变化的行；加 --all-cycles 可以看全部）")
    print("")
    print("说明：每一行是一个时钟上升沿，值是「该边沿到来之前」的值，也就是这一拍电路看到的输入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

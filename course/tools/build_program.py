"""把 RISC-V 源码编译成教学仓能装载的镜像。

流程（每一步都能在命令行里单独复现，方便教学）：

    .S / .c  --riscv64-unknown-elf-gcc-->  .elf
    .elf    --golden.elf（本仓库自己的解析器）-->  program.hex / data.hex / symbols.json

产出的镜像约定：
    program.hex  ITCM（0x0000_0000 起）每行一个 32 位字，直接喂给 $readmemh
    data.hex     DTCM（0x0001_0000 起）每行一个 32 位字
    symbols.json {符号名: 地址}，供测试脚本按名字读写变量（对齐上游 npusim 的用法）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from golden.elf import load_elf, parse_symbols  # noqa: E402

ITCM_BASE = 0x0000_0000
ITCM_WORDS = 2048
DTCM_BASE = 0x0001_0000
DTCM_WORDS = 8192

RV_PREFIX = os.environ.get("RISCV_PREFIX", "riscv64-unknown-elf-")


def tool(name: str) -> str:
    path = shutil.which(RV_PREFIX + name) or shutil.which(name)
    if not path:
        raise SystemExit(
            f"找不到 {RV_PREFIX}{name}。请先运行 ./learn doctor --install 安装 RISC-V 工具链。"
        )
    return path


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write("命令失败: " + " ".join(cmd) + "\n")
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(proc.returncode)


def build_elf(src: str, out_elf: str, linker: str, start: str, opt: str = "-O0",
              march: str = "rv32i") -> None:
    driver = tool("gcc")
    obj_dir = os.path.join(os.path.dirname(out_elf), "obj")
    os.makedirs(obj_dir, exist_ok=True)
    flags = [
        f"-march={march}",
        "-mabi=ilp32",
        "-nostdlib",
        "-ffreestanding",
        "-fno-builtin",
        opt,
        "-Wall",
    ]
    objs = []
    for path in (start, src):
        obj = os.path.join(obj_dir, os.path.basename(path) + ".o")
        run([driver] + flags + ["-c", path, "-o", obj])
        objs.append(obj)
    run(
        [driver, f"-march={march}", "-mabi=ilp32", "-nostdlib", "-nostartfiles",
         "-T", linker, "-o", out_elf]
        + objs
        + ["-lgcc"]
    )


def hex_words(blob: bytes) -> list[str]:
    words = []
    for i in range(0, len(blob), 4):
        chunk = blob[i : i + 4].ljust(4, b"\x00")
        words.append(f"{int.from_bytes(chunk, 'little'):08x}")
    return words


def write_hex(path: str, words: list[str]) -> None:
    trimmed = list(words)
    while trimmed and trimmed[-1] == "00000000":
        trimmed.pop()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(trimmed) + ("\n" if trimmed else ""))


@dataclass
class BuildResult:
    elf: str
    program_hex: str
    data_hex: str
    symbols: dict
    entry: int
    itcm_words: int


def build(src: str, out_dir: str, linker: str | None = None, start: str | None = None,
          opt: str = "-O0", march: str = "rv32i") -> BuildResult:
    """编译一个源文件并把 ELF 转成 RTL/黄金模型都能装载的镜像。"""
    here = os.path.dirname(os.path.abspath(__file__))
    link_dir = os.path.join(os.path.dirname(here), "lessons", "L01_scalar", "tests", "link")
    linker = linker or os.path.join(link_dir, "learn_tcm.ld")
    start = start or os.path.join(link_dir, "start.S")

    os.makedirs(out_dir, exist_ok=True)
    name = os.path.splitext(os.path.basename(src))[0]
    out_elf = os.path.join(out_dir, name + ".elf")
    build_elf(src, out_elf, linker, start, opt, march)

    with open(out_elf, "rb") as f:
        blob = f.read()
    img = load_elf(out_elf)
    itcm = img.bytes_at(ITCM_BASE, ITCM_WORDS * 4)
    dtcm = img.bytes_at(DTCM_BASE, DTCM_WORDS * 4)
    program_hex = os.path.join(out_dir, "program.hex")
    data_hex = os.path.join(out_dir, "data.hex")
    write_hex(program_hex, hex_words(itcm))
    write_hex(data_hex, hex_words(dtcm))
    symbols = parse_symbols(blob)
    with open(os.path.join(out_dir, "symbols.json"), "w", encoding="utf-8") as f:
        json.dump(symbols, f, indent=2, sort_keys=True)
    n_words = len(open(program_hex, encoding="utf-8").read().split())
    return BuildResult(
        elf=out_elf,
        program_hex=program_hex,
        data_hex=data_hex,
        symbols=symbols,
        entry=img.entry,
        itcm_words=n_words,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="编译教学例程并生成 RTL 可装载的镜像")
    ap.add_argument("src", help=".S 或 .c 源文件")
    ap.add_argument("--out-dir", required=True, help="产物目录")
    ap.add_argument("--linker", default=None)
    ap.add_argument("--start", default=None)
    ap.add_argument("-O", dest="opt", default="-O0")
    ap.add_argument("--march", default="rv32i", help="例如 rv32i / rv32im")
    args = ap.parse_args()

    result = build(args.src, args.out_dir, args.linker, args.start, args.opt, args.march)
    print(f"生成 {result.elf}")
    print(f"  program.hex  ITCM {result.itcm_words} 个字，入口 0x{result.entry:08x}")
    print("  data.hex     DTCM 初始数据")
    print("  symbols.json 符号表")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""环境自检：把「能不能学下去」的判断交给一条命令。

必需项：python3、iverilog、RISC-V 工具链（as/ld/gcc）
可选项：pandoc + weasyprint（渲染课程 PDF）、verilator、git
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

PASS, WARN, FAIL = "✅", "⚠️ ", "❌"

APT_PACKAGES = {
    "iverilog": "iverilog",
    "riscv-gcc": "gcc-riscv64-unknown-elf",
    "pdftotext": "poppler-utils",
}
APT_OPTIONAL = {
    "pandoc": "pandoc",
    "weasyprint": "weasyprint",
    "fonts-noto-cjk": "fonts-noto-cjk",
    "verilator": "verilator",
}


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def check() -> tuple[list[tuple[str, str, str]], bool]:
    """返回 ([(状态, 名称, 详情)], 是否全部必需项通过)。"""
    rows: list[tuple[str, str, str]] = []

    ok = sys.version_info >= (3, 9)
    rows.append((PASS if ok else FAIL, "python3", f"{sys.version.split()[0]}（需要 >= 3.9）"))

    iverilog = _which("iverilog")
    if iverilog:
        ok_v, out = _run(["iverilog", "-V"])
        ver = out.splitlines()[0] if out else ""
        rows.append((PASS, "iverilog", ver or iverilog))
    else:
        rows.append((FAIL, "iverilog", "缺少：sudo apt-get install iverilog"))

    gcc = _which("riscv64-unknown-elf-gcc")
    if gcc:
        ok_r, out = _run([gcc, "--version"])
        rows.append((PASS, "riscv64-unknown-elf-gcc", out.splitlines()[0] if out else gcc))
    else:
        rows.append((FAIL, "riscv64-unknown-elf-gcc", "缺少：sudo apt-get install gcc-riscv64-unknown-elf"))

    for name, cmd in (("pandoc", ["pandoc", "--version"]), ("weasyprint", ["weasyprint", "--version"])):
        path = _which(name)
        if path:
            _, out = _run(cmd)
            rows.append((PASS, name, out.splitlines()[0] if out else path))
        else:
            rows.append((WARN, name, f"可选（渲染 PDF 用）：sudo apt-get install {name}"))

    if _which("fc-list"):
        _, out = _run(["bash", "-lc", "fc-list :lang=zh-cn family | sort -u | head -1"])
        rows.append((PASS if out else WARN, "中文字体", out or "缺中文字体：sudo apt-get install fonts-noto-cjk"))

    verilator = _which("verilator")
    rows.append((PASS if verilator else WARN, "verilator", verilator or "可选：L10 用，sudo apt-get install verilator"))

    git = _which("git")
    rows.append((PASS if git else WARN, "git", git or "可选"))

    required_ok = all(status != FAIL for status, _, _ in rows)
    return rows, required_ok


def install_missing() -> int:
    pkgs = []
    if not _which("iverilog"):
        pkgs.append(APT_PACKAGES["iverilog"])
    if not _which("riscv64-unknown-elf-gcc"):
        pkgs.append(APT_PACKAGES["riscv-gcc"])
    if not _which("pandoc"):
        pkgs.append(APT_OPTIONAL["pandoc"])
    if not _which("weasyprint"):
        pkgs.append(APT_OPTIONAL["weasyprint"])
    has_cjk = False
    if _which("fc-list"):
        ok, out = _run(["bash", "-lc", "fc-list :lang=zh-cn family | head -1"])
        has_cjk = bool(ok and out)
    if not has_cjk:
        pkgs.append(APT_OPTIONAL["fonts-noto-cjk"])
    if not pkgs:
        print("没有缺失的必需组件。")
        return 0
    cmd = ["sudo", "apt-get", "install", "-y"] + pkgs
    print("将执行：", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def main(argv: list[str]) -> int:
    if "--install" in argv:
        return install_missing()
    rows, ok = check()
    width = max(len(name) for _, name, _ in rows)
    print("环境自检")
    print("")
    for status, name, detail in rows:
        print(f"  {status} {name.ljust(width)}  {detail}")
    print("")
    print("结论：" + ("环境就绪，可以开始 L00。" if ok else "还缺必需组件，运行 ./learn doctor --install 安装。"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

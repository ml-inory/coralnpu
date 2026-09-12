"""用 Icarus Verilog 编译并运行学员的 RTL，回收 trace 与内存镜像。

只依赖 `iverilog` / `vvp`（apt install iverilog 即可），因此教学循环是秒级的：
2 核笔记本上编译一个单周期核只要几百毫秒。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field


class RtlError(RuntimeError):
    pass


@dataclass
class SimResult:
    trace: list[tuple[int, int, int, int]] = field(default_factory=list)
    dmem: list[int] = field(default_factory=list)
    halted: bool = False
    cycles: int = 0
    timeout: bool = False
    log: str = ""


def have_iverilog() -> bool:
    return shutil.which("iverilog") is not None and shutil.which("vvp") is not None


def compile_rtl(rtl_files: list[str], out_vvp: str, top: str = "tb_cpu") -> None:
    if not have_iverilog():
        raise RtlError("找不到 iverilog / vvp，请运行 ./learn doctor --install")
    cmd = ["iverilog", "-g2012", "-o", out_vvp, "-s", top, "-Wno-timescale"] + list(rtl_files)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RtlError("iverilog 编译失败：\n" + proc.stdout + proc.stderr)
    warnings = (proc.stdout + proc.stderr).strip()
    if warnings:
        # 警告不影响判定，但保留下来方便学员自查
        with open(out_vvp + ".log", "w", encoding="utf-8") as f:
            f.write(warnings)


def run_sim(
    vvp_path: str,
    work_dir: str,
    program_hex: str,
    data_hex: str,
    max_cycles: int = 200_000,
    name: str = "sim",
    plusargs: dict | None = None,
) -> SimResult:
    os.makedirs(work_dir, exist_ok=True)
    trace_path = os.path.join(work_dir, f"{name}.trace")
    dmem_path = os.path.join(work_dir, f"{name}.dmem")
    cmd = [
        "vvp",
        vvp_path,
        f"+PROGRAM={program_hex}",
        f"+DATA={data_hex}",
        f"+TRACE={trace_path}",
        f"+DMEM={dmem_path}",
        f"+MAX_CYCLES={max_cycles}",
    ]
    for key, value in (plusargs or {}).items():
        cmd.append(f"+{key}={value}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    log = proc.stdout + proc.stderr

    res = SimResult(log=log)
    m = re.search(r"HALTED cycles=(\d+)", log)
    if m:
        res.halted = True
        res.cycles = int(m.group(1))

    if os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("TIMEOUT"):
                    res.timeout = True
                    continue
                parts = line.split()
                if len(parts) != 4:
                    raise RtlError(f"trace 行格式错误: {line!r}")
                try:
                    res.trace.append(
                        (int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), int(parts[3], 16))
                    )
                except ValueError as exc:  # X/Z 值通常意味着复位或写回逻辑有问题
                    raise RtlError(
                        f"trace 出现未知值（通常是 X/Z，说明复位或未初始化信号有问题）: {line!r}"
                    ) from exc

    if os.path.exists(dmem_path):
        with open(dmem_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if line:
                    res.dmem.append(int(line, 16))
    return res

"""极简 ELF32 加载器（只依赖 Python 标准库）。

教学仓需要把交叉编译器产出的裸机 ELF 装载进内存模型，这里只实现
必要的部分：解析 ELF 头、程序头表，取出 PT_LOAD 段。

字段布局参考 ELF 规范（ELF32, little endian, EM_RISCV=243）。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

EM_RISCV = 243
PT_LOAD = 1


@dataclass
class Segment:
    vaddr: int
    memsz: int
    data: bytes


@dataclass
class ElfImage:
    entry: int
    segments: list[Segment]

    def bytes_at(self, base: int, length: int) -> bytes:
        """按地址区间取镜像字节，未覆盖处补 0。"""
        buf = bytearray(length)
        for seg in self.segments:
            lo = max(base, seg.vaddr)
            hi = min(base + length, seg.vaddr + len(seg.data))
            if lo < hi:
                off = lo - base
                src = lo - seg.vaddr
                buf[off : off + (hi - lo)] = seg.data[src : src + (hi - lo)]
        return bytes(buf)

    def symbols(self, elf_bytes: bytes) -> dict[str, int]:
        return parse_symbols(elf_bytes)


def _cstr(tab: bytes, off: int) -> str:
    end = tab.find(b"\x00", off)
    return tab[off:end].decode("utf-8", "replace") if end >= 0 else ""


def parse_symbols(elf_bytes: bytes) -> dict[str, int]:
    """解析 .symtab，返回 {符号名: 地址}。"""
    if elf_bytes[:4] != b"\x7fELF":
        raise ValueError("不是 ELF 文件")
    is_64 = elf_bytes[4] == 2
    if is_64:
        raise ValueError("教学仓只支持 ELF32")
    (e_shoff,) = struct.unpack_from("<I", elf_bytes, 0x20)
    (e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from("<HHH", elf_bytes, 0x2E)

    def sh(i: int):
        off = e_shoff + i * e_shentsize
        name, typ, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from(
            "<IIIIIIIIII", elf_bytes, off
        )
        return dict(
            name=name, type=typ, addr=addr, offset=offset, size=size,
            link=link, entsize=entsize,
        )

    shstr = sh(e_shstrndx)
    shstr_tab = elf_bytes[shstr["offset"] : shstr["offset"] + shstr["size"]]
    out: dict[str, int] = {}
    for i in range(e_shnum):
        s = sh(i)
        if s["type"] != 2:  # SHT_SYMTAB
            continue
        strtab = sh(s["link"])
        str_tab = elf_bytes[strtab["offset"] : strtab["offset"] + strtab["size"]]
        entsize = s["entsize"] or 16
        for j in range(s["size"] // entsize):
            off = s["offset"] + j * entsize
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                "<IIIBBH", elf_bytes, off
            )
            if st_name == 0:
                continue
            name = _cstr(str_tab, st_name)
            if name and name not in out:
                out[name] = st_value
    return out


def load_elf(path: str) -> ElfImage:
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:4] != b"\x7fELF":
        raise ValueError(f"{path} 不是 ELF 文件")
    ei_class, ei_data = blob[4], blob[5]
    if ei_class != 1:
        raise ValueError("只支持 ELF32（请用 -march=rv32* 编译）")
    if ei_data != 1:
        raise ValueError("只支持小端 ELF")
    (e_type, e_machine) = struct.unpack_from("<HH", blob, 0x10)
    if e_machine != EM_RISCV:
        raise ValueError(f"ELF machine={e_machine}，不是 RISC-V（应为 {EM_RISCV}）")
    (e_entry, e_phoff, e_shoff) = struct.unpack_from("<III", blob, 0x18)
    (e_phentsize, e_phnum) = struct.unpack_from("<HH", blob, 0x2A)

    segs: list[Segment] = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        (p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz) = struct.unpack_from(
            "<IIIIII", blob, off
        )
        if p_type != PT_LOAD:
            continue
        data = blob[p_offset : p_offset + p_filesz]
        segs.append(Segment(vaddr=p_vaddr, memsz=p_memsz, data=data))
    return ElfImage(entry=e_entry, segments=segs)


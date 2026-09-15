/* CoralNPU 教学仓 L04 链接脚本
 *
 * 和 L01 的 learn_tcm.ld 只有一处不同：ITCM 的起点是 0x100 而不是 0。
 *
 * 为什么要这样链接？因为 L04 的主角之一是 PC_START：
 *   1. 程序被链接到 0x100，ELF 的入口（_start）也就是 0x100；
 *   2. 主机在第 2 步把 0x100 写进 PC_START；
 *   3. 核心复位时把 PC 装载成 PC_START。
 * 如果 PC_START 没接对，核心会从 0 开始取指（那里全是 0，即非法指令），
 * trace 的第一条就对不上——这正是这条用例想抓的错误。
 *
 * ITCM 容量仍然是 8 KB（0x0000_0000 – 0x0000_1FFF），程序放在它的后半段。
 */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
  ITCM (rx) : ORIGIN = 0x00000100, LENGTH = 8K - 0x100
  DTCM (rw) : ORIGIN = 0x00010000, LENGTH = 32K
}

SECTIONS
{
  .text : ALIGN(16)
  {
    KEEP(*(.text._start))
    *(.text .text.*)
  } > ITCM

  .rodata : ALIGN(16)
  {
    *(.rodata .rodata.*)
    *(.srodata .srodata.*)
  } > ITCM

  .data : ALIGN(16)
  {
    __data_start = .;
    *(.sdata .sdata.*)
    *(.data .data.*)
    __data_end = .;
  } > DTCM

  .bss (NOLOAD) : ALIGN(16)
  {
    __bss_start = .;
    *(.sbss .sbss.*)
    *(.bss .bss.*)
    *(COMMON)
    __bss_end = .;
  } > DTCM

  __stack_top = ORIGIN(DTCM) + LENGTH(DTCM) - 16;
  __global_pointer$ = ORIGIN(DTCM) + 0x800;

  /DISCARD/ :
  {
    *(.comment)
    *(.note .note.*)
    *(.riscv.attributes)
    *(.eh_frame .eh_frame.*)
  }
}

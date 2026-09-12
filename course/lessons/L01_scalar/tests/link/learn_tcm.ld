/* CoralNPU 教学仓 L01 链接脚本
 *
 * 地址与上游 CoralNPU 默认配置一致（见 doc/integration_guide.md 的内存映射）：
 *   ITCM: 0x0000_0000, 8 KB,  只存指令与只读数据
 *   DTCM: 0x0001_0000, 32 KB, 栈、全局变量、堆
 *
 * 上游的模板是 toolchain/coralnpu_tcm.ld.tpl，这里做了大幅简化：
 * 去掉 init/fini array、tdata/tbss、外部内存段，只保留单周期核能跑通的部分。
 */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
  ITCM (rx) : ORIGIN = 0x00000000, LENGTH = 8K
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


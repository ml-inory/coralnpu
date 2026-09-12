/* CoralNPU 教学仓 L01 启动代码（上游 toolchain/crt/coralnpu_start.S 的精简版）
 *
 * 上游版本会初始化 CSR、init/fini array、异常向量，并用 mpause 停机；
 * 那些属于 L03（异常与 CSR）的内容，这里只保留单周期核必须的部分：
 *
 *   1. 设置栈指针到 DTCM 顶部
 *   2. 调用 main
 *   3. main 返回 0 → mpause 停机；返回非 0 → ebreak（方便调试失败原因）
 */

  .section .text._start
  .balign 4
  .global _start
  .weak _start
  .type _start, @function
_start:
  .option push
  .option norelax
  la    sp, __stack_top
  la    gp, __global_pointer$
  .option pop

  call  main

  bnez  a0, .Lfail

  /* .word 0x08000073 == mpause，与 hdl/chisel/src/coralnpu/scalar/Decode.scala:1188 一致 */
  .word 0x08000073

.Lfail:
  ebreak
  j     .Lfail

  .size _start, . - _start

/* L04 测试 1：5 步启动流程 + 数据访问走 AXI 主接口
 *
 * 这个程序本身很普通：几次算术、几次 load/store。它的意义在于
 * "怎么跑起来的"——主机必须先按顺序
 *   ① 写 ITCM  ② 写 PC_START  ③ 释放时钟门控  ④ 释放复位  ⑤ 轮询 STATUS
 * 才能让它开始执行；而且它的每一次 load/store 都要经过 AXI 主接口。
 *
 * 程序链接在 0x100（见 tests/link/learn_tcm_0x100.ld），所以 PC_START 必须是 0x100。
 */

  .section .data
  .align 4
  .globl out
out:
  .word 0, 0, 0, 0, 0, 0

  .section .rodata
  .align 4
const_val:
  .word 0x5A5A5A5A

  .section .text
  .globl main
main:
  la    s5, out

  /* 算术（不碰总线） */
  li    t0, 0x12
  li    t1, 0x30
  add   t2, t0, t1
  sw    t2, 0(s5)             /* out[0] = 0x42 */

  /* load 回来再存一次：读和写都要走 AXI 主接口 */
  lw    t3, 0(s5)
  sw    t3, 4(s5)             /* out[1] = 0x42 */
  addi  t4, t3, -2
  sw    t4, 8(s5)             /* out[2] = 0x40 */

  /* 读 ITCM 里的只读数据：这一笔由外壳内部服务，不走 AXI */
  la    t5, const_val
  lw    t6, 0(t5)
  sw    t6, 12(s5)            /* out[3] = 0x5A5A5A5A */

  li    a0, 0
  ret

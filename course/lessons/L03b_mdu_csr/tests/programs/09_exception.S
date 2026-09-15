/* L03b 测试 3：异常进入与返回
 *
 * 流程：
 *   1. 把 mtvec 指向 handler；
 *   2. ecall 触发异常（mcause=11）→ 跳到 handler；
 *   3. handler 记录 mepc/mcause，把 mepc+4，mret 返回；
 *   4. 执行一条非法指令（.word 0）触发异常（mcause=2）→ 同样的流程；
 *   5. 最后正常结束。
 *
 * out[] 布局：
 *   out[0] = 0x111（异常前）
 *   out[1] = 0x333（第一次 mret 之后）
 *   out[2] = 0x555（第二次 mret 之后）
 *   out[4],out[5] = 第一次异常的 mepc / mcause
 *   out[6],out[7] = 第二次异常的 mepc / mcause
 */

  .section .data
  .align 4
  .globl out
out:
  .word 0, 0, 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    t0, handler
  csrw  mtvec, t0
  la    s5, out

  li    t1, 0x111
  sw    t1, 0(s5)

  ecall                       /* 异常 1：mcause = 11 */

  li    t1, 0x333
  sw    t1, 4(s5)

  .word 0x00000000            /* 异常 2：非法指令，mcause = 2 */

  li    t1, 0x555
  sw    t1, 8(s5)

  li    a0, 0
  ret

/* 异常处理程序 */
handler:
  csrr  t2, mepc
  csrr  t3, mcause

  /* 用 mscratch 记第几次异常，把结果写进 out[4]/out[6] */
  csrr  t4, mscratch
  addi  t4, t4, 1
  csrw  mscratch, t4
  slli  t5, t4, 3
  addi  t5, t5, 8
  la    s6, out
  add   s6, s6, t5
  sw    t2, 0(s6)             /* mepc */
  sw    t3, 4(s6)             /* mcause */

  /* mepc += 4：跳过触发异常的指令，再返回 */
  addi  t2, t2, 4
  csrw  mepc, t2
  mret

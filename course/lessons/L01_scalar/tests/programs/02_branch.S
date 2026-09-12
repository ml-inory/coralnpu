/* L01 测试 2：6 种条件分支 + 循环 + 跳转
 *
 * 结果 = 1..n 累加和，用来验证分支的「跳/不跳」两个方向都正确。
 */

  .section .data
  .align 4
  .globl result
result:
  .word 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, result

  li    t0, 10              /* n = 10 */
  li    t1, 0               /* sum = 0 */
  li    t2, 1               /* i = 1 */
loop:
  bgt   t2, t0, loop_end    /* 伪指令 → blt */
  add   t1, t1, t2
  addi  t2, t2, 1
  j     loop
loop_end:
  sw    t1, 0(s5)           /* sum(1..10) = 55 */

  /* beq / bne */
  li    t3, 5
  beq   t3, t3, beq_taken
  li    t4, 111             /* 不应执行 */
beq_taken:
  sw    t3, 4(s5)
  bne   t3, t0, bne_taken
  li    t4, 222             /* 不应执行 */
bne_taken:

  /* blt / bge（有符号） */
  li    t4, -1
  li    t5, 1
  blt   t4, t5, blt_taken
  li    t6, 333             /* 不应执行 */
blt_taken:
  sw    t4, 8(s5)
  bge   t5, t4, bge_taken
  li    t6, 444             /* 不应执行 */
bge_taken:

  /* bltu / bgeu（无符号） */
  li    t6, 1
  bgeu  t4, t6, bgeu_taken  /* 0xFFFFFFFF >= 1 */
  li    s0, 555             /* 不应执行 */
bgeu_taken:
  sw    t6, 12(s5)
  bltu  t6, t4, bltu_taken
  li    s0, 666             /* 不应执行 */
bltu_taken:
  sw    s0, 16(s5)

  li    a0, 0
  ret


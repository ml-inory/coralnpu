/* L01 测试 4：函数调用、栈、jal/jalr、乘加循环
 *
 * 计算 1 + 2 + ... + 10 用递归实现，强制用到栈和返回地址保存。
 */

  .section .data
  .align 4
  .globl result
result:
  .word 0, 0, 0, 0

  .section .text

/* int sum_to(int n)：递归求和 */
  .globl sum_to
sum_to:
  addi  sp, sp, -8
  sw    ra, 4(sp)
  sw    a0, 0(sp)
  li    t0, 1
  ble   a0, t0, base        /* n <= 1 → 返回 n */

  addi  a0, a0, -1
  call  sum_to
  lw    t1, 0(sp)           /* 取回原来的 n */
  add   a0, a0, t1
  lw    ra, 4(sp)
  addi  sp, sp, 8
  ret

base:
  lw    ra, 4(sp)
  addi  sp, sp, 8
  ret

/* int fib(int n)：迭代斐波那契 */
  .globl fib
fib:
  li    t0, 0               /* a */
  li    t1, 1               /* b */
  li    t2, 0               /* i */
fib_loop:
  bge   t2, a0, fib_done
  add   t3, t0, t1
  mv    t0, t1
  mv    t1, t3
  addi  t2, t2, 1
  j     fib_loop
fib_done:
  mv    a0, t0
  ret

  .globl main
main:
  addi  sp, sp, -4          /* main 里还会调用别的函数，必须先保存 ra */
  sw    ra, 0(sp)
  la    s5, result

  li    a0, 10
  call  sum_to
  sw    a0, 0(s5)           /* sum_to(10) = 55 */

  li    a0, 12
  call  fib
  sw    a0, 4(s5)           /* fib(12) = 144 */

  /* 用 jalr 直接跳到下一行并检查返回地址 */
  la    t0, after_jalr
  jalr  t1, t0, 0           /* t1 = PC+4 */
after_jalr:
  sw    t1, 8(s5)

  lw    ra, 0(sp)
  addi  sp, sp, 4
  li    a0, 0
  ret

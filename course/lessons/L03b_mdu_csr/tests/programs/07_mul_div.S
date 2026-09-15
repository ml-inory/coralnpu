/* L03b 测试 1：M 扩展（乘除法）
 *
 * 覆盖 8 条指令 + 三个边界情况：
 *   * 除零：div 返回 -1，rem 返回被除数
 *   * 溢出：INT_MIN / -1 = INT_MIN，rem = 0
 *   * 有符号/无符号的高位乘法结果不同
 */

  .section .data
  .align 4
  .globl out
out:
  .word 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, out

  /* mul：低 32 位 */
  li    t0, 6
  li    t1, 7
  mul   t2, t0, t1
  sw    t2, 0(s5)             /* 42 */

  li    t0, -3
  li    t1, 5
  mul   t2, t0, t1
  sw    t2, 4(s5)             /* -15 */

  /* 高位乘法：同一个操作数对，有符号/无符号结果不同 */
  li    t0, 0x80000000        /* 有符号看作 INT_MIN，无符号看作 2^31 */
  li    t1, 2
  mulh  t2, t0, t1
  sw    t2, 8(s5)             /* 有符号高位：-1（0xFFFFFFFF） */
  mulhu t2, t0, t1
  sw    t2, 12(s5)            /* 无符号高位：1 */
  mulhsu t2, t0, t1
  sw    t2, 16(s5)            /* 有符号×无符号高位：-1 */

  /* 除法：向零取整 */
  li    t0, -7
  li    t1, 2
  div   t2, t0, t1
  sw    t2, 20(s5)            /* -3 */
  rem   t2, t0, t1
  sw    t2, 24(s5)            /* -1 */

  li    t0, 7
  li    t1, -2                /* 无符号看是 0xFFFFFFFE */
  divu  t2, t0, t1
  sw    t2, 28(s5)            /* 0 */
  remu  t2, t0, t1
  sw    t2, 32(s5)            /* 7 */

  /* 除零 */
  li    t0, 123
  li    t1, 0
  div   t2, t0, t1
  sw    t2, 36(s5)            /* -1 */
  rem   t2, t0, t1
  sw    t2, 40(s5)            /* 123 */

  /* 溢出：INT_MIN / -1 */
  li    t0, 0x80000000
  li    t1, -1
  div   t2, t0, t1
  sw    t2, 44(s5)            /* 0x80000000 */
  rem   t2, t0, t1
  sw    t2, 48(s5)            /* 0 */

  li    a0, 0
  ret


/* L02 测试：非对齐访存
 *
 * L01 的核只会做对齐访问；这里每一条都会跨字或落在字内偏移上，
 * LSU 必须把它们拆成两次对齐事务（或做字节重排）才能得到正确结果。
 *
 * 初始内存：
 *   buf[0] = 0x11223344   → 字节 44 33 22 11
 *   buf[1] = 0x55667788   → 字节 88 77 66 55
 */

  .section .data
  .align 4
  .globl buf
buf:
  .word 0x11223344
  .word 0x55667788
  .word 0x00000000

  .align 4
  .globl out
out:
  .word 0, 0, 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, buf
  la    s6, out

  /* 1) 非对齐半字存储：写在 byte1、byte2 上（字内，不跨字） */
  li    t0, 0xBEEF
  sh    t0, 1(s5)
  lw    t1, 0(s5)
  sw    t1, 0(s6)             /* 期望 0x11BEEF44 */

  /* 2) 非对齐字存储：byte3..byte6，跨两个 32 位字 */
  li    t2, 0xAABBCCDD
  sw    t2, 3(s5)
  lw    t3, 0(s5)
  sw    t3, 4(s6)             /* 期望 0xDDBEEF44 */
  lw    t4, 4(s5)
  sw    t4, 8(s6)             /* 期望 0x55AABBCC */

  /* 3) 非对齐字载入：byte1..byte4，跨字读取后拼接 */
  lw    t5, 1(s5)
  sw    t5, 12(s6)            /* 期望 0xCCDDBEEF */

  /* 4) 非对齐半字载入：有符号 / 无符号 */
  lh    t6, 3(s5)
  sw    t6, 16(s6)            /* 期望 0xFFFFCCDD */
  lhu   s0, 3(s5)
  sw    s0, 20(s6)            /* 期望 0x0000CCDD */

  /* 5) 字内偏移的字节载入 */
  lb    s1, 7(s5)
  sw    s1, 24(s6)            /* 期望 0x00000055 */
  lbu   s2, 7(s5)
  sw    s2, 28(s6)            /* 期望 0x00000055 */

  li    a0, 0
  ret

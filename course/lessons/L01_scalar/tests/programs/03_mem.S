/* L01 测试 3：字节/半字/字 的载入与存储、符号扩展
 */

  .section .data
  .align 4
  .globl buf
buf:
  .word 0x00000000
  .word 0x00000000
  .word 0x00000000
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

  /* 字存储 + 字载入 */
  li    t0, 0xDEADBEEF
  sw    t0, 0(s5)
  lw    t1, 0(s5)
  sw    t1, 0(s6)

  /* 字节存储：只改最低字节 */
  li    t2, 0x55
  sb    t2, 1(s5)
  lw    t3, 0(s5)
  sw    t3, 4(s6)

  /* 半字存储：改低半字 */
  li    t4, 0x1234
  sh    t4, 2(s5)
  lw    t5, 0(s5)
  sw    t5, 8(s6)

  /* 符号扩展：lb 取 0x55 → 85；lbu 同一个字节也是 85 */
  lb    t6, 1(s5)
  sw    t6, 12(s6)
  lbu   s0, 1(s5)
  sw    s0, 16(s6)

  /* 负字节：写 0x80，lb 得到 -128，lbu 得到 128 */
  li    t0, 0x80
  sb    t0, 3(s5)
  lb    t1, 3(s5)
  sw    t1, 20(s6)
  lbu   t2, 3(s5)
  sw    t2, 24(s6)

  /* 半字符号扩展：写 0x8000 → lh = -32768，lhu = 32768 */
  li    t3, 0x8000
  sh    t3, 4(s5)
  lh    t4, 4(s5)
  sw    t4, 28(s6)
  lhu   t5, 4(s5)
  sw    t5, 32(s6)

  li    a0, 0
  ret


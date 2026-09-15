/* L04 测试 2：数据通路的宽度与掩码（每一笔都走 AXI 主接口）
 *
 * 字节/半字/非对齐访问由 L02 的 LSU 拆成多次总线事务，
 * 这里正好用来压 AX 主接口的 WSTRB 与地址对齐处理。
 */

  .section .data
  .align 4
  .globl buf
buf:
  .word 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, buf

  li    t0, 0x12345678
  sw    t0, 0(s5)             /* buf[0] = 0x12345678 */

  li    t1, 0xAB
  sb    t1, 4(s5)             /* 字节写 */

  li    t2, 0xCDEF
  sh    t2, 6(s5)             /* 半字写（跨字边界） */

  lw    t3, 0(s5)
  sw    t3, 8(s5)             /* 读回来再存 */

  lbu   t4, 4(s5)
  sw    t4, 12(s5)            /* 无符号字节读 = 0x000000AB */

  lhu   t5, 6(s5)
  sw    t5, 16(s5)            /* 无符号半字读 = 0x0000CDEF */

  lb    t6, 4(s5)
  sw    t6, 20(s5)            /* 有符号字节读 = 0xFFFFFFAB */

  li    a0, 0
  ret

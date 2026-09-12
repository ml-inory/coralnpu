/* L01 测试 1：整数算术、逻辑、移位、立即数指令
 *
 * 每条指令的结果都写进 DTCM 的 result 数组，检查器会同时对比
 * 「trace 逐指令」和「DTCM 全量内容」，任何一个字写错都会被抓住。
 */

  .section .data
  .align 4
  .globl result
result:
  .word 0, 0, 0, 0, 0, 0, 0, 0
  .word 0, 0, 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, result          /* s5 = result 基地址 */

  li    t0, 1234            /* addi：正立即数 */
  li    t1, -56             /* addi：负立即数（符号扩展） */
  li    t2, 0x7FFFFFFF      /* lui + addi */
  li    t3, 0x80000000      /* 只有 lui，负数 */

  add   t4, t0, t1
  sw    t4, 0(s5)
  sub   t4, t0, t1
  sw    t4, 4(s5)
  xor   t4, t0, t1
  sw    t4, 8(s5)
  or    t4, t0, t1
  sw    t4, 12(s5)
  and   t4, t0, t1
  sw    t4, 16(s5)

  sll   t4, t0, t1          /* 移位量取低 5 位：-56 & 31 = 8 */
  sw    t4, 20(s5)
  srl   t4, t0, t1
  sw    t4, 24(s5)
  sra   t4, t1, t1          /* 算术右移：符号位参与 */
  sw    t4, 28(s5)

  slt   t4, t1, t0          /* 有符号比较：-56 < 1234 → 1 */
  sw    t4, 32(s5)
  sltu  t4, t1, t0          /* 无符号比较：0xFFFFFFC8 < 1234 → 0 */
  sw    t4, 36(s5)

  /* OP-IMM 系列 */
  addi  t4, t0, -100
  sw    t4, 40(s5)
  slti  t4, t1, 0
  sw    t4, 44(s5)
  sltiu t4, t1, -1          /* 无符号：0xFFFFFFC8 < 0xFFFFFFFF → 1 */
  sw    t4, 48(s5)
  xori  t4, t0, 0xFF
  sw    t4, 52(s5)
  ori   t4, t3, 0x0F
  sw    t4, 56(s5)
  andi  t4, t3, 0xF0
  sw    t4, 60(s5)

  slli  t4, t0, 4
  sw    t4, 64(s5)
  srli  t4, t3, 4           /* 逻辑右移：高位补 0 */
  sw    t4, 68(s5)
  srai  t4, t3, 4           /* 算术右移：高位补符号 */
  sw    t4, 72(s5)

  /* LUI 与 AUIPC */
  lui   t4, 0x12345
  sw    t4, 76(s5)
  auipc t4, 0               /* 取出当前 PC */
  sw    t4, 80(s5)

  li    a0, 0
  ret


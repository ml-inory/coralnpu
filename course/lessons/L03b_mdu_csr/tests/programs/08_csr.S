/* L03b 测试 2：CSR 指令（Zicsr）
 *
 * 覆盖 csrrw / csrrs / csrrc 与它们的立即数形式，以及：
 *   * set/clear 时 rs1=x0 不应写 CSR（规范要求，避免读副作用）；
 *   * misa 是只读寄存器，写它无效。
 */

  .section .data
  .align 4
  .globl out
out:
  .word 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

  .section .text
  .globl main
main:
  la    s5, out

  /* csrrw：读出旧值，写入新值 */
  li    t0, 0x12345678
  csrrw t1, mtvec, t0
  sw    t1, 0(s5)             /* 旧 mtvec = 0 */
  csrr  t2, mtvec
  sw    t2, 4(s5)             /* 新 mtvec = 0x12345678 */

  /* csrrs：置位 */
  li    t0, 0xF0
  csrrs t3, mstatus, t0
  sw    t3, 8(s5)             /* 旧 mstatus = 0 */
  csrr  t4, mstatus
  sw    t4, 12(s5)            /* 0xF0 */

  /* csrrc：清位 */
  li    t0, 0x30
  csrrc t5, mstatus, t0
  sw    t5, 16(s5)            /* 0xF0 */
  csrr  t6, mstatus
  sw    t6, 20(s5)            /* 0xC0 */

  /* 立即数形式：csrrwi / csrrsi */
  csrrwi s0, mscratch, 5
  sw    s0, 24(s5)            /* 旧 mscratch = 0 */
  csrr  s1, mscratch
  sw    s1, 28(s5)            /* 5 */

  li    t0, 0x0F
  csrrsi s2, mscratch, 0x0F
  sw    s2, 32(s5)            /* 旧值 5 */
  csrr  s3, mscratch
  sw    s3, 36(s5)            /* 5 | 15 = 15 */

  /* rs1=x0 的 csrrs 不写：读 mstatus 不改变它 */
  csrrs s4, mstatus, x0
  sw    s4, 40(s5)            /* 0xC0 */
  csrr  s6, mstatus
  sw    s6, 44(s5)            /* 仍然是 0xC0 */

  /* misa 只读 */
  csrr  s7, misa
  sw    s7, 48(s5)            /* 0x40001100 */

  li    a0, 0
  ret


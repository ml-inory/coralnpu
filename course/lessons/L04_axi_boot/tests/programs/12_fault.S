/* L04 测试 3：没有安装处理程序的异常 → STATUS.FAULT
 *
 * 核心（courses 提供的 core_l04）在"进入异常但 mtvec 仍然是 0"时会置位 o_fault
 * 并冻结。主机第 5 步轮询 STATUS 时就能看到 FAULT=1，而不是等到仿真超时。
 *
 * 注意：这条用例没有黄金模型对照（黄金模型会一直执行地址 0 处的非法指令），
 * 检查器只校验"主机确实观察到了 FAULT"。
 */

  .section .data
  .align 4
  .globl marker
marker:
  .word 0

  .section .text
  .globl main
main:
  la    s5, marker
  li    t0, 0x1BADB002
  sw    t0, 0(s5)             /* 先把证据写进 DTCM（这笔要走 AXI） */

  .word 0                     /* 非法指令：trap 到 mtvec=0 → core_l04 报 fault */

  li    a0, 0
  ret

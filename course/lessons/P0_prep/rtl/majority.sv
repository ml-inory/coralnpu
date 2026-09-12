// P0 模块 C 练习：三输入多数表决器（组合逻辑）
//
// 任务：当 a、b、c 里至少有两个为 1 时，y 输出 1，否则 0。
//
// 真值表（第三个是 y）：
//   a b c | y        a b c | y
//   0 0 0 | 0        1 0 0 | 0
//   0 0 1 | 0        1 0 1 | 1
//   0 1 0 | 0        1 1 0 | 1
//   0 1 1 | 1        1 1 1 | 1
//
// 要求：只用组合逻辑（assign 或 always_comb），不要用时钟。

`default_nettype none

module majority (
    input  logic a,
    input  logic b,
    input  logic c,
    output logic y
);

  // TODO 1：实现「至少两个输入为 1」
  //   提示：任意两个输入相与，再把三种组合或起来
  assign y = 1'b0;

endmodule

`default_nettype wire


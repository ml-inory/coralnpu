// P0 模块 D 练习之二：带复位和使能的 8 位计数器（时序逻辑）
//
// 任务：
//   * rst=1 时，q 清 0（复位优先）
//   * 每个时钟上升沿：en=1 时 q 加 1；en=0 时 q 保持不变
//   * 加法在 8 位里自然回绕（255 再加 1 变 0），不需要额外处理
//
// 这是「时序逻辑」的标准写法：所有变化都发生在时钟边沿。

`default_nettype none

module counter (
    input  logic       clk,
    input  logic       rst,
    input  logic       en,
    output logic [7:0] q
);

  // TODO 3：用 always_ff @(posedge clk) 实现
  //   结构是：if (rst) ... else if (en) ...
  always_ff @(posedge clk) begin
    q <= 8'h00;
  end

endmodule

`default_nettype wire


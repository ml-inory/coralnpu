// P0 模块 D 参考实现：带复位和使能的 8 位计数器

`default_nettype none

module counter (
    input  logic       clk,
    input  logic       rst,
    input  logic       en,
    output logic [7:0] q
);

  always_ff @(posedge clk) begin
    if (rst) q <= 8'h00;
    else if (en) q <= q + 8'd1;
  end

endmodule

`default_nettype wire


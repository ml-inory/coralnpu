// P0 模块 D 参考实现：4 选 1 多路选择器

`default_nettype none

module mux4 (
    input  logic [31:0] d0,
    input  logic [31:0] d1,
    input  logic [31:0] d2,
    input  logic [31:0] d3,
    input  logic [1:0]  sel,
    output logic [31:0] y
);

  always_comb begin
    case (sel)
      2'd0: y = d0;
      2'd1: y = d1;
      2'd2: y = d2;
      default: y = d3;
    endcase
  end

endmodule

`default_nettype wire


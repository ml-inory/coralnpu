// CoralNPU 教学仓 L00 参考实现：32 位 ALU

`default_nettype none

module alu32 (
    input  logic [31:0] a,
    input  logic [31:0] b,
    input  logic [3:0]  op,
    output logic [31:0] y,
    output logic        zero
);

  logic [4:0] shamt;
  assign shamt = b[4:0];

  // 算术右移：逻辑右移后把高 shamt 位填成符号位
  logic [31:0] sra_result;
  assign sra_result = (a >> shamt) | ({32{a[31]}} & ~(32'hFFFF_FFFF >> shamt));

  always_comb begin
    case (op)
      4'd0: y = a + b;
      4'd1: y = a - b;
      4'd2: y = a << shamt;
      4'd3: y = ($signed(a) < $signed(b)) ? 32'd1 : 32'd0;
      4'd4: y = (a < b) ? 32'd1 : 32'd0;
      4'd5: y = a ^ b;
      4'd6: y = a >> shamt;
      4'd7: y = sra_result;
      4'd8: y = a | b;
      default: y = a & b;
    endcase
  end

  assign zero = (y == 32'h0);

endmodule

`default_nettype wire


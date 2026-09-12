// CoralNPU 教学仓 L00 热身作业：32 位 ALU
//
// 这个模块在 L01 里会直接用于单周期核的数据通路，所以现在就把语义写对。
// 你需要补齐 3 个 TODO，最终 ./learn check L00 会随机撒 2000 组向量验证。
//
// 操作码定义（课程约定，和上游 Alu.scala 的 opcode 含义一致）：
//   0=ADD  1=SUB  2=SLL  3=SLT(有符号)  4=SLTU(无符号)
//   5=XOR  6=SRL  7=SRA(算术)           8=OR   9=AND
//
// 注意：移位量只取 b 的低 5 位（RV32 规范如此）。

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

  // TODO 1：实现算术右移
  //   提示：不要用 $signed(a) >>> shamt，它在无符号上下文里会退化成逻辑移位。
  //         用 (a >> shamt) | (符号填充掩码) 的方式，掩码 = {32{a[31]}} & ~(32'hFFFF_FFFF >> shamt)
  logic [31:0] sra_result;
  assign sra_result = (a >> shamt) | ({32{a[31]}} & ~(32'hFFFF_FFFF >> shamt));  // TODO

  // TODO 2：把 op 译码成 y
  always_comb begin
    case (op)
      4'd0: y = a + b;
      4'd1: y = a - b;  // TODO: 减法
      4'd2: y = a << shamt;  // TODO: 逻辑左移
      4'd3: y = ($signed(a) < $signed(b)) ? 32'd1 : 32'd0;  // TODO: 有符号比较，结果 0/1
      4'd4: y = (a < b) ? 32'd1 : 32'd0;  // TODO: 无符号比较，结果 0/1
      4'd5: y = a ^ b;  // TODO: 异或
      4'd6: y = a >> shamt;  // TODO: 逻辑右移
      4'd7: y = sra_result;
      4'd8: y = a | b;  // TODO: 或
      default: y = a & b;  // AND
    endcase
  end

  // TODO 3：zero 标志：y 全 0 时置 1
  assign zero = (y == 32'd0) ? 1 : 0;

endmodule

`default_nettype wire


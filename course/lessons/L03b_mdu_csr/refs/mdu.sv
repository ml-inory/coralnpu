// CoralNPU 教学仓 L03b 参考实现：M 扩展（乘除法单元）
//
// op 直接用指令的 funct3 编码：
//   000 mul     低 32 位
//   001 mulh    有符号 × 有符号 的高 32 位
//   010 mulhsu  有符号 × 无符号 的高 32 位
//   011 mulhu   无符号 × 无符号 的高 32 位
//   100 div     有符号除法（向零取整）
//   101 divu    无符号除法
//   110 rem     有符号取余（符号跟被除数）
//   111 remu    无符号取余
//
// 三个必须记住的边界情况（RISC-V 规范定义，不能靠 Verilog 的默认行为）：
//   * 除零：div/divu 返回全 1，rem/remu 返回被除数
//   * 溢出：INT_MIN / -1 = INT_MIN，rem = 0
//   * 高位乘法：有符号/无符号要把操作数按不同方式扩展到 64 位

`default_nettype none

module mdu (
    input  logic [31:0] a,
    input  logic [31:0] b,
    input  logic [2:0]  op,
    output logic [31:0] y
);

  localparam logic [31:0] INT_MIN = 32'h8000_0000;

  logic signed [31:0] sa, sb;
  logic        [63:0] uprod;
  logic signed [63:0] sprod, sprod_su;

  assign sa = a;
  assign sb = b;
  assign uprod    = a * b;                      // 64 位无符号乘积
  assign sprod    = sa * sb;                    // 64 位有符号乘积
  assign sprod_su = sa * $signed({1'b0, b});    // 有符号 × 无符号

  always_comb begin
    y = 32'h0;
    unique case (op)
      3'b000: y = a * b;                        // mul
      3'b001: y = sprod[63:32];                 // mulh
      3'b010: y = sprod_su[63:32];              // mulhsu
      3'b011: y = uprod[63:32];                 // mulhu
      3'b100: begin                             // div
        if (b == 32'd0)                        y = 32'hFFFF_FFFF;
        else if (a == INT_MIN && b == 32'hFFFF_FFFF) y = INT_MIN;
        else                                   y = sa / sb;
      end
      3'b101: y = (b == 32'd0) ? 32'hFFFF_FFFF : (a / b);          // divu
      3'b110: begin                             // rem
        if (b == 32'd0)                        y = a;
        else if (a == INT_MIN && b == 32'hFFFF_FFFF) y = 32'h0;
        else                                   y = sa % sb;
      end
      default: y = (b == 32'd0) ? a : (a % b);  // remu
    endcase
  end

endmodule

`default_nettype wire


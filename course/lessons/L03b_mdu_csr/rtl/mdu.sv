// CoralNPU 教学仓 L03b 骨架：M 扩展（乘除法单元）
//
// ============================ 你来实现 ============================
// op 直接用指令的 funct3：
//   000 mul     001 mulh    010 mulhsu  011 mulhu
//   100 div     101 divu    110 rem     111 remu
//
// 难点不在"怎么乘"，而在这三个规范细节：
//   1. 高位乘法要把操作数按正确的符号性扩展到 64 位：
//        mulh   = 有符号 × 有符号
//        mulhsu = 有符号 × 无符号
//        mulhu  = 无符号 × 无符号
//   2. 除零：div/divu 返回全 1（-1），rem/remu 返回被除数
//   3. 溢出：INT_MIN / -1 = INT_MIN，rem = 0
//
// 提示：Verilog 里需要 64 位中间结果时，赋值目标的位宽会决定运算位宽，例如
//   logic [63:0] uprod;  assign uprod = a * b;          // 64 位无符号乘积
//   logic signed [63:0] sprod; assign sprod = sa * sb;  // 64 位有符号乘积
// 除法的除零情况要先用 if 挡住，再算 a / b（不要指望硬件的默认行为）。
// ==================================================================

`default_nettype none

module mdu (
    input  logic [31:0] a,
    input  logic [31:0] b,
    input  logic [2:0]  op,
    output logic [31:0] y
);

  localparam logic [31:0] INT_MIN = 32'h8000_0000;

  logic signed [31:0] sa, sb;
  assign sa = a;
  assign sb = b;

  always_comb begin
    y = 32'h0;
    unique case (op)
      3'b000: y = a * b;               // mul：低 32 位（已给）
      // TODO 1: mulh    —— 有符号 × 有符号 的高 32 位
      // TODO 2: mulhsu  —— 有符号 × 无符号 的高 32 位
      // TODO 3: mulhu   —— 无符号 × 无符号 的高 32 位
      // TODO 4: div     —— 注意除零与 INT_MIN/-1
      // TODO 5: divu
      // TODO 6: rem
      // TODO 7: remu
      default: y = 32'h0;
    endcase
  end

endmodule

`default_nettype wire


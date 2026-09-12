// P0 模块 C 参考实现：三输入多数表决器

`default_nettype none

module majority (
    input  logic a,
    input  logic b,
    input  logic c,
    output logic y
);

  // 任意两个为 1 → 输出 1
  assign y = (a & b) | (b & c) | (a & c);

endmodule

`default_nettype wire


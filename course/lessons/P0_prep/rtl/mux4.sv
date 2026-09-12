// P0 模块 D 练习之一：4 选 1 多路选择器（组合逻辑）
//
// 任务：根据 sel 选择其中一路数据输出。
//   sel=0 → y=d0    sel=1 → y=d1    sel=2 → y=d2    sel=3 → y=d3
//
// 这是处理器里最常见的一块逻辑：寄存器堆读端口、写回数据选择、
// 地址译码，本质上都是「多路选择器」。

`default_nettype none

module mux4 (
    input  logic [31:0] d0,
    input  logic [31:0] d1,
    input  logic [31:0] d2,
    input  logic [31:0] d3,
    input  logic [1:0]  sel,
    output logic [31:0] y
);

  // TODO 2：用 always_comb + case 实现选择逻辑
  //   注意：每个分支都要给 y 赋值，最后要有 default，否则会综合出锁存器
  always_comb begin
    y = 32'h0;
  end

endmodule

`default_nettype wire


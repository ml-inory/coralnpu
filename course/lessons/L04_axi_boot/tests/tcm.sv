// CoralNPU 教学仓 L04：ITCM 存储器（课程提供，学员不需要修改）
//
// 为什么不直接在测试平台里用 $readmemh 灌程序？因为 L04 的"第 1 步"就是
// **主机通过 s_axi 把程序写进 ITCM**——存储器必须有一个主机写口，这个写口
// 由外壳的地址译码驱动。
//
// 端口分工（一个写口 + 三个组合读口）：
//   host_*   主机写口 / 主机读口（来自 s_axi 译码，跑在总线时钟上）
//   iaddr    核心取指读口（核心要求"当拍出数据"，所以是组合读）
//   daddr    核心数据读口（程序可以 load 只读数据，比如 .rodata）
//
// 核心对 ITCM 的"写"由外壳丢弃：ITCM 只读，和上游 CoralNPU 一致
// （往 ITCM 写会被上游的地址检查拦住，本课简化为丢弃）。

`default_nettype none

module tcm #(
    parameter int          WORDS = 2048,             // 8 KB
    parameter logic [31:0] BASE  = 32'h0000_0000
) (
    input  logic        clk,
    // 主机写口 / 读口
    input  logic        host_we,
    input  logic [31:0] host_waddr,
    input  logic [31:0] host_wdata,
    input  logic [3:0]  host_wstrb,
    input  logic [31:0] host_raddr,
    output logic [31:0] host_rdata,
    // 核心取指
    input  logic [31:0] iaddr,
    output logic [31:0] irdata,
    // 核心数据读
    input  logic [31:0] daddr,
    output logic [31:0] drdata
);

  logic [31:0] mem[0:WORDS-1];

  function automatic bit in_range(input logic [31:0] a);
    in_range = (a >= BASE) && (a < BASE + WORDS * 4);
  endfunction

  function automatic int unsigned idx_of(input logic [31:0] a);
    idx_of = (a - BASE) >> 2;
  endfunction

  // 组合读：核心的取指端口要求"地址给出后当拍就能读回数据"。
  //
  // 注意这里必须用 always_comb（而不是 assign + 函数）：数组内容被写入后，
  // iverilog 对"连续赋值里调用读数组的函数"这种写法不会重新求值，
  // 会读回旧数据。always_comb 会把 mem 整体放进敏感列表，行为才对。
  always_comb begin
    host_rdata = in_range(host_raddr) ? mem[idx_of(host_raddr)] : 32'h0;
    irdata     = in_range(iaddr)      ? mem[idx_of(iaddr)]      : 32'h0;
    drdata     = in_range(daddr)      ? mem[idx_of(daddr)]      : 32'h0;
  end

  // 主机写：按字节掩码写入
  always_ff @(posedge clk) begin
    if (host_we && in_range(host_waddr)) begin
      logic [31:0] cur;
      cur = mem[idx_of(host_waddr)];
      if (host_wstrb[0]) cur[7:0]   = host_wdata[7:0];
      if (host_wstrb[1]) cur[15:8]  = host_wdata[15:8];
      if (host_wstrb[2]) cur[23:16] = host_wdata[23:16];
      if (host_wstrb[3]) cur[31:24] = host_wdata[31:24];
      mem[idx_of(host_waddr)] <= cur;
    end
  end

  initial begin
    for (int unsigned i = 0; i < WORDS; i++) mem[i] = 32'h0;
  end

endmodule

`default_nettype wire

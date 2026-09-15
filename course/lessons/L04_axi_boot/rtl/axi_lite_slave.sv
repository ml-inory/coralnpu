// CoralNPU 教学仓 L04 骨架：AXI4-Lite 从接口
//
// ============================ 你来实现 ============================
// 把主机的五条 AXI 通道翻译成一个"本地读写端口"：
//
//   写：AW + W 两路都到齐 → o_wr_en 拉高一拍（地址/数据/掩码同时有效）
//       → 采样 i_wr_resp → 回 B 响应（s_bvalid/s_bresp 一直举到 s_bready）
//   读：AR 握手 → 地址保持 → 用组合的 i_rd_data/i_rd_resp 回 R 响应
//
// 关键约束（写错会仿真卡死，见 基础知识 2.3 节）：
//   * VALID 不能等 READY：主机拉高 s_awvalid 后必须一直保持，直到 s_awready；
//   * 握手只发生在"valid 与 ready 同一拍为 1"的时刻；
//   * 写响应用 s_bvalid（不是一拍脉冲）：主机可能还没准备好接 B。
//
// 提示：
//   * AW 和 W 可能在不同拍到达，所以要各留一个"到了吗"的标志；
//   * s_awready 不能在 b_pending 时拉高（否则同一拍会收进第二笔写）。
// ==================================================================

`default_nettype none

module axi_lite_slave (
    input  logic        clk,
    input  logic        rst,

    // ---- 主机侧：AXI4-Lite 从接口 ----
    input  logic [31:0] s_awaddr,
    input  logic        s_awvalid,
    output logic        s_awready,
    input  logic [31:0] s_wdata,
    input  logic [3:0]  s_wstrb,
    input  logic        s_wvalid,
    output logic        s_wready,
    output logic [1:0]  s_bresp,
    output logic        s_bvalid,
    input  logic        s_bready,
    input  logic [31:0] s_araddr,
    input  logic        s_arvalid,
    output logic        s_arready,
    output logic [31:0] s_rdata,
    output logic [1:0]  s_rresp,
    output logic        s_rvalid,
    input  logic        s_rready,

    // ---- 本地端口（由外壳做地址译码）----
    output logic [31:0] o_wr_addr,
    output logic [31:0] o_wr_data,
    output logic [3:0]  o_wr_strb,
    output logic        o_wr_en,      // 单拍脉冲：这一拍发生写入
    input  logic [1:0]  i_wr_resp,    // 写入的响应码（OKAY / SLVERR）
    output logic [31:0] o_rd_addr,    // 读地址：握手后保持有效，直到 R 返回
    input  logic [31:0] i_rd_data,    // 读数据（组合，随 o_rd_addr 变化）
    input  logic [1:0]  i_rd_resp
);

  // 状态（骨架已经替你声明好，直接填逻辑即可）
  logic        aw_have, w_have;      // AW / W 两路谁已经到齐
  logic        b_pending;            // 写响应还没发完
  logic        r_pending;            // 读数据还没发完
  logic [31:0] aw_addr_q, w_data_q;
  logic [3:0]  w_strb_q;
  logic [31:0] ar_addr_q;
  logic [1:0]  b_resp_q;

  // ---- 写通道 ----------------------------------------------------
  // TODO 1：AW / W 各自握手，把地址、数据、掩码捕获进上面的 *_q
  assign s_awready = ~aw_have & ~b_pending;
  assign s_wready  = ~w_have & ~b_pending;

  // TODO 2：两路都到齐的那一拍拉高 o_wr_en；随后把 i_wr_resp 作为 B 响应发出去
  assign o_wr_en   = 1'b0;
  assign o_wr_addr = aw_addr_q;
  assign o_wr_data = w_data_q;
  assign o_wr_strb = w_strb_q;
  assign s_bvalid  = 1'b0;
  assign s_bresp   = b_resp_q;

  // ---- 读通道 ----------------------------------------------------
  // TODO 3：AR 握手，把地址捕获到 ar_addr_q 并在 R 被接走之前保持不变
  assign s_arready = 1'b0;
  assign o_rd_addr = ar_addr_q;

  // TODO 4：R 响应（组合的 i_rd_data / i_rd_resp 直接转发）
  assign s_rvalid  = 1'b0;
  assign s_rdata   = i_rd_data;
  assign s_rresp   = i_rd_resp;

  // ---- 时序 ------------------------------------------------------
  // TODO 5：复位清零；每个时钟沿更新上面的标志与寄存器
  always_ff @(posedge clk) begin
    if (rst) begin
      aw_have   <= 1'b0;
      w_have    <= 1'b0;
      b_pending <= 1'b0;
      r_pending <= 1'b0;
      aw_addr_q <= 32'h0;
      w_data_q  <= 32'h0;
      w_strb_q  <= 4'h0;
      ar_addr_q <= 32'h0;
      b_resp_q  <= 2'b00;
    end else begin
      // TODO 5：AW/W/AR 到齐时置标志、写完成时清标志并回 B、R 被接走后清 r_pending
    end
  end

endmodule

`default_nettype wire

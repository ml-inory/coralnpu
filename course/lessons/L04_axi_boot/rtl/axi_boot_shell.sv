// CoralNPU 教学仓 L04 骨架：AXI 外壳、控制寄存器与启动流程
//
// ============================ 你来实现 ============================
// 这一层等于上游的 CoreAxiCSR.scala + AXI 桥（教学版）：
//
//   主机 ──s_axi──►[ 外壳 ]──imem/dmem──► 核心
//                     │                    │
//                     ├── ITCM（tcm.sv）    └── 数据访问走 m_axi 出去
//                     └── RESET_CONTROL / PC_START / STATUS
//
// 地址映射：
//   0x0000_0000 – 0x0000_1FFF  ITCM（8 KB，主机可写，核心只读）
//   0x0003_0000 + 0x0          RESET_CONTROL  bit0=RESET bit1=CLOCK_GATE（复位值 0x3）
//   0x0003_0000 + 0x4          PC_START
//   0x0003_0000 + 0x8          STATUS（只读）bit0=HALTED bit1=FAULT
//   其它地址                   从接口回 SLVERR(2'b10)
//
// TODO 一览：
//   1. 地址译码：写/读分别判断 ITCM / CSR / 未映射，给出 l_rd_data 与两个响应码
//   2. 例化 ITCM（课程提供的 tcm.sv），主机写口接译码结果
//   3. CSR 读：RESET_CONTROL / PC_START / STATUS 三选一
//   4. CSR 写 + 启动控制：RESET_CONTROL / PC_START 落寄存器，
//      并产生 o_core_rst / o_core_clk_gate / o_core_pc_start
//   5. 核心侧路由：取指读 ITCM；数据命中 ITCM 就内部服务（一拍完成、写丢弃），
//      未命中就交给下面的 AXI 主状态机
//   6. AXI 主状态机：AR→R 读、AW+W→B 写，并在"事务真正完成的那一拍"把
//      o_dmem_ready 拉高（读的时候 o_dmem_rdata 同时给出数据）
// ==================================================================

`default_nettype none

module axi_boot_shell (
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

    // ---- 核心侧：取指与数据（沿用 L02/L03 的本地接口）----
    input  logic [31:0] i_imem_addr,
    output logic [31:0] o_imem_rdata,
    input  logic [31:0] i_dmem_addr,
    input  logic [31:0] i_dmem_wdata,
    input  logic [3:0]  i_dmem_wmask,
    input  logic        i_dmem_we,
    input  logic        i_dmem_valid,
    output logic [31:0] o_dmem_rdata,
    output logic        o_dmem_ready,

    // ---- 核心侧：AXI4 主接口（每个事务一个数据拍）----
    output logic [31:0] m_araddr,
    output logic        m_arvalid,
    input  logic        m_arready,
    input  logic [31:0] m_rdata,
    input  logic [1:0]  m_rresp,
    input  logic        m_rvalid,
    output logic        m_rready,
    output logic [31:0] m_awaddr,
    output logic        m_awvalid,
    input  logic        m_awready,
    output logic [31:0] m_wdata,
    output logic [3:0]  m_wstrb,
    output logic        m_wvalid,
    input  logic        m_wready,
    input  logic [1:0]  m_bresp,
    input  logic        m_bvalid,
    output logic        m_bready,

    // ---- 启动与状态 ----
    output logic        o_core_rst,
    output logic        o_core_clk_gate,
    output logic [31:0] o_core_pc_start,
    input  logic        i_core_halted,
    input  logic        i_core_fault
);

  localparam logic [31:0] CSR_BASE   = 32'h0003_0000;
  localparam logic [31:0] ITCM_BYTES = 32'h0000_2000;   // 2048 字 = 8 KB
  localparam logic [1:0]  OKAY       = 2'b00;
  localparam logic [1:0]  SLVERR     = 2'b10;

  // ---------------------------------------------------------------- 从接口
  logic [31:0] l_wr_addr, l_wr_data, l_rd_addr, l_rd_data;
  logic [3:0]  l_wr_strb;
  logic        l_wr_en;
  logic [1:0]  l_wr_resp, l_rd_resp;

  axi_lite_slave u_slave (
      .clk (clk), .rst (rst),
      .s_awaddr (s_awaddr), .s_awvalid (s_awvalid), .s_awready (s_awready),
      .s_wdata  (s_wdata),  .s_wstrb (s_wstrb), .s_wvalid (s_wvalid), .s_wready (s_wready),
      .s_bresp  (s_bresp),  .s_bvalid (s_bvalid), .s_bready (s_bready),
      .s_araddr (s_araddr), .s_arvalid (s_arvalid), .s_arready (s_arready),
      .s_rdata  (s_rdata),  .s_rresp (s_rresp), .s_rvalid (s_rvalid), .s_rready (s_rready),
      .o_wr_addr (l_wr_addr), .o_wr_data (l_wr_data), .o_wr_strb (l_wr_strb),
      .o_wr_en   (l_wr_en),   .i_wr_resp (l_wr_resp),
      .o_rd_addr (l_rd_addr), .i_rd_data (l_rd_data), .i_rd_resp (l_rd_resp)
  );

  // ---------------------------------------------------------------- TODO 1
  // TODO 1：地址译码（ITCM / CSR / 未映射）与响应码
  // l_wr_en 是写脉冲，l_rd_addr 是正在读的地址
  logic wr_hit_itcm, wr_hit_csr, rd_hit_itcm, rd_hit_csr;
  assign wr_hit_itcm = 1'b0;
  assign wr_hit_csr  = 1'b0;
  assign rd_hit_itcm = 1'b0;
  assign rd_hit_csr  = 1'b0;
  assign l_rd_data   = 32'h0;
  assign l_rd_resp   = SLVERR;
  assign l_wr_resp   = SLVERR;

  // ---------------------------------------------------------------- TODO 2
  // TODO 2：例化 ITCM（tcm.sv），把主机写口接到译码结果
  logic [31:0] itcm_host_rdata, itcm_irdata, itcm_drdata;
  assign itcm_host_rdata = 32'h0;
  assign itcm_irdata     = 32'h0;
  assign itcm_drdata     = 32'h0;

  // ---------------------------------------------------------------- TODO 3
  // TODO 3：CSR 读（RESET_CONTROL / PC_START / STATUS）
  logic        reset_bit;      // RESET_CONTROL[0]，复位值 1
  logic        cg_bit;         // RESET_CONTROL[1]，复位值 1（时钟门控打开）
  logic [31:0] pc_start_q;     // PC_START
  logic        bus_error_q;    // 总线上出现过非 OKAY 响应
  logic [31:0] csr_rdata;

  assign csr_rdata = 32'h0;

  // TODO 4：复位值与两个寄存器写入；并且
  //   o_core_rst      = rst | reset_bit
  //   o_core_clk_gate = cg_bit
  //   o_core_pc_start = pc_start_q
  assign o_core_rst      = rst;
  assign o_core_clk_gate = 1'b1;
  assign o_core_pc_start = 32'h0;

  always_ff @(posedge clk) begin
    if (rst) begin
      reset_bit   <= 1'b1;
      cg_bit      <= 1'b1;
      pc_start_q  <= 32'h0;
      bus_error_q <= 1'b0;
    end else begin
      // TODO 4：写 RESET_CONTROL / PC_START；出现非 OKAY 响应时记一笔故障
    end
  end

  // ---------------------------------------------------------------- TODO 5
  // TODO 5：取指读 ITCM；数据命中 ITCM 内部服务，否则交给主状态机
  assign o_imem_rdata = 32'h0;

  logic d_hit_itcm, d_go_axi;
  assign d_hit_itcm   = 1'b0;
  assign d_go_axi     = 1'b0;
  assign o_dmem_rdata = 32'h0;
  assign o_dmem_ready = 1'b0;

  // ---------------------------------------------------------------- TODO 6
  // TODO 6：AXI 主接口（单拍读 AR→R、单拍写 AW+W→B）
  typedef enum logic [2:0] {M_IDLE, M_RADDR, M_RDATA, M_WADDR, M_BRESP} mstate_e;
  mstate_e     mstate;
  logic [31:0] m_addr_q, m_wdata_q;
  logic [3:0]  m_strb_q;
  logic        aw_pending, w_pending;

  assign m_araddr  = m_addr_q;
  assign m_arvalid = 1'b0;
  assign m_rready  = 1'b0;
  assign m_awaddr  = m_addr_q;
  assign m_awvalid = 1'b0;
  assign m_wdata   = m_wdata_q;
  assign m_wstrb   = m_strb_q;
  assign m_wvalid  = 1'b0;
  assign m_bready  = 1'b0;

  always_ff @(posedge clk) begin
    if (rst) begin
      mstate     <= M_IDLE;
      aw_pending <= 1'b0;
      w_pending  <= 1'b0;
      m_addr_q   <= 32'h0;
      m_wdata_q  <= 32'h0;
      m_strb_q   <= 4'h0;
    end else begin
      // TODO 6：主状态机的时序部分
    end
  end

endmodule

`default_nettype wire

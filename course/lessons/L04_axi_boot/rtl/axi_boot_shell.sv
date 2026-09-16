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
  assign wr_hit_itcm = l_wr_en & (l_wr_addr < ITCM_BYTES);
  assign wr_hit_csr  = l_wr_en & (l_wr_addr >= CSR_BASE & l_wr_addr <= CSR_BASE + 32'd8);
  assign rd_hit_itcm = l_rd_addr < ITCM_BYTES;
  assign rd_hit_csr  = (l_rd_addr >= CSR_BASE) & (l_rd_addr <= CSR_BASE + 32'd8);
  // 注意：l_rd_data 现在由下面的 TCM 实例驱动（TODO 3 做 CSR 时再改成按 hit 选择）
  assign l_rd_resp   = ~l_wr_en & (rd_hit_itcm | rd_hit_csr) ? OKAY : SLVERR;
  assign l_wr_resp   = l_wr_en  & (wr_hit_itcm | wr_hit_csr) ? OKAY : SLVERR;

  // ---------------------------------------------------------------- TODO 2
  // TODO 2：例化 ITCM（tcm.sv），把主机写口接到译码结果
  logic [31:0] itcm_irdata, itcm_drdata, itcm_host_rdata;

  tcm #(ITCM_BYTES, 32'h0000_0000) u_tcm
  (
    .clk(clk), 
    .host_we(wr_hit_itcm), 
    .host_waddr(l_wr_addr),
    .host_wdata(l_wr_data),
    .host_wstrb(l_wr_strb),
    .host_raddr(l_rd_addr),
    .host_rdata(itcm_host_rdata),
    .iaddr(i_imem_addr),
    .irdata(itcm_irdata),
    .daddr(i_dmem_addr),
    .drdata(itcm_drdata)
  );

  // ---------------------------------------------------------------- TODO 3
  // TODO 3：CSR 读（RESET_CONTROL / PC_START / STATUS）
  logic        reset_bit;      // RESET_CONTROL[0]，复位值 1
  logic        cg_bit;         // RESET_CONTROL[1]，复位值 1（时钟门控打开）
  logic [31:0] pc_start_q;     // PC_START
  logic        bus_error_q;    // 总线上出现过非 OKAY 响应
  logic [31:0] csr_rdata;

  // 假CSR，只是3个寄存器
  always_comb begin
    if (rd_hit_csr) begin
      case (l_rd_addr)
        CSR_BASE:         csr_rdata = {30'h0, cg_bit, reset_bit};
        CSR_BASE + 32'd4: csr_rdata = pc_start_q;
        CSR_BASE + 32'd8: csr_rdata = {30'h0, i_core_fault | bus_error_q, i_core_halted};
        default:          csr_rdata = 32'h0;
      endcase
    end else begin
      csr_rdata = 32'h0;
    end
  end
  
  // 读数据MUX
  assign l_rd_data = rd_hit_itcm ? itcm_host_rdata : csr_rdata;

  // TODO 4：复位值与两个寄存器写入；并且
  //   o_core_rst      = rst | reset_bit
  //   o_core_clk_gate = cg_bit
  //   o_core_pc_start = pc_start_q
  assign o_core_rst      = rst | reset_bit;
  assign o_core_clk_gate = cg_bit;
  assign o_core_pc_start = pc_start_q;

  always_ff @(posedge clk) begin
    if (rst) begin
      reset_bit   <= 1'b1;
      cg_bit      <= 1'b1;
      pc_start_q  <= 32'h0;
      bus_error_q <= 1'b0;
    end else begin
      // TODO 4：写 RESET_CONTROL / PC_START；出现非 OKAY 响应时记一笔故障
      if (wr_hit_csr & (l_wr_addr == CSR_BASE)) begin
        reset_bit <= l_wr_data[0];
        cg_bit    <= l_wr_data[1];
      end

      if (wr_hit_csr & (l_wr_addr == CSR_BASE + 32'd4)) begin
        pc_start_q <= l_wr_data;
      end

      if ((m_rvalid && (m_rresp != OKAY)) || (m_bvalid && (m_bresp != OKAY)))
        bus_error_q <= 1'b1;
    end
  end

  // ---------------------------------------------------------------- TODO 5
  // TODO 5：取指读 ITCM；数据命中 ITCM 内部服务，否则交给主状态机
  assign o_imem_rdata = itcm_irdata;

  logic d_hit_itcm, d_go_axi;
  assign d_hit_itcm   = i_dmem_addr < ITCM_BYTES;
  assign d_go_axi     = i_dmem_valid & ~d_hit_itcm;
  assign o_dmem_rdata = d_hit_itcm ? itcm_drdata : m_rdata;
  assign o_dmem_ready = d_hit_itcm ? 1'b1 :
                        i_dmem_we ? (mstate == M_BRESP && m_bvalid) : (mstate == M_RDATA && m_rvalid);

  // ---------------------------------------------------------------- TODO 6
  // TODO 6：AXI 主接口（单拍读 AR→R、单拍写 AW+W→B）
  typedef enum logic [2:0] {M_IDLE, M_RADDR, M_RDATA, M_WADDR, M_BRESP} mstate_e;
  mstate_e     mstate;
  logic [31:0] m_addr_q, m_wdata_q;
  logic [3:0]  m_strb_q;
  logic        aw_pending, w_pending;

  assign m_araddr  = m_addr_q;
  assign m_arvalid = mstate == M_RADDR;
  assign m_rready  = mstate == M_RDATA;
  assign m_awaddr  = m_addr_q;
  assign m_awvalid = (mstate == M_WADDR) & aw_pending;
  assign m_wdata   = m_wdata_q;
  assign m_wstrb   = m_strb_q;
  assign m_wvalid  = (mstate == M_WADDR) & w_pending;
  assign m_bready  = mstate == M_BRESP;

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
      case (mstate)
        M_IDLE: begin
          if (d_go_axi) begin
            if (i_dmem_we) begin
              aw_pending <= 1'b1;
              w_pending <= 1'b1;
              m_addr_q <= i_dmem_addr;
              m_wdata_q <= i_dmem_wdata;
              m_strb_q <= i_dmem_wmask;
              mstate <= M_WADDR;
            end
            else begin
              m_addr_q <= i_dmem_addr;
              mstate <= M_RADDR;
            end
          end
          else  mstate <= M_IDLE;
        end
        M_RADDR: begin
          mstate <= m_arready ? M_RDATA : M_RADDR;
        end
        M_RDATA: begin
          mstate <= m_rvalid ? M_IDLE : M_RDATA;
        end
        M_WADDR: begin
          if (m_awvalid && m_awready) aw_pending <= 1'b0;
          if (m_wvalid && m_wready) w_pending <= 1'b0;
          mstate <= ~aw_pending & ~w_pending ? M_BRESP : M_WADDR;
        end
        M_BRESP: begin
          mstate <= m_bvalid ? M_IDLE : M_BRESP;
          aw_pending <= 1'b0;
          w_pending <= 1'b0;
        end
        default: mstate <= M_IDLE;
      endcase
    end
  end

endmodule

`default_nettype wire

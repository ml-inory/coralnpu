// CoralNPU 教学仓 L04：AXI 外壳与启动控制（参考实现）
//
// 这一层就是上游 CoreAxiCSR.scala + AXI 桥的教学版：
//
//   主机 ──s_axi──►[ 外壳 ]──imem/dmem──► 核心
//                     │                    │
//                     ├── ITCM（tcm.sv）    └── 数据访问走 m_axi 出去
//                     └── RESET_CONTROL / PC_START / STATUS
//
// 地址映射（与 doc/integration_guide.md 对齐，做了裁剪）：
//   0x0000_0000 – 0x0000_1FFF  ITCM（8 KB，主机可写，核心只读）
//   0x0003_0000 + 0x0          RESET_CONTROL  bit0=RESET bit1=CLOCK_GATE
//   0x0003_0000 + 0x4          PC_START
//   0x0003_0000 + 0x8          STATUS（只读）bit0=HALTED bit1=FAULT
//   其它地址                   从接口回 SLVERR

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

  // ---------------------------------------------------------------- 本地端口
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

  // ---------------------------------------------------------------- ITCM
  logic [31:0] itcm_host_rdata, itcm_irdata, itcm_drdata;
  logic        wr_hit_itcm, wr_hit_csr, rd_hit_itcm, rd_hit_csr;

  assign wr_hit_itcm = l_wr_en && (l_wr_addr < ITCM_BYTES);
  assign wr_hit_csr  = l_wr_en && (l_wr_addr >= CSR_BASE) && (l_wr_addr < CSR_BASE + 12);
  assign rd_hit_itcm = (l_rd_addr < ITCM_BYTES);
  assign rd_hit_csr  = (l_rd_addr >= CSR_BASE) && (l_rd_addr < CSR_BASE + 12);

  tcm #(.WORDS (2048), .BASE (32'h0)) u_itcm (
      .clk        (clk),
      .host_we    (wr_hit_itcm),
      .host_waddr (l_wr_addr),
      .host_wdata (l_wr_data),
      .host_wstrb (l_wr_strb),
      .host_raddr (l_rd_addr),
      .host_rdata (itcm_host_rdata),
      .iaddr      (i_imem_addr),
      .irdata     (itcm_irdata),
      .daddr      (i_dmem_addr),
      .drdata     (itcm_drdata)
  );

  // ---------------------------------------------------------------- 控制寄存器
  logic        reset_bit;      // RESET_CONTROL[0]
  logic        cg_bit;         // RESET_CONTROL[1]
  logic [31:0] pc_start_q;     // PC_START
  logic        bus_error_q;    // 总线上出现过非 OKAY 响应
  logic [31:0] csr_rdata;

  wire fault_w = i_core_fault | bus_error_q;
  wire halted_w = i_core_halted;

  function automatic logic [31:0] apply_strb(input logic [31:0] old_v,
                                             input logic [31:0] new_v,
                                             input logic [3:0]  strb);
    apply_strb = old_v;
    if (strb[0]) apply_strb[7:0]   = new_v[7:0];
    if (strb[1]) apply_strb[15:8]  = new_v[15:8];
    if (strb[2]) apply_strb[23:16] = new_v[23:16];
    if (strb[3]) apply_strb[31:24] = new_v[31:24];
  endfunction

  always_comb begin
    case (l_rd_addr)
      CSR_BASE + 32'h0: csr_rdata = {30'b0, cg_bit, reset_bit};
      CSR_BASE + 32'h4: csr_rdata = pc_start_q;
      CSR_BASE + 32'h8: csr_rdata = {30'b0, fault_w, halted_w};
      default:          csr_rdata = 32'h0;
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      reset_bit  <= 1'b1;          // 上电：核心保持在复位
      cg_bit     <= 1'b1;          // 上电：核心时钟门控打开（=时钟停住）
      pc_start_q <= 32'h0;
      bus_error_q <= 1'b0;
    end else begin
      if (wr_hit_csr) begin
        case (l_wr_addr)
          CSR_BASE + 32'h0: begin
            if (l_wr_strb[0]) reset_bit <= l_wr_data[0];
            if (l_wr_strb[1]) cg_bit    <= l_wr_data[1];
          end
          CSR_BASE + 32'h4: pc_start_q <= apply_strb(pc_start_q, l_wr_data, l_wr_strb);
          default: ;               // STATUS 只读
        endcase
      end
      if ((m_rvalid && (m_rresp != OKAY)) || (m_bvalid && (m_bresp != OKAY)))
        bus_error_q <= 1'b1;
    end
  end

  // 从机侧读数据/响应：ITCM 命中读 ITCM，CSR 命中读 CSR，其它 SLVERR
  assign l_rd_data = rd_hit_itcm ? itcm_host_rdata : csr_rdata;
  assign l_rd_resp = (rd_hit_itcm || rd_hit_csr) ? OKAY : SLVERR;
  assign l_wr_resp = (wr_hit_itcm || wr_hit_csr) ? OKAY : SLVERR;

  assign o_core_rst      = rst | reset_bit;
  assign o_core_clk_gate = cg_bit;
  assign o_core_pc_start = pc_start_q;

  // ---------------------------------------------------------------- 核心取指
  assign o_imem_rdata = itcm_irdata;

  // ---------------------------------------------------------------- 核心数据访问
  // 规则：命中 ITCM → 内部组合读（一拍完成，写丢弃）；其余地址 → 走 m_axi
  wire d_hit_itcm = (i_dmem_addr < ITCM_BYTES);
  wire d_go_axi   = i_dmem_valid & ~d_hit_itcm;

  typedef enum logic [2:0] {M_IDLE, M_RADDR, M_RDATA, M_WADDR, M_BRESP} mstate_e;
  mstate_e     mstate;
  logic [31:0] m_addr_q, m_wdata_q;
  logic [3:0]  m_strb_q;
  logic        aw_pending, w_pending;

  assign m_araddr  = m_addr_q;
  assign m_arvalid = (mstate == M_RADDR);
  assign m_rready  = (mstate == M_RDATA);

  assign m_awaddr  = m_addr_q;
  assign m_awvalid = (mstate == M_WADDR) && aw_pending;
  assign m_wdata   = m_wdata_q;
  assign m_wstrb   = m_strb_q;
  assign m_wvalid  = (mstate == M_WADDR) && w_pending;
  assign m_bready  = (mstate == M_BRESP);

  // 核心侧：ready 在"事务真正完成的那一拍"拉高；读数据同时给出
  assign o_dmem_rdata = d_hit_itcm ? itcm_drdata : m_rdata;
  assign o_dmem_ready = d_hit_itcm ? 1'b1
                      : i_dmem_we  ? ((mstate == M_BRESP) && m_bvalid)
                                   : ((mstate == M_RDATA) && m_rvalid);

  always_ff @(posedge clk) begin
    if (rst) begin
      mstate     <= M_IDLE;
      aw_pending <= 1'b0;
      w_pending  <= 1'b0;
      m_addr_q   <= 32'h0;
      m_wdata_q  <= 32'h0;
      m_strb_q   <= 4'h0;
    end else begin
      case (mstate)
        M_IDLE: if (d_go_axi) begin
          m_addr_q  <= i_dmem_addr;
          m_wdata_q <= i_dmem_wdata;
          m_strb_q  <= i_dmem_wmask;
          if (i_dmem_we) begin
            mstate     <= M_WADDR;
            aw_pending <= 1'b1;
            w_pending  <= 1'b1;
          end else begin
            mstate <= M_RADDR;
          end
        end
        M_RADDR: if (m_arvalid && m_arready) mstate <= M_RDATA;
        M_RDATA: if (m_rvalid)               mstate <= M_IDLE;
        M_WADDR: begin
          if (m_awvalid && m_awready) aw_pending <= 1'b0;
          if (m_wvalid  && m_wready)  w_pending  <= 1'b0;
          if ((!aw_pending || (m_awvalid && m_awready)) &&
              (!w_pending  || (m_wvalid  && m_wready)))
            mstate <= M_BRESP;
        end
        M_BRESP: if (m_bvalid) mstate <= M_IDLE;
        default: mstate <= M_IDLE;
      endcase
    end
  end

endmodule

`default_nettype wire

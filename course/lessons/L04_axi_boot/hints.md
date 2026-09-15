# L04 分级提示

## 提示 1：从接口的写通道（AW / W / B）

```systemverilog
  assign s_awready = ~aw_have & ~b_pending;      // 有空接、且没有待发响应
  assign s_wready  = ~w_have  & ~b_pending;
  assign o_wr_en   = aw_have & w_have & ~b_pending;   // 两路都到齐 → 本地写一拍
  assign s_bvalid  = b_pending;
  assign s_bresp   = b_resp_q;

  // 时序：
  if (s_awvalid && s_awready) begin aw_have <= 1'b1; aw_addr_q <= s_awaddr; end
  if (s_wvalid  && s_wready)  begin w_have <= 1'b1; w_data_q <= s_wdata; w_strb_q <= s_wstrb; end
  if (o_wr_en) begin aw_have <= 0; w_have <= 0; b_resp_q <= i_wr_resp; b_pending <= 1'b1; end
  else if (s_bvalid && s_bready) b_pending <= 1'b0;
```

## 提示 2：从接口的读通道（AR / R）

```systemverilog
  assign s_arready = ~r_pending;
  assign o_rd_addr = ar_addr_q;          // 握手后地址保持不变，组合读数据才稳定
  assign s_rvalid  = r_pending;
  assign s_rdata   = i_rd_data;
  assign s_rresp   = i_rd_resp;

  if (s_arvalid && s_arready) begin r_pending <= 1'b1; ar_addr_q <= s_araddr; end
  else if (s_rvalid && s_rready) r_pending <= 1'b0;
```

## 提示 3：地址译码与 CSR 读

```systemverilog
  assign wr_hit_itcm = l_wr_en && (l_wr_addr < ITCM_BYTES);
  assign wr_hit_csr  = l_wr_en && (l_wr_addr >= CSR_BASE) && (l_wr_addr < CSR_BASE + 12);
  assign rd_hit_itcm = (l_rd_addr < ITCM_BYTES);
  assign rd_hit_csr  = (l_rd_addr >= CSR_BASE) && (l_rd_addr < CSR_BASE + 12);

  assign l_rd_data = rd_hit_itcm ? itcm_host_rdata : csr_rdata;
  assign l_rd_resp = (rd_hit_itcm || rd_hit_csr) ? OKAY : SLVERR;
  assign l_wr_resp = (wr_hit_itcm || wr_hit_csr) ? OKAY : SLVERR;

  always_comb begin
    case (l_rd_addr)
      CSR_BASE + 32'h0: csr_rdata = {30'b0, cg_bit, reset_bit};
      CSR_BASE + 32'h4: csr_rdata = pc_start_q;
      CSR_BASE + 32'h8: csr_rdata = {30'b0, (i_core_fault | bus_error_q), i_core_halted};
      default:          csr_rdata = 32'h0;
    endcase
  end
```

## 提示 4：启动控制与 CSR 写

```systemverilog
  assign o_core_rst      = rst | reset_bit;      // 外部复位 + CSR 里的 RESET
  assign o_core_clk_gate = cg_bit;               // 1 = 门控打开（核心没有时钟沿）
  assign o_core_pc_start = pc_start_q;           // 复位时装载进 PC

  if (wr_hit_csr) begin
    case (l_wr_addr)
      CSR_BASE + 32'h0: begin
        if (l_wr_strb[0]) reset_bit <= l_wr_data[0];
        if (l_wr_strb[1]) cg_bit    <= l_wr_data[1];
      end
      CSR_BASE + 32'h4: pc_start_q <= l_wr_data;   // 更严谨的做法是按 wstrb 逐字节改
      default: ;                                    // STATUS 只读
    endcase
  end

  // AXI 主接口上出现非 OKAY 响应时，也记一笔故障：
  if ((m_rvalid && (m_rresp != OKAY)) || (m_bvalid && (m_bresp != OKAY)))
    bus_error_q <= 1'b1;
```

## 提示 5：ITCM、核心侧路由与 AXI 主状态机

```systemverilog
  tcm #(.WORDS (2048), .BASE (32'h0)) u_itcm (
      .clk (clk),
      .host_we (wr_hit_itcm), .host_waddr (l_wr_addr), .host_wdata (l_wr_data),
      .host_wstrb (l_wr_strb), .host_raddr (l_rd_addr), .host_rdata (itcm_host_rdata),
      .iaddr (i_imem_addr), .irdata (itcm_irdata),
      .daddr (i_dmem_addr), .drdata (itcm_drdata)
  );

  assign o_imem_rdata = itcm_irdata;                       // 取指始终读 ITCM
  wire d_hit_itcm = (i_dmem_addr < ITCM_BYTES);
  wire d_go_axi   = i_dmem_valid & ~d_hit_itcm;            // 未命中才走总线
  assign o_dmem_rdata = d_hit_itcm ? itcm_drdata : m_rdata;
  assign o_dmem_ready = d_hit_itcm ? 1'b1
                      : i_dmem_we  ? ((mstate == M_BRESP) && m_bvalid)
                                   : ((mstate == M_RDATA) && m_rvalid);

  assign m_arvalid = (mstate == M_RADDR);
  assign m_rready  = (mstate == M_RDATA);
  assign m_awvalid = (mstate == M_WADDR) && aw_pending;
  assign m_wvalid  = (mstate == M_WADDR) && w_pending;
  assign m_bready  = (mstate == M_BRESP);

  // 状态机：IDLE 抓请求 →
  //   读：RADDR（AR 握手）→ RDATA（R 握手）→ IDLE
  //   写：WADDR（AW、W 各自握完，各自清 pending）→ BRESP（B 握手）→ IDLE
```

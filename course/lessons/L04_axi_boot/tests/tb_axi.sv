// CoralNPU 教学仓 L04 测试平台（课程提供，学员不需要修改）
//
// 这个测试平台同时扮演三个角色：
//
//   1. 主机（Host）：用 AXI4-Lite 从接口（s_axi）按上游 5 步流程启动核心——
//        ① 把程序写进 ITCM  ② 写 PC_START  ③ 释放时钟门控  ④ 释放复位
//        ⑤ 轮询 STATUS 等 HALTED / FAULT
//   2. 系统存储器：接在核心的 AXI 主接口（m_axi）后面，就是 DTCM（0x0001_0000 起）。
//      核心的每一次 load/store 都要真的走一遍 AXI 主接口。
//   3. 采集器：把退休指令写进 trace、停机后把 DTCM 镜像写文件，
//      交给 Python 检查器与黄金模型对拍（和 L01～L03 的判定标准一致）。
//
// 时钟：
//   * clk      —— 总线/主机时钟，外壳与系统存储器跑在这个时钟上；
//   * core_clk —— 核心时钟 = clk 与"时钟门控位"相与（上游 CoreAxiCSR 的 io_cg 也是这么用的）。
//     门控打开时核心没有时钟沿，所以"先释放时钟门控、再释放复位"的顺序是必须的。
//
// 参数（+PLUSARG）：
//   +PROGRAM=   ITCM 镜像（每行一个 32 位字，从 +ENTRY 开始写）
//   +DATA=      DTCM 初始镜像
//   +ENTRY=     程序入口地址（同时写进 PC_START）
//   +TRACE= / +DMEM= / +MAX_CYCLES= / +LATENCY=
//   +NO_BOOT=1  只做 AXI 探针（不启动核心），用于单独验证从接口

`timescale 1ns/1ps

module tb_axi;
  parameter int          DMEM_WORDS = 8192;
  parameter logic [31:0] DTCM_BASE  = 32'h0001_0000;
  parameter logic [31:0] CSR_BASE   = 32'h0003_0000;

  logic clk = 1'b0;
  logic rst = 1'b1;
  logic core_clk;

  // ------------------------------------------------------------ 主机侧 s_axi
  logic [31:0] s_awaddr, s_wdata, s_araddr, s_rdata;
  logic [3:0]  s_wstrb;
  logic [1:0]  s_bresp, s_rresp;
  logic        s_awvalid, s_awready, s_wvalid, s_wready, s_bvalid, s_bready;
  logic        s_arvalid, s_arready, s_rvalid, s_rready;

  // ------------------------------------------------------------ 核心侧
  logic [31:0] imem_addr, imem_rdata;
  logic [31:0] dmem_addr, dmem_wdata, dmem_rdata;
  logic [3:0]  dmem_wmask;
  logic        dmem_we, dmem_valid, dmem_ready;

  logic        core_rst, core_clk_gate;
  logic [31:0] core_pc_start;
  logic        core_halted, core_fault;

  logic        retire_valid;
  logic [31:0] retire_pc, retire_inst, retire_wdata;
  logic [4:0]  retire_rd;

  // ------------------------------------------------------------ 主接口 m_axi
  logic [31:0] m_araddr, m_rdata, m_awaddr, m_wdata;
  logic [3:0]  m_wstrb;
  logic [1:0]  m_rresp, m_bresp;
  logic        m_arvalid, m_arready, m_rvalid, m_rready;
  logic        m_awvalid, m_awready, m_wvalid, m_wready, m_bvalid, m_bready;

  // 系统存储器：DTCM（0x0001_0000 起，32 KB）
  logic [31:0] dmem[0:DMEM_WORDS-1];

  string       program_path, data_path, trace_path, dmem_path;
  string       vcd_path;
  int unsigned max_cycles, cycles = 0;
  int unsigned bus_cycles = 0;
  int unsigned latency = 0;
  int          trace_fd, dmem_fd, i;
  logic [31:0] entry = 32'h0;
  bit          no_boot = 1'b0;
  int unsigned rd_txns = 0, wr_txns = 0;      // m_axi 事务计数
  bit          axi_trace = 1'b0;              // +AXI_TRACE=1 打印每一笔总线事务
  bit          stopped_seen = 1'b0;
  logic [31:0] status_seen = 32'h0;

  // 门控未知时按"门控打开"处理（上电默认就是停时钟），避免出现 X 时钟
  logic gate_safe;
  assign gate_safe = (core_clk_gate === 1'b0) ? 1'b0 : 1'b1;
  assign core_clk  = clk & ~gate_safe;

  // ------------------------------------------------------------ DUT
  axi_boot_shell dut (
      .clk (clk), .rst (rst),
      .s_awaddr (s_awaddr), .s_awvalid (s_awvalid), .s_awready (s_awready),
      .s_wdata (s_wdata), .s_wstrb (s_wstrb), .s_wvalid (s_wvalid), .s_wready (s_wready),
      .s_bresp (s_bresp), .s_bvalid (s_bvalid), .s_bready (s_bready),
      .s_araddr (s_araddr), .s_arvalid (s_arvalid), .s_arready (s_arready),
      .s_rdata (s_rdata), .s_rresp (s_rresp), .s_rvalid (s_rvalid), .s_rready (s_rready),
      .i_imem_addr (imem_addr), .o_imem_rdata (imem_rdata),
      .i_dmem_addr (dmem_addr), .i_dmem_wdata (dmem_wdata), .i_dmem_wmask (dmem_wmask),
      .i_dmem_we (dmem_we), .i_dmem_valid (dmem_valid),
      .o_dmem_rdata (dmem_rdata), .o_dmem_ready (dmem_ready),
      .m_araddr (m_araddr), .m_arvalid (m_arvalid), .m_arready (m_arready),
      .m_rdata (m_rdata), .m_rresp (m_rresp), .m_rvalid (m_rvalid), .m_rready (m_rready),
      .m_awaddr (m_awaddr), .m_awvalid (m_awvalid), .m_awready (m_awready),
      .m_wdata (m_wdata), .m_wstrb (m_wstrb), .m_wvalid (m_wvalid), .m_wready (m_wready),
      .m_bresp (m_bresp), .m_bvalid (m_bvalid), .m_bready (m_bready),
      .o_core_rst (core_rst), .o_core_clk_gate (core_clk_gate),
      .o_core_pc_start (core_pc_start),
      .i_core_halted (core_halted), .i_core_fault (core_fault)
  );

  // 核心跑在（可能被门控的）core_clk 上
  core_l04 cpu (
      .clk (core_clk), .rst (core_rst), .i_pc_start (core_pc_start),
      .io_imem_addr (imem_addr), .io_imem_rdata (imem_rdata),
      .io_dmem_addr (dmem_addr), .io_dmem_wmask (dmem_wmask),
      .io_dmem_wdata (dmem_wdata), .io_dmem_we (dmem_we),
      .io_dmem_valid (dmem_valid), .io_dmem_rdata (dmem_rdata),
      .io_dmem_ready (dmem_ready),
      .o_retire_valid (retire_valid), .o_retire_pc (retire_pc),
      .o_retire_inst (retire_inst), .o_retire_rd (retire_rd),
      .o_retire_wdata (retire_wdata),
      .o_halted (core_halted), .o_fault (core_fault)
  );

  // ------------------------------------------------------------ 系统存储器模型
  // 地址落在 DTCM 范围 → OKAY；其它地址 → SLVERR（模拟"没有设备响应"）
  function automatic bit in_dtcm(input logic [31:0] a);
    in_dtcm = (a >= DTCM_BASE) && (a < DTCM_BASE + DMEM_WORDS * 4);
  endfunction

  typedef enum logic [2:0] {MEM_IDLE, MEM_RWAIT, MEM_RDATA, MEM_WWAIT, MEM_BRESP} memstate_e;
  memstate_e   memstate;
  int unsigned wait_cnt;
  logic [31:0] rd_addr_q, wr_addr_q, wr_data_q;
  logic [3:0]  wr_strb_q;
  logic        aw_seen, w_seen;

  assign m_arready = (memstate == MEM_IDLE);
  assign m_awready = (memstate == MEM_WWAIT) && !aw_seen;
  assign m_wready  = (memstate == MEM_WWAIT) && !w_seen;
  assign m_rvalid  = (memstate == MEM_RDATA);
  assign m_bvalid  = (memstate == MEM_BRESP);

  // 读数据必须用 always_comb：assign + 函数读数组时 iverilog 不会在数组被写后重新求值
  always_comb begin
    m_rdata = in_dtcm(rd_addr_q) ? dmem[(rd_addr_q - DTCM_BASE) >> 2] : 32'h0;
    m_rresp = in_dtcm(rd_addr_q) ? 2'b00 : 2'b10;
    m_bresp = in_dtcm(wr_addr_q) ? 2'b00 : 2'b10;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      memstate  <= MEM_IDLE;
      wait_cnt  <= 0;
      aw_seen   <= 1'b0;
      w_seen    <= 1'b0;
      rd_addr_q <= 32'h0;
      wr_addr_q <= 32'h0;
      wr_data_q <= 32'h0;
      wr_strb_q <= 4'h0;
    end else begin
      // AW / W 两路各自独立接收（本课的读事务不会和写事务同时发起）
      if (m_awvalid && m_awready) begin
        aw_seen   <= 1'b1;
        wr_addr_q <= m_awaddr;
      end
      if (m_wvalid && m_wready) begin
        w_seen    <= 1'b1;
        wr_data_q <= m_wdata;
        wr_strb_q <= m_wstrb;
      end

      case (memstate)
        MEM_IDLE: begin
          if (m_arvalid) begin
            rd_addr_q <= m_araddr;
            wait_cnt  <= latency;
            memstate  <= (latency == 0) ? MEM_RDATA : MEM_RWAIT;
            rd_txns   <= rd_txns + 1;
          end else if (m_awvalid || m_wvalid) begin
            wait_cnt <= latency;
            memstate <= MEM_WWAIT;
            wr_txns  <= wr_txns + 1;
          end
        end
        MEM_RWAIT: if (wait_cnt == 0) memstate <= MEM_RDATA;
                   else               wait_cnt <= wait_cnt - 1;
        MEM_RDATA: if (m_rvalid && m_rready) memstate <= MEM_IDLE;
        MEM_WWAIT: begin
          if (aw_seen && w_seen) begin
            if (wait_cnt == 0) memstate <= MEM_BRESP;
            else               wait_cnt <= wait_cnt - 1;
          end
        end
        MEM_BRESP: if (m_bvalid && m_bready) begin
          memstate <= MEM_IDLE;
          aw_seen  <= 1'b0;
          w_seen   <= 1'b0;
        end
        default: memstate <= MEM_IDLE;
      endcase
    end
  end

  // DTCM 写入：在 B 之前落盘（写数据在 W 握手时已经捕获）
  always_ff @(posedge clk) begin
    if (!rst && (memstate == MEM_WWAIT) && aw_seen && w_seen && (wait_cnt == 0) &&
        in_dtcm(wr_addr_q)) begin
      logic [31:0] cur;
      if (axi_trace) $display("AXI WR addr=0x%08x data=0x%08x strb=%b", wr_addr_q, wr_data_q, wr_strb_q);
      cur = dmem[(wr_addr_q - DTCM_BASE) >> 2];
      if (wr_strb_q[0]) cur[7:0]   = wr_data_q[7:0];
      if (wr_strb_q[1]) cur[15:8]  = wr_data_q[15:8];
      if (wr_strb_q[2]) cur[23:16] = wr_data_q[23:16];
      if (wr_strb_q[3]) cur[31:24] = wr_data_q[31:24];
      dmem[(wr_addr_q - DTCM_BASE) >> 2] <= cur;
    end
  end

  always_ff @(posedge clk) begin
    if (!rst && axi_trace && (memstate == MEM_RDATA) && m_rvalid)
      $display("AXI RD addr=0x%08x data=0x%08x resp=%b", rd_addr_q, m_rdata, m_rresp);
  end

  // ------------------------------------------------------------ 主机 BFM（AXI4-Lite 主设备）
  task automatic host_write(input logic [31:0] addr, input logic [31:0] data,
                            output logic [1:0] resp);
    @(negedge clk);
    s_awaddr  = addr;
    s_awvalid = 1'b1;
    s_wdata   = data;
    s_wstrb   = 4'hF;
    s_wvalid  = 1'b1;
    s_bready  = 1'b1;
    while (!s_bvalid) @(negedge clk);
    resp = s_bresp;
    @(negedge clk);
    s_awvalid = 1'b0;
    s_wvalid  = 1'b0;
    s_bready  = 1'b0;
  endtask

  task automatic host_read(input logic [31:0] addr, output logic [31:0] data,
                           output logic [1:0] resp);
    @(negedge clk);
    s_araddr  = addr;
    s_arvalid = 1'b1;
    s_rready  = 1'b1;
    while (!s_rvalid) @(negedge clk);
    data = s_rdata;
    resp = s_rresp;
    @(negedge clk);
    s_arvalid = 1'b0;
    s_rready  = 1'b0;
  endtask

  // ------------------------------------------------------------ trace / DTCM 采集
  always_ff @(posedge core_clk) begin
    if (!core_rst) cycles <= cycles + 1;
  end

  always_ff @(posedge core_clk) begin
    if (!core_rst && retire_valid)
      $fdisplay(trace_fd, "%08x %08x %02x %08x", retire_pc, retire_inst, retire_rd, retire_wdata);
  end

  // ------------------------------------------------------------ 主流程
  int unsigned n_words, k;
  int          prog_fd;
  logic [31:0] prog_words[0:4095];
  logic [31:0] rd_val;
  logic [1:0]  rd_resp, wr_resp;
  logic [31:0] status;

  initial begin
    program_path = "";
    data_path    = "";
    trace_path   = "trace.txt";
    dmem_path    = "dmem.txt";
    max_cycles   = 200000;
    void'($value$plusargs("PROGRAM=%s", program_path));
    void'($value$plusargs("DATA=%s", data_path));
    void'($value$plusargs("ENTRY=%d", entry));
    void'($value$plusargs("TRACE=%s", trace_path));
    void'($value$plusargs("DMEM=%s", dmem_path));
    void'($value$plusargs("MAX_CYCLES=%d", max_cycles));
    void'($value$plusargs("LATENCY=%d", latency));
    void'($value$plusargs("NO_BOOT=%d", no_boot));
    void'($value$plusargs("AXI_TRACE=%d", axi_trace));

    for (k = 0; k < DMEM_WORDS; k++) dmem[k] = 32'h0;
    if (data_path != "") $readmemh(data_path, dmem);
    for (k = 0; k < 4096; k++) prog_words[k] = 32'h0;
    n_words = 0;
    if (program_path != "") begin
      prog_fd = $fopen(program_path, "r");
      if (prog_fd == 0) begin
        $display("无法打开程序镜像 %s", program_path);
        $finish;
      end
      while (!$feof(prog_fd) && (n_words < 4096)) begin
        logic [31:0] w;
        if ($fscanf(prog_fd, "%h\n", w) == 1) begin
          prog_words[n_words] = w;
          n_words = n_words + 1;
        end
      end
      $fclose(prog_fd);
    end

    trace_fd = $fopen(trace_path, "w");
    if (trace_fd == 0) begin
      $display("无法打开 trace 文件 %s", trace_path);
      $finish;
    end

    // 波形：./learn wave L04 会打开这个开关，可以逐拍看信号名与值
    if ($test$plusargs("WAVES")) begin
      vcd_path = "waves.vcd";
      void'($value$plusargs("VCD=%s", vcd_path));
      $dumpfile(vcd_path);
      $dumpvars(0, tb_axi);
      $display("WAVES %s", vcd_path);
    end

    // 总线侧的初始状态
    s_awvalid = 1'b0; s_wvalid = 1'b0; s_bready = 1'b0;
    s_arvalid = 1'b0; s_rready = 1'b0;
    s_awaddr = 32'h0; s_wdata = 32'h0; s_wstrb = 4'h0; s_araddr = 32'h0;

    // 外部复位：先让外壳自己的状态（RESET=1、门控=1）就位
    repeat (4) @(posedge clk);
    @(negedge clk);
    rst = 1'b0;

    // ---- AXI 从接口探针：未映射地址应当返回 SLVERR ----
    host_read(CSR_BASE + 32'h20, rd_val, rd_resp);
    $display("HOST probe_unmapped=0x%08x resp=%0d", rd_val, rd_resp);
    host_read(CSR_BASE + 32'h8, rd_val, rd_resp);
    $display("HOST status_before=0x%08x resp=%0d", rd_val, rd_resp);

    if (no_boot) begin
      repeat (20) @(posedge clk);
      $display("HOST no_boot_done");
      $fclose(trace_fd);
      $finish;
    end

    // ---- 第 1 步：把程序写进 ITCM（镜像从地址 0 开始，入口在 +ENTRY）----
    for (k = 0; k < n_words; k++) begin
      host_write(k * 4, prog_words[k], wr_resp);
      if (wr_resp != 2'b00) $display("HOST itcm_write_err addr=0x%08x resp=%0d", k * 4, wr_resp);
    end
    host_read(entry, rd_val, rd_resp);
    $display("HOST step1_words=%0d entry=0x%08x first=0x%08x resp=%0d",
             n_words, entry, rd_val, rd_resp);

    // ---- 第 2 步：写 PC_START（并读回确认）----
    host_write(CSR_BASE + 32'h4, entry, wr_resp);
    host_read(CSR_BASE + 32'h4, rd_val, rd_resp);
    $display("HOST step2_pc_start=0x%08x resp=%0d", rd_val, rd_resp);

    // ---- 第 3 步：释放时钟门控（RESET 仍为 1，让核心看到复位）----
    host_write(CSR_BASE + 32'h0, 32'h1, wr_resp);
    host_read(CSR_BASE + 32'h0, rd_val, rd_resp);
    $display("HOST step3_reset_control=0x%08x resp=%0d", rd_val, rd_resp);

    // ---- 第 4 步：释放复位 ----
    host_write(CSR_BASE + 32'h0, 32'h0, wr_resp);
    host_read(CSR_BASE + 32'h0, rd_val, rd_resp);
    $display("HOST step4_reset_control=0x%08x resp=%0d", rd_val, rd_resp);

    // ---- 第 5 步：轮询 STATUS ----
    status = 32'h0;
    while (!(status[0] || status[1]) && (cycles <= max_cycles)) begin
      host_read(CSR_BASE + 32'h8, status, rd_resp);
      if (!(status[0] || status[1])) repeat (16) @(posedge clk);
    end
    status_seen = status;
    if (status[1]) begin
      $display("HOST fault=1 status=0x%08x (核心在 mtvec=0 时进入异常)", status);
    end else if (status[0]) begin
      $display("HOST halted=1 status=0x%08x", status);
    end else begin
      $display("HOST poll_timeout status=0x%08x", status);
    end
    $display("HOST axi_txns rd=%0d wr=%0d", rd_txns, wr_txns);

    // 等核心把流水线里的写回排空，再收尾
    repeat (8) @(posedge core_clk);
    stopped_seen = 1'b1;
  end

  // ------------------------------------------------------------ 收尾
  always_ff @(posedge core_clk) begin
    if (stopped_seen) begin
      dmem_fd = $fopen(dmem_path, "w");
      for (i = 0; i < DMEM_WORDS; i++) $fdisplay(dmem_fd, "%08x", dmem[i]);
      $fclose(dmem_fd);
      $fclose(trace_fd);
      $display("HALTED cycles=%0d latency=%0d halted=%0d fault=%0d status=0x%08x",
               cycles, latency, core_halted, core_fault, status_seen);
      $finish;
    end else if (cycles > max_cycles) begin
      $fdisplay(trace_fd, "TIMEOUT after %0d cycles", cycles);
      $fclose(trace_fd);
      $display("TIMEOUT after %0d cycles", cycles);
      $finish;
    end
  end

  always #5 clk = ~clk;

  // 总线看门狗：AXI 握手卡住时核心可能一直没有时钟（cycles 不涨），
  // 所以额外按总线周期数兜底，避免仿真永远挂着。
  always_ff @(posedge clk) begin
    if (!rst) bus_cycles <= bus_cycles + 1;
  end

  always_ff @(posedge clk) begin
    if (bus_cycles > max_cycles) begin
      if (trace_fd != 0) begin
        $fdisplay(trace_fd, "TIMEOUT after %0d bus cycles", bus_cycles);
        $fclose(trace_fd);
      end
      $display("TIMEOUT after %0d bus cycles（主机/总线卡住）", bus_cycles);
      $finish;
    end
  end

endmodule

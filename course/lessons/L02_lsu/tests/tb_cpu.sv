// CoralNPU 教学仓 L02 测试平台（由课程提供，学员不需要修改）
//
// 与 L01 的差别有两点：
//   1. 数据端口改成 valid/ready 握手：存储器可以"忙"若干拍才接受事务；
//   2. 多了 +LATENCY=N 参数：模拟不同速度的存储器（0 = 组合读，和 L01 一样）。
//
// 握手约定（L02 基础知识.pdf 有波形说明）：
//   * 核心把 addr/we/wmask/wdata 和 valid=1 保持住，直到 ready=1；
//   * valid=1 && ready=1 的那一拍，事务完成：
//       - 写：测试平台在该时钟上升沿按掩码写入 DTCM；
//       - 读：io_dmem_rdata 当拍有效，核心自己采样；
//   * ready=0 表示"存储器还忙"，核心必须保持请求不变并冻结后续指令。

`timescale 1ns/1ps

module tb_cpu;
  parameter int IMEM_WORDS = 2048;
  parameter int DMEM_WORDS = 8192;
  parameter logic [31:0] ITCM_BASE = 32'h0000_0000;
  parameter logic [31:0] DTCM_BASE = 32'h0001_0000;

  logic clk = 1'b0;
  logic rst = 1'b1;

  logic [31:0] imem_addr;
  logic [31:0] imem_rdata;

  logic [31:0] dmem_addr;
  logic [31:0] dmem_wdata;
  logic [31:0] dmem_rdata;
  logic [3:0]  dmem_wmask;
  logic        dmem_we;
  logic        dmem_valid;
  logic        dmem_ready;

  logic        retire_valid;
  logic [31:0] retire_pc;
  logic [31:0] retire_inst;
  logic [4:0]  retire_rd;
  logic [31:0] retire_wdata;
  logic        halted;

  logic [31:0] imem [0:IMEM_WORDS-1];
  logic [31:0] dmem [0:DMEM_WORDS-1];

  string program_path, data_path, trace_path, dmem_path;
  string vcd_path;
  int unsigned max_cycles;
  int unsigned cycles = 0;
  int trace_fd, dmem_fd, i;

  // 存储器延迟模型
  int unsigned latency = 0;
  logic        started = 1'b0;
  int unsigned wait_cnt = 0;

  cpu_core dut (
      .clk           (clk),
      .rst           (rst),
      .io_imem_addr  (imem_addr),
      .io_imem_rdata (imem_rdata),
      .io_dmem_addr  (dmem_addr),
      .io_dmem_wmask (dmem_wmask),
      .io_dmem_wdata (dmem_wdata),
      .io_dmem_we    (dmem_we),
      .io_dmem_valid (dmem_valid),
      .io_dmem_rdata (dmem_rdata),
      .io_dmem_ready (dmem_ready),
      .o_retire_valid(retire_valid),
      .o_retire_pc   (retire_pc),
      .o_retire_inst (retire_inst),
      .o_retire_rd   (retire_rd),
      .o_retire_wdata(retire_wdata),
      .o_halted      (halted)
  );

  function automatic bit in_itcm(input logic [31:0] a);
    return (a >= ITCM_BASE) && (a < ITCM_BASE + IMEM_WORDS * 4);
  endfunction

  function automatic bit in_dtcm(input logic [31:0] a);
    return (a >= DTCM_BASE) && (a < DTCM_BASE + DMEM_WORDS * 4);
  endfunction

  // 取指：组合读，固定 1 拍（L03 再讨论指令侧的延迟）
  always_comb begin
    if (in_itcm(imem_addr)) imem_rdata = imem[(imem_addr - ITCM_BASE) >> 2];
    else imem_rdata = 32'h0000_0000;
  end

  // 数据读：组合给出"当前地址所在的那个字"
  always_comb begin
    if (in_dtcm(dmem_addr)) dmem_rdata = dmem[(dmem_addr - DTCM_BASE) >> 2];
    else if (in_itcm(dmem_addr)) dmem_rdata = imem[(dmem_addr - ITCM_BASE) >> 2];
    else dmem_rdata = 32'h0000_0000;
  end

  // ready：latency=0 时永远就绪；否则每个事务要等 latency 拍
  assign dmem_ready = (latency == 0) ? 1'b1 : (started && wait_cnt == 0);

  always_ff @(posedge clk) begin
    if (rst) begin
      started  <= 1'b0;
      wait_cnt <= 0;
    end else if (latency != 0) begin
      if (!started && dmem_valid) begin
        started  <= 1'b1;
        wait_cnt <= (latency >= 1) ? latency - 1 : 0;
      end else if (started && wait_cnt != 0) begin
        wait_cnt <= wait_cnt - 1;
      end else if (started && dmem_valid && dmem_ready) begin
        started <= 1'b0;
      end
    end
  end

  // 数据写：事务完成的那一拍按掩码逐字节写入
  always_ff @(posedge clk) begin
    if (!rst && dmem_valid && dmem_ready && dmem_we && in_dtcm(dmem_addr)) begin
      logic [31:0] cur;
      cur = dmem[(dmem_addr - DTCM_BASE) >> 2];
      if (dmem_wmask[0]) cur[7:0]   = dmem_wdata[7:0];
      if (dmem_wmask[1]) cur[15:8]  = dmem_wdata[15:8];
      if (dmem_wmask[2]) cur[23:16] = dmem_wdata[23:16];
      if (dmem_wmask[3]) cur[31:24] = dmem_wdata[31:24];
      dmem[(dmem_addr - DTCM_BASE) >> 2] <= cur;
    end
  end

  always #5 clk = ~clk;

  initial begin
    program_path = "";
    data_path = "";
    trace_path = "trace.txt";
    dmem_path = "dmem.txt";
    max_cycles = 200000;
    void'($value$plusargs("PROGRAM=%s", program_path));
    void'($value$plusargs("DATA=%s", data_path));
    void'($value$plusargs("TRACE=%s", trace_path));
    void'($value$plusargs("DMEM=%s", dmem_path));
    void'($value$plusargs("MAX_CYCLES=%d", max_cycles));
    void'($value$plusargs("LATENCY=%d", latency));

    for (i = 0; i < IMEM_WORDS; i++) imem[i] = 32'h0;
    for (i = 0; i < DMEM_WORDS; i++) dmem[i] = 32'h0;
    if (program_path != "") $readmemh(program_path, imem);
    if (data_path != "") $readmemh(data_path, dmem);

    trace_fd = $fopen(trace_path, "w");
    if (trace_fd == 0) begin
      $display("无法打开 trace 文件 %s", trace_path);
      $finish;
    end

    // 波形：./learn wave <课> 会打开这个开关
    if ($test$plusargs("WAVES")) begin
      vcd_path = "waves.vcd";
      void'($value$plusargs("VCD=%s", vcd_path));
      $dumpfile(vcd_path);
      $dumpvars(0, tb_cpu);
      $display("WAVES %s", vcd_path);
    end

    rst = 1'b1;
    repeat (4) @(posedge clk);
    @(negedge clk);
    rst = 1'b0;
  end

  always_ff @(posedge clk) begin
    if (!rst) cycles <= cycles + 1;
  end

  always_ff @(posedge clk) begin
    if (!rst && retire_valid) begin
      $fdisplay(trace_fd, "%08x %08x %02x %08x", retire_pc, retire_inst, retire_rd, retire_wdata);
    end
  end

  always_ff @(posedge clk) begin
    if (!rst) begin
      if (halted) begin
        dmem_fd = $fopen(dmem_path, "w");
        for (i = 0; i < DMEM_WORDS; i++) $fdisplay(dmem_fd, "%08x", dmem[i]);
        $fclose(dmem_fd);
        $fclose(trace_fd);
        $display("HALTED cycles=%0d latency=%0d", cycles, latency);
        $finish;
      end else if (cycles > max_cycles) begin
        $fdisplay(trace_fd, "TIMEOUT after %0d cycles", cycles);
        $fclose(trace_fd);
        $display("TIMEOUT after %0d cycles", cycles);
        $finish;
      end
    end
  end
endmodule

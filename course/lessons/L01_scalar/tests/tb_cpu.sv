// CoralNPU 教学仓 L01 测试平台（由课程提供，学员不需要修改）
//
// 它做的事：
//   1. 把 program.hex 装进 ITCM、data.hex 装进 DTCM
//   2. 给被测核心 cpu_core 提供时钟/复位和组合读的存储器端口
//   3. 记录每条退休指令的 trace：pc inst rd wdata
//   4. 停机后把 DTCM 全量导出，交给 Python 检查器与黄金模型对拍
//
// 运行参数（iverilog 的 plusargs）：
//   +PROGRAM=program.hex +DATA=data.hex +TRACE=trace.txt +DMEM=dmem.txt +MAX_CYCLES=200000

`timescale 1ns/1ps

module tb_cpu;
  parameter int IMEM_WORDS = 2048;   // 8 KB ITCM
  parameter int DMEM_WORDS = 8192;   // 32 KB DTCM
  parameter logic [31:0] ITCM_BASE = 32'h0000_0000;
  parameter logic [31:0] DTCM_BASE = 32'h0001_0000;

  logic clk = 1'b0;
  logic rst = 1'b1;

  // 指令端口
  logic [31:0] imem_addr;
  logic [31:0] imem_rdata;

  // 数据端口
  logic [31:0] dmem_addr;
  logic [31:0] dmem_wdata;
  logic [31:0] dmem_rdata;
  logic [3:0]  dmem_wmask;
  logic        dmem_we;

  // 可观测性端口（对拍用）
  logic        retire_valid;
  logic [31:0] retire_pc;
  logic [31:0] retire_inst;
  logic [4:0]  retire_rd;
  logic [31:0] retire_wdata;
  logic        halted;

  logic [31:0] imem [0:IMEM_WORDS-1];
  logic [31:0] dmem [0:DMEM_WORDS-1];

  string program_path;
  string data_path;
  string trace_path;
  string dmem_path;
  int unsigned max_cycles;
  int unsigned cycles = 0;
  int trace_fd;
  int dmem_fd;
  int i;

  cpu_core dut (
      .clk           (clk),
      .rst           (rst),
      .io_imem_addr  (imem_addr),
      .io_imem_rdata (imem_rdata),
      .io_dmem_addr  (dmem_addr),
      .io_dmem_wmask (dmem_wmask),
      .io_dmem_wdata (dmem_wdata),
      .io_dmem_we    (dmem_we),
      .io_dmem_rdata (dmem_rdata),
      .o_retire_valid(retire_valid),
      .o_retire_pc   (retire_pc),
      .o_retire_inst (retire_inst),
      .o_retire_rd   (retire_rd),
      .o_retire_wdata(retire_wdata),
      .o_halted      (halted)
  );

  // ---------------------------------------------------------------- 存储器
  function automatic bit in_itcm(input logic [31:0] a);
    return (a >= ITCM_BASE) && (a < ITCM_BASE + IMEM_WORDS * 4);
  endfunction

  function automatic bit in_dtcm(input logic [31:0] a);
    return (a >= DTCM_BASE) && (a < DTCM_BASE + DMEM_WORDS * 4);
  endfunction

  always_comb begin
    if (in_itcm(imem_addr)) imem_rdata = imem[(imem_addr - ITCM_BASE) >> 2];
    else imem_rdata = 32'h0000_0000;
  end

  always_comb begin
    if (in_dtcm(dmem_addr)) dmem_rdata = dmem[(dmem_addr - DTCM_BASE) >> 2];
    else if (in_itcm(dmem_addr)) dmem_rdata = imem[(dmem_addr - ITCM_BASE) >> 2];
    else dmem_rdata = 32'h0000_0000;
  end

  always_ff @(posedge clk) begin
    if (!rst && dmem_we && in_dtcm(dmem_addr)) begin
      logic [31:0] cur;
      cur = dmem[(dmem_addr - DTCM_BASE) >> 2];
      if (dmem_wmask[0]) cur[7:0]   = dmem_wdata[7:0];
      if (dmem_wmask[1]) cur[15:8]  = dmem_wdata[15:8];
      if (dmem_wmask[2]) cur[23:16] = dmem_wdata[23:16];
      if (dmem_wmask[3]) cur[31:24] = dmem_wdata[31:24];
      dmem[(dmem_addr - DTCM_BASE) >> 2] <= cur;
    end
  end

  // ------------------------------------------------------------------ 时钟
  always #5 clk = ~clk;

  // ------------------------------------------------------------ 激励与检查
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

    // 存储器清零，保证未初始化位置可复现（否则会有 X）
    for (i = 0; i < IMEM_WORDS; i++) imem[i] = 32'h0;
    for (i = 0; i < DMEM_WORDS; i++) dmem[i] = 32'h0;
    if (program_path != "") $readmemh(program_path, imem);
    if (data_path != "") $readmemh(data_path, dmem);

    trace_fd = $fopen(trace_path, "w");
    if (trace_fd == 0) begin
      $display("无法打开 trace 文件 %s", trace_path);
      $finish;
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
        $display("HALTED cycles=%0d", cycles);
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

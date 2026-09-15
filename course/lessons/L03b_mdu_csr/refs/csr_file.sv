// CoralNPU 教学仓 L03b 参考实现：最小 CSR 寄存器堆
//
// 只实现异常处理必需的一小组 CSR：
//   0x300 mstatus   0x301 misa(只读)   0x305 mtvec
//   0x340 mscratch  0x341 mepc         0x342 mcause   0x343 mtval
//   0xF14 mhartid(只读)
//
// 读端口是组合的（EX 级用），写端口在 WB 级提交时生效（和寄存器堆写回同一个时钟沿）。
// 异常提交时由 trap_en 把 mepc/mcause 写进去。

`default_nettype none

module csr_file (
    input  logic        clk,
    input  logic        rst,
    // 读端口（组合）
    input  logic [11:0] raddr,
    output logic [31:0] rdata,
    // 写端口（WB 级提交）
    input  logic        we,
    input  logic [11:0] waddr,
    input  logic [31:0] wdata,
    // 异常提交：设置 mepc / mcause / mtval
    input  logic        trap_en,
    input  logic [31:0] trap_cause,
    input  logic [31:0] trap_epc,
    // 给核心做重定向用
    output logic [31:0] mtvec_o,
    output logic [31:0] mepc_o
);

  localparam logic [11:0] CSR_MSTATUS  = 12'h300;
  localparam logic [11:0] CSR_MISA     = 12'h301;
  localparam logic [11:0] CSR_MTVEC    = 12'h305;
  localparam logic [11:0] CSR_MSCRATCH = 12'h340;
  localparam logic [11:0] CSR_MEPC     = 12'h341;
  localparam logic [11:0] CSR_MCAUSE   = 12'h342;
  localparam logic [11:0] CSR_MTVAL    = 12'h343;
  localparam logic [11:0] CSR_MHARTID  = 12'hF14;

  localparam logic [31:0] MISA_VALUE = 32'h4000_1100;   // RV32 + I + M

  logic [31:0] mstatus, mtvec, mscratch, mepc, mcause, mtval;

  assign mtvec_o = mtvec;
  assign mepc_o  = mepc;

  always_comb begin
    unique case (raddr)
      CSR_MSTATUS:  rdata = mstatus;
      CSR_MISA:     rdata = MISA_VALUE;
      CSR_MTVEC:    rdata = mtvec;
      CSR_MSCRATCH: rdata = mscratch;
      CSR_MEPC:     rdata = mepc;
      CSR_MCAUSE:   rdata = mcause;
      CSR_MTVAL:    rdata = mtval;
      CSR_MHARTID:  rdata = 32'h0;
      default:      rdata = 32'h0;     // 未实现的地址按 0 读（本课约定）
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      mstatus  <= 32'h0;
      mtvec    <= 32'h0;
      mscratch <= 32'h0;
      mepc     <= 32'h0;
      mcause   <= 32'h0;
      mtval    <= 32'h0;
    end else begin
      if (we) begin
        unique case (waddr)
          CSR_MSTATUS:  mstatus  <= wdata;
          CSR_MTVEC:    mtvec    <= wdata;
          CSR_MSCRATCH: mscratch <= wdata;
          CSR_MEPC:     mepc     <= wdata;
          CSR_MCAUSE:   mcause   <= wdata;
          CSR_MTVAL:    mtval    <= wdata;
          default: ;                                   // misa / mhartid 只读
        endcase
      end
      if (trap_en) begin                               // 异常优先
        mepc   <= trap_epc;
        mcause <= trap_cause;
        mtval  <= 32'h0;
      end
    end
  end

endmodule

`default_nettype wire

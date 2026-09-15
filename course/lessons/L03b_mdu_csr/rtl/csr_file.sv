// CoralNPU 教学仓 L03b 骨架：最小 CSR 寄存器堆
//
// ============================ 你来实现 ============================
// 需要实现的 CSR（其余地址按 0 读、写忽略）：
//   0x300 mstatus（可读写）   0x301 misa（只读，固定 0x40001100）
//   0x305 mtvec（异常入口）    0x340 mscratch
//   0x341 mepc（异常返回地址）  0x342 mcause（异常原因）
//   0x343 mtval                0xF14 mhartid（只读，0）
//
// 三个要点：
//   1. 读端口是组合的（EX 级要用），写端口在 WB 级提交时生效；
//   2. misa / mhartid 只读，写它们没有效果；
//   3. trap_en 有效时要写入 mepc / mcause / mtval，而且它的优先级高于普通 CSR 写
//      （异常提交必须赢过同拍的普通写）。
// ==================================================================

`default_nettype none

module csr_file (
    input  logic        clk,
    input  logic        rst,
    input  logic [11:0] raddr,
    output logic [31:0] rdata,
    input  logic        we,
    input  logic [11:0] waddr,
    input  logic [31:0] wdata,
    input  logic        trap_en,
    input  logic [31:0] trap_cause,
    input  logic [31:0] trap_epc,
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
  localparam logic [31:0] MISA_VALUE   = 32'h4000_1100;   // RV32 + I + M

  logic [31:0] mstatus, mtvec, mscratch, mepc, mcause, mtval;

  assign mtvec_o = mtvec;
  assign mepc_o  = mepc;

  // TODO 1：读端口（组合）——按 raddr 选择，misa/mhartid 返回固定值，其余 0
  always_comb begin
    unique case (raddr)
      CSR_MSTATUS:  rdata = mstatus;
      CSR_MISA:     rdata = 32'h40001100;
      CSR_MTVEC:    rdata = mtvec;
      CSR_MSCRATCH: rdata = mscratch;
      CSR_MEPC:     rdata = mepc;
      CSR_MCAUSE:   rdata = mcause;
      CSR_MTVAL:    rdata = mtval;
      CSR_MHARTID:  rdata = 0;
      default:      rdata = 0;
    endcase
  end

  // TODO 2：写端口（时序）——reset 清零；we 时按 waddr 写入；
  //         trap_en 时写 mepc/mcause/mtval，并且优先级最高
  always_ff @(posedge clk) begin
    if (rst) begin
      mstatus  <= 32'h0;
      mtvec    <= 32'h0;
      mscratch <= 32'h0;
      mepc     <= 32'h0;
      mcause   <= 32'h0;
      mtval    <= 32'h0;
    end else begin
      // TODO
      if (we) begin
        unique case (waddr)
          CSR_MSTATUS:  mstatus   = wdata;
          CSR_MTVEC:    mtvec     = wdata;
          CSR_MSCRATCH: mscratch  = wdata;
          CSR_MEPC:     mepc      = wdata;
          CSR_MCAUSE:   mcause    = wdata;
          CSR_MTVAL:    mtval     = wdata;
          default: ;  // 只读寄存器
        endcase
      end

      if (trap_en) begin
        mepc    <= trap_epc;    // 异常指令地址
        mcause  <= trap_cause;  // 异常原因, 最高位1表示中断，0表示同步异常
        mtval   <= 32'h0;       // 异常附加信息
      end
    end
  end

endmodule

`default_nettype wire

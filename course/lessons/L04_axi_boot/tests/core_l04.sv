// CoralNPU 教学仓 L04：课程提供的核心（= L03b 的核心 + 一个 o_fault 输出）
//
// 你不需要改这个文件。与 L03b 的 core_l03b.sv 相比只有两处不同：
//   1. 模块名改成 core_l04；
//   2. 多了一个 o_fault 输出：当核心进入异常、而 mtvec == 0（没有安装处理程序）时，
//      置位 o_fault 并冻结核心。这样主机可以通过外壳的 STATUS.FAULT 位观察到
//      "程序跑飞了"，而不是让仿真一直跑到超时。
//
// 其余部分照旧：它把两个模块接进流水线：
//   * mdu      —— EX 级的乘除法（组合），你要实现
//   * csr_file —— CSR 寄存器堆与异常寄存（mepc/mcause），你要实现
//
// 异常的处理方式与分支类似：在 EX 级检测到异常/ mret 时重定向 PC，
// 冲刷已经取进来的错路指令；异常指令本身仍然流到 WB 退休（trace 里能看到它），
// 并在退休时把 mepc/mcause 写进 CSR。

`default_nettype none

module core_l04 (
    input  logic        clk,
    input  logic        rst,
    input  logic [31:0] i_pc_start,      // 复位时装载的启动 PC（来自外壳的 PC_START）
    output logic [31:0] io_imem_addr,
    input  logic [31:0] io_imem_rdata,
    output logic [31:0] io_dmem_addr,
    output logic [3:0]  io_dmem_wmask,
    output logic [31:0] io_dmem_wdata,
    output logic        io_dmem_we,
    output logic        io_dmem_valid,
    input  logic [31:0] io_dmem_rdata,
    input  logic        io_dmem_ready,
    output logic        o_retire_valid,
    output logic [31:0] o_retire_pc,
    output logic [31:0] o_retire_inst,
    output logic [4:0]  o_retire_rd,
    output logic [31:0] o_retire_wdata,
    output logic        o_halted,
    output logic        o_fault
);

  localparam logic [31:0] INSTR_MPAUSE = 32'h0800_0073;
  localparam logic [31:0] INSTR_EBREAK = 32'h0010_0073;
  localparam logic [31:0] INSTR_ECALL  = 32'h0000_0073;
  localparam logic [31:0] INSTR_MRET   = 32'h3020_0073;

  localparam logic [3:0] ALU_ADD  = 4'd0;
  localparam logic [3:0] ALU_SUB  = 4'd1;
  localparam logic [3:0] ALU_SLL  = 4'd2;
  localparam logic [3:0] ALU_SLT  = 4'd3;
  localparam logic [3:0] ALU_SLTU = 4'd4;
  localparam logic [3:0] ALU_XOR  = 4'd5;
  localparam logic [3:0] ALU_SRL  = 4'd6;
  localparam logic [3:0] ALU_SRA  = 4'd7;
  localparam logic [3:0] ALU_OR   = 4'd8;
  localparam logic [3:0] ALU_AND  = 4'd9;

  localparam logic [31:0] CAUSE_ILLEGAL = 32'd2;
  localparam logic [31:0] CAUSE_EBREAK  = 32'd3;
  localparam logic [31:0] CAUSE_ECALL   = 32'd11;

  // ------------------------------------------------------------ 阶段寄存器
  logic [31:0] pc;
  logic        stopped;
  // 仿真的初值：核心在"时钟门控 + 复位"期间没有时钟沿，寄存器不会被复位，
  // 所以 halted/fault 这两个状态输出给一个确定的 0，主机启动前读 STATUS 才有意义。
  logic        halted_q = 1'b0;
  logic        fault_q  = 1'b0;      // L04：异常且 mtvec == 0 → 核心级 fault
  logic [31:0] regs[0:31];

  assign o_halted = halted_q;
  assign o_fault = fault_q;

  logic [31:0] id_pc, id_inst;
  logic        id_valid;

  logic [31:0] ex_pc, ex_inst, ex_rs1_val, ex_rs2_val;
  logic        ex_valid;

  logic [31:0] mem_pc, mem_inst, mem_alu_y, mem_rs2_val;
  logic        mem_reg_we, mem_is_load, mem_is_store, mem_valid;
  logic        mem_csr_we, mem_trap;
  logic [11:0] mem_csr_addr;
  logic [31:0] mem_csr_wdata, mem_trap_cause, mem_trap_epc;

  logic [31:0] wb_pc, wb_inst, wb_data;
  logic        wb_reg_we, wb_valid, wb_csr_we, wb_trap;
  logic [11:0] wb_csr_addr;
  logic [31:0] wb_csr_wdata, wb_trap_cause, wb_trap_epc;

  assign io_imem_addr = pc;

  // ---------------------------------------------------------------- 译码辅助
  function automatic logic [6:0] op_of(input logic [31:0] i);  op_of  = i[6:0];   endfunction
  function automatic logic [2:0] f3_of(input logic [31:0] i);  f3_of  = i[14:12]; endfunction
  function automatic logic [6:0] f7_of(input logic [31:0] i);  f7_of  = i[31:25]; endfunction
  function automatic logic [4:0] rs1_of(input logic [31:0] i); rs1_of = i[19:15]; endfunction
  function automatic logic [4:0] rs2_of(input logic [31:0] i); rs2_of = i[24:20]; endfunction
  function automatic logic [4:0] rd_of(input logic [31:0] i);  rd_of  = i[11:7];  endfunction
  function automatic logic [31:0] imm_i_of(input logic [31:0] i); imm_i_of = {{20{i[31]}}, i[31:20]}; endfunction
  function automatic logic [31:0] imm_s_of(input logic [31:0] i); imm_s_of = {{20{i[31]}}, i[31:25], i[11:7]}; endfunction
  function automatic logic [31:0] imm_b_of(input logic [31:0] i); imm_b_of = {{20{i[31]}}, i[7], i[30:25], i[11:8], 1'b0}; endfunction
  function automatic logic [31:0] imm_u_of(input logic [31:0] i); imm_u_of = {i[31:12], 12'b0}; endfunction
  function automatic logic [31:0] imm_j_of(input logic [31:0] i); imm_j_of = {{11{i[31]}}, i[31], i[19:12], i[20], i[30:21], 1'b0}; endfunction

  function automatic logic is_halt_f(input logic [31:0] i);
    is_halt_f = (i == INSTR_MPAUSE);
  endfunction

  function automatic logic uses_rs1_of(input logic [31:0] i);
    logic [6:0] op;
    op = op_of(i);
    uses_rs1_of = (op == 7'b0110011) || (op == 7'b0010011) || (op == 7'b0000011) ||
                  (op == 7'b0100011) || (op == 7'b1100011) || (op == 7'b1100111);
  endfunction

  function automatic logic uses_rs2_of(input logic [31:0] i);
    logic [6:0] op;
    op = op_of(i);
    uses_rs2_of = (op == 7'b0110011) || (op == 7'b0100011) || (op == 7'b1100011);
  endfunction

  // ---------------------------------------------------------------- ID 阶段
  logic id_bypass_rs1, id_bypass_rs2;
  logic [31:0] id_rs1_val, id_rs2_val;
  assign id_bypass_rs1 = wb_valid & wb_reg_we & (rd_of(wb_inst) != 5'd0) &
                         (rd_of(wb_inst) == rs1_of(id_inst));
  assign id_bypass_rs2 = wb_valid & wb_reg_we & (rd_of(wb_inst) != 5'd0) &
                         (rd_of(wb_inst) == rs2_of(id_inst));
  assign id_rs1_val = (rs1_of(id_inst) == 5'd0) ? 32'h0 :
                      id_bypass_rs1 ? wb_data : regs[rs1_of(id_inst)];
  assign id_rs2_val = (rs2_of(id_inst) == 5'd0) ? 32'h0 :
                      id_bypass_rs2 ? wb_data : regs[rs2_of(id_inst)];

  // ---------------------------------------------------------------- EX 阶段
  logic [6:0]  ex_op;
  logic [2:0]  ex_f3;
  logic        ex_reg_we, ex_is_load, ex_is_store, ex_is_branch, ex_is_jal, ex_is_jalr;
  logic        ex_is_halt, ex_br_taken, ex_redirect, ex_illegal;
  logic        ex_is_mdu, ex_is_csr, ex_is_mret, ex_is_ecall, ex_is_ebreak, ex_trap;
  logic [3:0]  ex_alu_op;
  logic [31:0] ex_imm_sel, ex_target, ex_pc_plus4, ex_wb_value;
  logic [31:0] fwd_a, fwd_b, alu_a, alu_b, alu_y, mdu_y;
  logic        alu_zero;
  logic [11:0] ex_csr_addr;
  logic [31:0] ex_csr_rdata, ex_csr_src, ex_csr_wdata, ex_trap_cause;
  logic        ex_csr_we;
  logic [31:0] csr_mtvec, csr_mepc;
  logic [31:0] ex_csr_rdata_f, csr_mepc_f, csr_mtvec_f;

  assign ex_op       = op_of(ex_inst);
  assign ex_f3       = f3_of(ex_inst);
  assign ex_pc_plus4 = ex_pc + 32'd4;

  always_comb begin
    fwd_a = ex_rs1_val;
    fwd_b = ex_rs2_val;
    if (mem_valid && mem_reg_we && !mem_is_load && rd_of(mem_inst) != 5'd0 &&
        rd_of(mem_inst) == rs1_of(ex_inst))
      fwd_a = mem_alu_y;
    else if (wb_valid && wb_reg_we && rd_of(wb_inst) != 5'd0 &&
             rd_of(wb_inst) == rs1_of(ex_inst))
      fwd_a = wb_data;

    if (mem_valid && mem_reg_we && !mem_is_load && rd_of(mem_inst) != 5'd0 &&
        rd_of(mem_inst) == rs2_of(ex_inst))
      fwd_b = mem_alu_y;
    else if (wb_valid && wb_reg_we && rd_of(wb_inst) != 5'd0 &&
             rd_of(wb_inst) == rs2_of(ex_inst))
      fwd_b = wb_data;
  end

  always_comb begin
    ex_reg_we    = 1'b0;
    ex_is_load   = 1'b0;
    ex_is_store  = 1'b0;
    ex_is_branch = 1'b0;
    ex_is_jal    = 1'b0;
    ex_is_jalr   = 1'b0;
    ex_is_halt   = 1'b0;
    ex_illegal   = 1'b0;
    ex_br_taken  = 1'b0;
    ex_alu_op    = ALU_ADD;
    ex_imm_sel   = imm_i_of(ex_inst);
    ex_is_mdu    = 1'b0;
    ex_is_csr    = 1'b0;
    ex_is_mret   = 1'b0;
    ex_is_ecall  = 1'b0;
    ex_is_ebreak = 1'b0;
    ex_csr_we    = 1'b0;

    unique case (ex_op)
      7'b0110111: begin ex_reg_we = 1'b1; ex_imm_sel = imm_u_of(ex_inst); end
      7'b0010111: begin ex_reg_we = 1'b1; ex_imm_sel = imm_u_of(ex_inst); end
      7'b1101111: begin ex_reg_we = 1'b1; ex_is_jal  = 1'b1; end
      7'b1100111: begin ex_reg_we = 1'b1; ex_is_jalr = 1'b1; end
      7'b1100011: begin
        ex_is_branch = 1'b1;
        unique case (ex_f3)
          3'b000: ex_br_taken = (fwd_a == fwd_b);
          3'b001: ex_br_taken = (fwd_a != fwd_b);
          3'b100: ex_br_taken = ($signed(fwd_a) < $signed(fwd_b));
          3'b101: ex_br_taken = ($signed(fwd_a) >= $signed(fwd_b));
          3'b110: ex_br_taken = (fwd_a < fwd_b);
          3'b111: ex_br_taken = (fwd_a >= fwd_b);
          default: ex_illegal = 1'b1;
        endcase
      end
      7'b0000011: begin ex_reg_we = 1'b1; ex_is_load  = 1'b1; end
      7'b0100011: begin ex_is_store = 1'b1; ex_imm_sel = imm_s_of(ex_inst); end
      7'b0010011: begin
        ex_reg_we  = 1'b1;
        ex_imm_sel = imm_i_of(ex_inst);
        unique case (ex_f3)
          3'b000:  ex_alu_op = ALU_ADD;
          3'b010:  ex_alu_op = ALU_SLT;
          3'b011:  ex_alu_op = ALU_SLTU;
          3'b100:  ex_alu_op = ALU_XOR;
          3'b110:  ex_alu_op = ALU_OR;
          3'b111:  ex_alu_op = ALU_AND;
          3'b001:  ex_alu_op = ALU_SLL;
          3'b101:  ex_alu_op = ex_inst[30] ? ALU_SRA : ALU_SRL;
          default: ex_illegal = 1'b1;
        endcase
      end
      7'b0110011: begin
        ex_reg_we = 1'b1;
        if (f7_of(ex_inst) == 7'b0000001) ex_is_mdu = 1'b1;   // M 扩展
        else begin
          unique case (ex_f3)
            3'b000:  ex_alu_op = ex_inst[30] ? ALU_SUB : ALU_ADD;
            3'b001:  ex_alu_op = ALU_SLL;
            3'b010:  ex_alu_op = ALU_SLT;
            3'b011:  ex_alu_op = ALU_SLTU;
            3'b100:  ex_alu_op = ALU_XOR;
            3'b101:  ex_alu_op = ex_inst[30] ? ALU_SRA : ALU_SRL;
            3'b110:  ex_alu_op = ALU_OR;
            3'b111:  ex_alu_op = ALU_AND;
            default: ex_illegal = 1'b1;
          endcase
        end
      end
      7'b0001111: ;                                            // fence
      7'b1110011: begin
        if (ex_f3 != 3'b000) begin                             // Zicsr
          ex_is_csr = 1'b1;
          ex_reg_we = 1'b1;                                    // 读出的旧值写回 rd
          // set/clear 且 rs1=x0 时不写 CSR（规范要求）
          ex_csr_we = !((ex_f3 == 3'b010 || ex_f3 == 3'b011 ||
                         ex_f3 == 3'b110 || ex_f3 == 3'b111) && rs1_of(ex_inst) == 5'd0);
        end else if (ex_inst == INSTR_MPAUSE) begin
          ex_is_halt = 1'b1;
        end else if (ex_inst == INSTR_ECALL) begin
          ex_is_ecall = 1'b1;
        end else if (ex_inst == INSTR_EBREAK) begin
          ex_is_ebreak = 1'b1;
        end else if (ex_inst == INSTR_MRET) begin
          ex_is_mret = 1'b1;
        end else begin
          ex_illegal = 1'b1;
        end
      end
      default: ex_illegal = 1'b1;
    endcase
  end

  assign alu_a = (ex_op == 7'b0010111) ? ex_pc : fwd_a;
  assign alu_b = (ex_op == 7'b0110011) ? fwd_b : ex_imm_sel;

  alu32 u_alu (.a(alu_a), .b(alu_b), .op(ex_alu_op), .y(alu_y), .zero(alu_zero));

  mdu u_mdu (.a(fwd_a), .b(fwd_b), .op(ex_f3), .y(mdu_y));

  // ---- CSR 读写
  // CSR 也会产生数据冒险：`csrw mepc, x` 紧跟 `mret` 时，mret 在 EX 读到的还是旧值。
  // 处理办法与寄存器堆旁路一致：MEM/WB 里有对同一地址的待提交写，就用它的值。
  assign ex_csr_addr = ex_inst[31:20];
  assign ex_csr_src  = (ex_f3 >= 3'b101) ? {27'b0, rs1_of(ex_inst)} : fwd_a;
  always_comb begin
    ex_csr_rdata_f = ex_csr_rdata;
    if (mem_valid && mem_csr_we && mem_csr_addr == ex_csr_addr)
      ex_csr_rdata_f = mem_csr_wdata;
    else if (wb_valid && wb_csr_we && wb_csr_addr == ex_csr_addr)
      ex_csr_rdata_f = wb_csr_wdata;

    csr_mepc_f = csr_mepc;
    if (mem_valid && mem_csr_we && mem_csr_addr == 12'h341)
      csr_mepc_f = mem_csr_wdata;
    else if (wb_valid && wb_csr_we && wb_csr_addr == 12'h341)
      csr_mepc_f = wb_csr_wdata;

    csr_mtvec_f = csr_mtvec;
    if (mem_valid && mem_csr_we && mem_csr_addr == 12'h305)
      csr_mtvec_f = mem_csr_wdata;
    else if (wb_valid && wb_csr_we && wb_csr_addr == 12'h305)
      csr_mtvec_f = wb_csr_wdata;
  end
  always_comb begin
    if (ex_f3 == 3'b001 || ex_f3 == 3'b101)      ex_csr_wdata = ex_csr_src;           // rw
    else if (ex_f3 == 3'b010 || ex_f3 == 3'b110) ex_csr_wdata = ex_csr_rdata_f | ex_csr_src;
    else                                        ex_csr_wdata = ex_csr_rdata_f & ~ex_csr_src;
  end

  csr_file u_csr (
      .clk       (clk),
      .rst       (rst),
      .raddr     (ex_csr_addr),
      .rdata     (ex_csr_rdata),
      .we        (wb_valid & wb_csr_we),
      .waddr     (wb_csr_addr),
      .wdata     (wb_csr_wdata),
      .trap_en   (wb_valid & wb_trap),
      .trap_cause(wb_trap_cause),
      .trap_epc  (wb_trap_epc),
      .mtvec_o   (csr_mtvec),
      .mepc_o    (csr_mepc)
  );

  // ---- 异常检测与重定向
  assign ex_trap       = ex_valid & (ex_is_ecall | ex_is_ebreak | ex_illegal);
  assign ex_trap_cause = ex_is_ecall  ? CAUSE_ECALL :
                         ex_is_ebreak ? CAUSE_EBREAK : CAUSE_ILLEGAL;

  assign ex_target = ex_is_halt ? ex_pc :
                     ex_trap   ? csr_mtvec_f :
                     ex_is_mret ? csr_mepc_f :
                     ex_is_jalr ? ((fwd_a + imm_i_of(ex_inst)) & ~32'd1) :
                     ex_is_jal  ? (ex_pc + imm_j_of(ex_inst)) :
                                  (ex_pc + imm_b_of(ex_inst));

  assign ex_redirect = ex_valid & (ex_br_taken | ex_is_jal | ex_is_jalr |
                                   ex_is_halt | ex_is_mret | ex_trap);

  assign ex_wb_value = ex_is_csr   ? ex_csr_rdata_f :
                       ex_is_mdu   ? mdu_y :
                       (ex_is_jal | ex_is_jalr) ? ex_pc_plus4 :
                       (ex_op == 7'b0110111)    ? imm_u_of(ex_inst) : alu_y;

  // ------------------------------------------------------------- MEM 级：LSU
  logic        lsu_req_valid, lsu_busy, lsu_done;
  logic [31:0] lsu_rdata;
  logic        mem_op, lsu_wait;

  assign mem_op        = mem_valid & (mem_is_load | mem_is_store);
  assign lsu_req_valid = mem_op & ~lsu_busy;
  assign lsu_wait      = mem_op & ~lsu_done;

  lsu u_lsu (
      .clk(clk), .rst(rst),
      .req_valid(lsu_req_valid), .req_write(mem_is_store), .req_addr(mem_alu_y),
      .req_funct3(f3_of(mem_inst)), .req_wdata(mem_rs2_val),
      .dmem_valid(io_dmem_valid), .dmem_we(io_dmem_we), .dmem_addr(io_dmem_addr),
      .dmem_wmask(io_dmem_wmask), .dmem_wdata(io_dmem_wdata),
      .dmem_rdata(io_dmem_rdata), .dmem_ready(io_dmem_ready),
      .busy(lsu_busy), .done(lsu_done), .rdata(lsu_rdata)
  );

  logic [31:0] mem_wb_value;
  assign mem_wb_value = mem_is_load ? lsu_rdata : mem_alu_y;

  // ------------------------------------------------------- 冒险检测（ID 级）
  logic load_use_stall;
  assign load_use_stall = ex_valid & ex_is_load & id_valid & (rd_of(ex_inst) != 5'd0) &
                          ((uses_rs1_of(id_inst) & (rs1_of(id_inst) == rd_of(ex_inst))) |
                           (uses_rs2_of(id_inst) & (rs2_of(id_inst) == rd_of(ex_inst))));

  logic stall_all, stall_bubble;
  assign stall_all    = lsu_wait;
  assign stall_bubble = load_use_stall;

  // ------------------------------------------------------------ WB 级：提交
  assign o_retire_valid = wb_valid & ~stall_all & ~o_halted;
  assign o_retire_pc    = wb_pc;
  assign o_retire_inst  = wb_inst;
  assign o_retire_rd    = (wb_reg_we && rd_of(wb_inst) != 5'd0) ? rd_of(wb_inst) : 5'd0;
  assign o_retire_wdata = (wb_reg_we && rd_of(wb_inst) != 5'd0) ? wb_data : 32'h0;

  logic wb_is_halt;
  assign wb_is_halt = wb_valid & (wb_inst == INSTR_MPAUSE);

  logic ex_imm_is_addr;
  assign ex_imm_is_addr = ex_is_load | ex_is_store;

`ifdef L03B_DEBUG
  always_ff @(posedge clk) begin
    if (!rst && (ex_is_mret || ex_is_csr || ex_trap))
      $display("[CSR] pc=%04x inst=%08x mret=%b csr=%b trap=%b addr=%03x rdata=%08x rdata_f=%08x we=%b wdata=%08x | MEM v=%b we=%b addr=%03x wdata=%08x | WB v=%b we=%b addr=%03x wdata=%08x | mepc=%08x mepc_f=%08x target=%08x redirect=%b",
               ex_pc, ex_inst, ex_is_mret, ex_is_csr, ex_trap, ex_csr_addr, ex_csr_rdata, ex_csr_rdata_f,
               ex_csr_we, ex_csr_wdata, mem_valid, mem_csr_we, mem_csr_addr, mem_csr_wdata,
               wb_valid, wb_csr_we, wb_csr_addr, wb_csr_wdata, csr_mepc, csr_mepc_f, ex_target, ex_redirect);
  end
`endif

  // ---------------------------------------------------------------- 时序更新
  always_ff @(posedge clk) begin
    if (rst) begin
      pc       <= i_pc_start;
      stopped  <= 1'b0;
      fault_q  <= 1'b0;
      halted_q <= 1'b0;
      id_valid <= 1'b0;
      ex_valid <= 1'b0;
      mem_valid <= 1'b0;
      wb_valid  <= 1'b0;
      mem_reg_we <= 1'b0; mem_csr_we <= 1'b0; mem_trap <= 1'b0;
      wb_reg_we  <= 1'b0; wb_csr_we  <= 1'b0; wb_trap  <= 1'b0;
      for (int unsigned i = 0; i < 32; i++) regs[i] <= 32'h0;
    end else if (stall_all) begin
      // 冻结：等待 LSU（什么都不改）
    end else begin
      if (ex_redirect)  pc <= ex_target;
      else if (stopped) pc <= pc;
      else if (!stall_bubble) pc <= pc + 32'd4;

      if (ex_redirect || stopped) begin
        id_valid <= 1'b0;
      end else if (stall_bubble) begin
        id_valid <= id_valid;
      end else begin
        id_pc    <= pc;
        id_inst  <= io_imem_rdata;
        id_valid <= 1'b1;
      end

      if (ex_redirect || stall_bubble) begin
        ex_valid <= 1'b0;
      end else begin
        ex_pc      <= id_pc;
        ex_inst    <= id_inst;
        ex_rs1_val <= id_rs1_val;
        ex_rs2_val <= id_rs2_val;
        ex_valid   <= id_valid;
      end

      mem_pc        <= ex_pc;
      mem_inst      <= ex_inst;
      mem_alu_y     <= ex_imm_is_addr ? alu_y : ex_wb_value;
      mem_rs2_val   <= fwd_b;
      mem_reg_we    <= ex_reg_we & ex_valid & ~ex_trap;   // 异常指令不写寄存器
      mem_is_load   <= ex_is_load  & ex_valid;
      mem_is_store  <= ex_is_store & ex_valid;
      mem_csr_we    <= ex_csr_we   & ex_valid & ~ex_trap;
      mem_csr_addr  <= ex_csr_addr;
      mem_csr_wdata <= ex_csr_wdata;
      mem_trap      <= ex_trap;
      mem_trap_cause<= ex_trap_cause;
      mem_trap_epc  <= ex_pc;
      mem_valid     <= ex_valid;

      wb_pc         <= mem_pc;
      wb_inst       <= mem_inst;
      wb_data       <= mem_wb_value;
      wb_reg_we     <= mem_reg_we;
      wb_csr_we     <= mem_csr_we;
      wb_csr_addr   <= mem_csr_addr;
      wb_csr_wdata  <= mem_csr_wdata;
      wb_trap       <= mem_trap;
      wb_trap_cause <= mem_trap_cause;
      wb_trap_epc   <= mem_trap_epc;
      wb_valid      <= mem_valid;

      if (wb_is_halt)            halted_q <= 1'b1;
      if (ex_valid & ex_is_halt) stopped  <= 1'b1;
      // L04：异常发生时如果 mtvec 还是 0（没有处理程序），就是"跑飞了"：
      // 置 fault 并冻结，等主机读 STATUS 观察。
      if (ex_valid & ex_trap & (csr_mtvec_f == 32'h0)) begin
        fault_q <= 1'b1;
        stopped <= 1'b1;
      end
      if (wb_valid && wb_reg_we && rd_of(wb_inst) != 5'd0) regs[rd_of(wb_inst)] <= wb_data;
      regs[0] <= 32'h0;
    end
  end

endmodule

`default_nettype wire

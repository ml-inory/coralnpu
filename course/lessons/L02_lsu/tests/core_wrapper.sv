// CoralNPU 教学仓 L02 参考实现：把访存交给独立的 LSU 模块
//
// 这一版的核心与 L01 几乎一样，区别只有两点：
//   1. 访存指令不再由核心直接驱动 dmem，而是发一条请求给 lsu；
//   2. 核心必须会"等"：LSU 没做完（busy）时冻结 PC 和寄存器写回，
//      做完（done）的那一拍才提交这条指令（写回 + 打印 trace + 前进 PC）。
//
// 本文件由课程提供（作为 L02 的起点），L02 需要你实现的是 lsu.sv。
// 你也可以把自己的 L01 实现搬过来替换这里，只要保持同样的端口和提交语义。

`default_nettype none

module cpu_core (
    input  logic        clk,
    input  logic        rst,
    // 指令端口
    output logic [31:0] io_imem_addr,
    input  logic [31:0] io_imem_rdata,
    // 数据端口（valid/ready 握手，由 LSU 驱动）
    output logic [31:0] io_dmem_addr,
    output logic [3:0]  io_dmem_wmask,
    output logic [31:0] io_dmem_wdata,
    output logic        io_dmem_we,
    output logic        io_dmem_valid,
    input  logic [31:0] io_dmem_rdata,
    input  logic        io_dmem_ready,
    // 可观测性端口
    output logic        o_retire_valid,
    output logic [31:0] o_retire_pc,
    output logic [31:0] o_retire_inst,
    output logic [4:0]  o_retire_rd,
    output logic [31:0] o_retire_wdata,
    output logic        o_halted
);

  localparam logic [31:0] INSTR_MPAUSE = 32'h0800_0073;
  localparam logic [31:0] INSTR_EBREAK = 32'h0010_0073;
  localparam logic [31:0] INSTR_ECALL  = 32'h0000_0073;

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

  logic [31:0] pc;
  logic [31:0] regs[0:31];

  assign io_imem_addr = pc;
  logic [31:0] inst;
  assign inst = io_imem_rdata;

  logic [6:0] opcode;
  logic [2:0] funct3;
  logic [6:0] funct7;
  logic [4:0] rd, rs1, rs2;
  assign opcode = inst[6:0];
  assign funct3 = inst[14:12];
  assign funct7 = inst[31:25];
  assign rd     = inst[11:7];
  assign rs1    = inst[19:15];
  assign rs2    = inst[24:20];

  logic [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
  assign imm_i = {{20{inst[31]}}, inst[31:20]};
  assign imm_s = {{20{inst[31]}}, inst[31:25], inst[11:7]};
  assign imm_b = {{20{inst[31]}}, inst[7], inst[30:25], inst[11:8], 1'b0};
  assign imm_u = {inst[31:12], 12'b0};
  assign imm_j = {{11{inst[31]}}, inst[31], inst[19:12], inst[20], inst[30:21], 1'b0};

  logic [31:0] rs1_val, rs2_val;
  assign rs1_val = (rs1 == 5'd0) ? 32'h0 : regs[rs1];
  assign rs2_val = (rs2 == 5'd0) ? 32'h0 : regs[rs2];

  // ------------------------------------------------------------- 译码/控制
  logic [31:0] alu_a, alu_b, alu_y;
  logic [3:0]  alu_op;
  logic        alu_zero;
  logic [31:0] alu_result, pc_plus4, next_pc;
  logic        reg_we, is_load, is_store, halt_inst, illegal_inst, br_taken;

  assign pc_plus4 = pc + 32'd4;

  always_comb begin
    alu_a  = rs1_val;
    alu_b  = imm_i;
    alu_op = ALU_ADD;

    next_pc      = pc_plus4;
    reg_we       = 1'b0;
    is_load      = 1'b0;
    is_store     = 1'b0;
    halt_inst    = 1'b0;
    illegal_inst = 1'b0;
    br_taken     = 1'b0;

    unique case (opcode)
      7'b0110111: reg_we = 1'b1;                          // lui
      7'b0010111: begin                                   // auipc
        alu_a  = pc;
        alu_b  = imm_u;
        reg_we = 1'b1;
      end
      7'b1101111: begin                                   // jal
        next_pc = pc + imm_j;
        reg_we  = 1'b1;
      end
      7'b1100111: begin                                   // jalr
        alu_op  = ALU_ADD;
        next_pc = alu_y & ~32'd1;
        reg_we  = 1'b1;
      end
      7'b1100011: begin                                   // 分支
        unique case (funct3)
          3'b000:  br_taken = (rs1_val == rs2_val);
          3'b001:  br_taken = (rs1_val != rs2_val);
          3'b100:  br_taken = ($signed(rs1_val) < $signed(rs2_val));
          3'b101:  br_taken = ($signed(rs1_val) >= $signed(rs2_val));
          3'b110:  br_taken = (rs1_val < rs2_val);
          3'b111:  br_taken = (rs1_val >= rs2_val);
          default: illegal_inst = 1'b1;
        endcase
        next_pc = br_taken ? (pc + imm_b) : pc_plus4;
      end
      7'b0000011: begin                                   // load：地址 = rs1 + imm_i
        is_load = 1'b1;
        reg_we  = 1'b1;
      end
      7'b0100011: begin                                   // store：地址 = rs1 + imm_s
        alu_b    = imm_s;
        is_store = 1'b1;
      end
      7'b0010011: begin                                   // OP-IMM
        reg_we = 1'b1;
        unique case (funct3)
          3'b000:  alu_op = ALU_ADD;
          3'b010:  alu_op = ALU_SLT;
          3'b011:  alu_op = ALU_SLTU;
          3'b100:  alu_op = ALU_XOR;
          3'b110:  alu_op = ALU_OR;
          3'b111:  alu_op = ALU_AND;
          3'b001:  alu_op = ALU_SLL;
          3'b101:  alu_op = inst[30] ? ALU_SRA : ALU_SRL;
          default: illegal_inst = 1'b1;
        endcase
      end
      7'b0110011: begin                                   // OP
        reg_we = 1'b1;
        alu_b  = rs2_val;
        if (funct7 == 7'b0000001) illegal_inst = 1'b1;
        unique case (funct3)
          3'b000:  alu_op = inst[30] ? ALU_SUB : ALU_ADD;
          3'b001:  alu_op = ALU_SLL;
          3'b010:  alu_op = ALU_SLT;
          3'b011:  alu_op = ALU_SLTU;
          3'b100:  alu_op = ALU_XOR;
          3'b101:  alu_op = inst[30] ? ALU_SRA : ALU_SRL;
          3'b110:  alu_op = ALU_OR;
          3'b111:  alu_op = ALU_AND;
          default: illegal_inst = 1'b1;
        endcase
      end
      7'b0001111: reg_we = 1'b0;                          // fence
      7'b1110011: begin                                   // SYSTEM
        if (inst == INSTR_MPAUSE || inst == INSTR_EBREAK || inst == INSTR_ECALL) halt_inst = 1'b1;
        else illegal_inst = 1'b1;
      end
      default: illegal_inst = 1'b1;
    endcase
  end

  always_comb begin
    unique case (opcode)
      7'b0110111: alu_result = imm_u;
      7'b1101111: alu_result = pc_plus4;
      7'b1100111: alu_result = pc_plus4;
      default:    alu_result = alu_y;
    endcase
  end

  alu32 u_alu (
      .a   (alu_a),
      .b   (alu_b),
      .op  (alu_op),
      .y   (alu_y),
      .zero(alu_zero)
  );

  // ----------------------------------------------------------------- LSU
  logic        mem_op;
  logic        lsu_req_valid;
  logic        lsu_busy, lsu_done;
  logic [31:0] lsu_rdata;

  assign mem_op        = is_load | is_store;
  assign lsu_req_valid = mem_op & ~lsu_busy;

  lsu u_lsu (
      .clk       (clk),
      .rst       (rst),
      .req_valid (lsu_req_valid),
      .req_write (is_store),
      .req_addr  (alu_y),
      .req_funct3(funct3),
      .req_wdata (rs2_val),
      .dmem_valid(io_dmem_valid),
      .dmem_we   (io_dmem_we),
      .dmem_addr (io_dmem_addr),
      .dmem_wmask(io_dmem_wmask),
      .dmem_wdata(io_dmem_wdata),
      .dmem_rdata(io_dmem_rdata),
      .dmem_ready(io_dmem_ready),
      .busy      (lsu_busy),
      .done      (lsu_done),
      .rdata     (lsu_rdata)
  );

  // 提交：非访存指令当拍完成；访存指令要等 LSU done
  logic        commit;
  logic [31:0] wb_data;
  assign commit  = mem_op ? lsu_done : 1'b1;
  assign wb_data = is_load ? lsu_rdata : alu_result;

  assign o_retire_valid = ~rst & ~o_halted & commit;
  assign o_retire_pc    = pc;
  assign o_retire_inst  = inst;
  assign o_retire_rd    = (reg_we && rd != 5'd0) ? rd : 5'd0;
  assign o_retire_wdata = (reg_we && rd != 5'd0) ? wb_data : 32'h0;

  always_ff @(posedge clk) begin
    if (rst) begin
      pc <= 32'h0;
      for (int unsigned i = 0; i < 32; i++) regs[i] <= 32'h0;
    end else if (!o_halted) begin
      if (commit) begin
        if (reg_we && rd != 5'd0) regs[rd] <= wb_data;
        pc <= next_pc;
      end
      regs[0] <= 32'h0;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) o_halted <= 1'b0;
    else if (halt_inst) o_halted <= 1'b1;
  end

`ifndef SYNTHESIS
  always_ff @(posedge clk) begin
    if (!rst && illegal_inst && !o_halted && !lsu_busy) begin
      $display("[cpu_core] 非法指令 0x%08x @ pc=0x%08x", inst, pc);
      $finish;
    end
  end
`endif

endmodule

`default_nettype wire

// CoralNPU 教学仓 L01 骨架：RV32I 单周期核
//
// ============================ 你来实现 ============================
// 这里已经给了你「外壳」：端口定义、PC 寄存器、寄存器堆、复位行为、
// 停机指令的识别。剩下的 6 个 TODO 就是本次作业：
//
//   TODO 1  立即数生成（I/S/B/U/J 五种格式）
//   TODO 2  译码：funct3/funct7 → ALU 操作
//   TODO 3  ALU：算术、逻辑、移位、比较
//   TODO 4  控制：reg_we / 访存使能 / 分支跳转 / next_pc
//   TODO 5  访存：lb/lh/lw/lbu/lhu 的符号扩展，sb/sh/sw 的写掩码
//   TODO 6  写回与 trace：o_retire_rd / o_retire_wdata
//
// 每完成一个 TODO，就跑一次 ./learn check L01，看失败位置一步步往后移动。
// 详细说明见 作业说明.pdf；数据通路图见 基础知识.pdf。
// ==================================================================

`default_nettype none

module cpu_core (
    input  logic        clk,
    input  logic        rst,
    // 指令端口：组合读（当拍给地址，当拍拿数据）
    output logic [31:0] io_imem_addr,
    input  logic [31:0] io_imem_rdata,
    // 数据端口：组合读；写发生在时钟上升沿（用 io_dmem_we + wmask 控制）
    output logic [31:0] io_dmem_addr,
    output logic [3:0]  io_dmem_wmask,
    output logic [31:0] io_dmem_wdata,
    output logic        io_dmem_we,
    input  logic [31:0] io_dmem_rdata,
    // 可观测性端口：每条退休指令输出一行 trace，检查器靠它和黄金模型对拍
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

  // ------------------------------------------------------------- 架构状态
  logic [31:0] pc;
  logic [31:0] regs[0:31];

  // --------------------------------------------------------------- 取指
  assign io_imem_addr = pc;
  logic [31:0] inst;
  assign inst = io_imem_rdata;

  // --------------------------------------------------------------- 译码字段
  // 指令格式参考 基础知识.pdf 第 2 章：R/I/S/B/U/J 六种格式的位域
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

  // TODO 1：立即数生成
  //   提示：I 型 = 符号扩展(inst[31:20])；S 型要拼 inst[31:25] 和 inst[11:7]；
  //        B 型最低位恒为 0；U 型是 inst[31:12] 左移 12；J 型的位序最容易写错。
  logic [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
  assign imm_i = {{20{inst[31]}}, inst[31:20]};  // TODO
  assign imm_s = {{20{inst[31]}}, inst[31:25], inst[11:7]};  // TODO
  assign imm_b = {{20{inst[31]}}, inst[7], inst[30:25], inst[11:8], 1'b0};  // TODO
  assign imm_u = {inst[31:12], 12'b0};  // TODO
  assign imm_j = {{12{inst[31]}}, inst[19:12], inst[20], inst[30:21], 1'b0};  // TODO

  logic [31:0] rs1_val, rs2_val;
  assign rs1_val = (rs1 == 5'd0) ? 32'h0 : regs[rs1];
  assign rs2_val = (rs2 == 5'd0) ? 32'h0 : regs[rs2];

  // ---------------------------------------------------------------- 执行
  logic [31:0] alu_y;
  logic [31:0] alu_result;   // 非载入指令的写回值
  logic [31:0] load_data;    // 载入指令的写回值
  logic [31:0] wb_data;      // 最终写回值（已接好，见下方 mux）
  logic [31:0] next_pc;
  logic        reg_we;
  logic        is_load, is_store;
  logic [4:0]  shamt;
  logic [31:0] next_pc_branch;
  logic [31:0] word;
  logic [3:0]  wmask;

  always_comb begin
    // TODO 2 + TODO 3 + TODO 4：把 opcode/funct3/funct7 翻译成数据通路动作
    //   建议顺序：先做最简单的 OP-IMM（addi），让第一条 trace 对上；
    //   然后 LUI/AUIPC；然后 OP；然后分支；然后 load/store；最后 jal/jalr。
    alu_y      = 32'd0;
    alu_result = imm_u;
    next_pc    = pc + 32'd4;
    reg_we     = 1'b1;
    is_load    = 1'b0;
    is_store   = 1'b0;

    shamt      = inst[24:20];
    next_pc_branch  = pc + $signed(imm_b);

    unique case(opcode)
      // 整数运算指令, RV32I有21条, 具体见 https://nju-projectn.github.io/dlco-lecture-note/exp/11.html
      
      // U-Type
      // lui
      7'b0110111: alu_result = imm_u;
      // auipc
      7'b0010111: alu_result = pc + imm_u;

      // I-Type
      7'b0010011: begin
        shamt = inst[24:20];
        unique case(funct3)
          // addi
          3'b000: alu_result = $signed(rs1_val) + $signed(imm_i);
          // slti: signed less than
          3'b010: alu_result = ($signed(rs1_val) < $signed(imm_i)) ? 32'b1 : 32'b0;
          // sltiu
          3'b011: alu_result = (rs1_val < imm_i) ? 32'b1 : 32'b0;
          // xori
          3'b100: alu_result = rs1_val ^ imm_i;
          // ori
          3'b110: alu_result = rs1_val | imm_i;
          // andi
          3'b111: alu_result = rs1_val & imm_i;
          // slli
          3'b001: alu_result = rs1_val << shamt;
          // srli/srai
          3'b101: alu_result = (funct7 == 7'b0) ? rs1_val >> shamt : (rs1_val >> shamt) | ({32{rs1_val[31]}} & ~(32'hFFFF_FFFF >> shamt));
        endcase
      end
      
      // R-Type
      7'b0110011: begin
        shamt = rs2_val[4:0];
        unique case(funct3)
          // add/sub
          3'b000: alu_result = (funct7 == 7'b0) ? rs1_val + rs2_val : rs1_val - rs2_val;
          // sll
          3'b001: alu_result = rs1_val << shamt;
          // slt
          3'b010: alu_result = ($signed(rs1_val) < $signed(rs2_val)) ? 32'b1 : 32'b0;
          // sltu
          3'b011: alu_result = (rs1_val < rs2_val) ? 32'b1 : 32'b0;
          // xor
          3'b100: alu_result = rs1_val ^ rs2_val;
          // srl/sra
          3'b101: alu_result = (funct7 == 7'b0) ? rs1_val >> shamt : (rs1_val >> shamt) | ({32{rs1_val[31]}} & ~(32'hFFFF_FFFF >> shamt));
          // or
          3'b110: alu_result = rs1_val | rs2_val;
          // and
          3'b111: alu_result = rs1_val & rs2_val;
        endcase
      end

      // 控制转移指令, 6条分支指令和2条无条件转移指令
      // 无条件转移
      7'b1101111: begin
        // jal
        reg_we = 1'b1;
        alu_result = pc + 32'd4;
        next_pc = pc + $signed(imm_j);
      end
      7'b1100111: begin
        // jalr
        reg_we = 1'b1;
        alu_result = pc + 32'd4;
        next_pc = (rs1_val + $signed(imm_i)) & 32'hFFFF_FFFE;
      end
      // 分支指令
      7'b1100011: begin
        reg_we = 1'b0;
        alu_result = 32'd0;
        unique case(funct3)
          // beq
          3'b000: next_pc = (rs1_val == rs2_val) ? next_pc_branch : pc + 32'd4;
          // bne
          3'b001: next_pc = (rs1_val != rs2_val) ? next_pc_branch : pc + 32'd4;
          // blt
          3'b100: next_pc = ($signed(rs1_val) < $signed(rs2_val)) ? next_pc_branch : pc + 32'd4;
          // bge
          3'b101: next_pc = ($signed(rs1_val) >= $signed(rs2_val)) ? next_pc_branch : pc + 32'd4;
          // bltu
          3'b110: next_pc = (rs1_val < rs2_val) ? next_pc_branch : pc + 32'd4;
          // bgeu
          3'b111: next_pc = (rs1_val >= rs2_val) ? next_pc_branch : pc + 32'd4;
        endcase
      end

      // 存储器访问指令
      // l指令
      7'b0000011: begin
        // lb, R[rd] <- SEXT(M_{1B}[R[rs1] + SEXT(imm_i)])
        reg_we    = 1'b1;
        is_load   = 1'b1;
        is_store  = 1'b0;
        alu_y     = rs1_val + imm_i;
      end
      // s指令
      7'b0100011: begin
        // sb, M_{1B}[R[rs1] + SEXT(imm_s)] <- R[rs2][7:0]
        reg_we    = 1'b0;
        is_load   = 1'b0;
        is_store  = 1'b1;
        alu_y     = rs1_val + imm_s;
      end
    endcase
  end

  // TODO 5：访存
  //   写掩码：sb 只写 1 个字节、sh 写 2 个、sw 写 4 个，注意 alu_y[1:0] 决定落在哪个字节
  //   载入：数据端口返回的是「对齐后的 32 位字」，lb 1(s5) 要先右移 8 位再取低字节，
  //         lb/lh 需要符号扩展，lbu/lhu 高位补 0
  assign io_dmem_addr  = alu_y;
  assign io_dmem_we    = is_store;
  assign io_dmem_wmask = wmask;   // TODO：按 funct3 生成
  assign io_dmem_wdata = rs2_val << (8 * alu_y[1:0]);   // TODO：按字节偏移对齐

  always_comb begin
    unique case(funct3)
      // sb
      3'b000: wmask = 4'b0001 << alu_y[1:0];
      // sh
      3'b001: wmask = 4'b0011 << alu_y[1:0];
      // sw
      3'b010: wmask = 4'b1111;
    endcase

    // TODO：按 funct3 做符号/零扩展

    // M取1B/2B/4B，由alu_y[1:0]决定移位
    word = io_dmem_rdata >> (8 * alu_y[1:0]);

    unique case(funct3)
      // lb
      3'b000: load_data = {{24{word[7]}}, word[7:0]};
      // lh
      3'b001: load_data = {{16{word[15]}}, word[15:0]};
      // lw
      3'b010: load_data = io_dmem_rdata;
      // lbu
      3'b100: load_data = {24'b0, word[7:0]};
      // lhu
      3'b101: load_data = {16'b0, word[15:0]};

      default: load_data = io_dmem_rdata;
    endcase
  end

  // 写回值选择已经接好：载入走内存数据，其余走 ALU 结果
  always_comb wb_data = is_load ? load_data : alu_result;

  // ---------------------------------------------------------------- 写回
  // TODO 6：让 rd/wdata 反映本周期真正写回的寄存器
  assign o_retire_valid = ~rst & ~o_halted;
  assign o_retire_pc    = pc;
  assign o_retire_inst  = inst;
  assign o_retire_rd    = reg_we ? rd : 5'd0;       // TODO
  assign o_retire_wdata = reg_we ? (rd ? wb_data : 32'h0) : 32'h0;      // TODO

  always_ff @(posedge clk) begin
    if (rst) begin
      pc <= 32'h0;
      for (int unsigned i = 0; i < 32; i++) regs[i] <= 32'h0;
    end else if (!o_halted) begin
      if (reg_we && rd != 5'd0) regs[rd] <= wb_data;
      regs[0] <= 32'h0;
      pc <= next_pc;
    end
  end

  // 停机识别已给好：mpause / ebreak / ecall（L01 不需要区分它们）
  logic halt_inst;
  assign halt_inst = (inst == INSTR_MPAUSE) || (inst == INSTR_EBREAK) || (inst == INSTR_ECALL);

  always_ff @(posedge clk) begin
    if (rst) o_halted <= 1'b0;
    else if (halt_inst) o_halted <= 1'b1;
  end

endmodule

`default_nettype wire

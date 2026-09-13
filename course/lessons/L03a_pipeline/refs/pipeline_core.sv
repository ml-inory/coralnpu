// CoralNPU 教学仓 L03a 参考实现：5 级流水线核心
//
//   IF  →  ID  →  EX  →  MEM  →  WB
//   取指   译码   执行   访存    写回
//
// 架构结果必须与 L01/L02 的单周期核完全一致（同样的 trace、同样的内存），
// 变的只是"同一时刻有多条指令在流水线里"，因此必须处理四类冒险：
//
//   1. 数据冒险：后面的指令要用前面还没写回的结果 → 旁路（forwarding）
//   2. load-use：载入的数据要等 MEM 级结束才有 → 插一个气泡（stall）
//   3. 控制冒险：分支/跳转要到 EX 才知道跳不跳 → 冲刷已取的两条指令（flush）
//   4. 结构冒险：LSU 可能忙好几拍 → 冻结流水线前几级（stall_all）
//
// 访存复用 L02 写的 lsu.sv：本文件只负责把请求送到 MEM 级。

`default_nettype none

module cpu_core (
    input  logic        clk,
    input  logic        rst,
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

  // ------------------------------------------------------------ 阶段寄存器
  logic [31:0] pc;
  logic        stopped;     // 停机指令已进入 EX：不再取新指令
  logic [31:0] regs[0:31];

  // IF/ID
  logic [31:0] id_pc, id_inst;
  logic        id_valid;

  // ID/EX
  logic [31:0] ex_pc, ex_inst, ex_rs1_val, ex_rs2_val;
  logic        ex_valid;

  // EX/MEM（控制位在 EX 译码后随指令一起流下去）
  logic [31:0] mem_pc, mem_inst, mem_alu_y, mem_rs2_val;
  logic        mem_reg_we, mem_is_load, mem_is_store, mem_valid;

  // MEM/WB
  logic [31:0] wb_pc, wb_inst, wb_data;
  logic        wb_reg_we, wb_valid;

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

  function automatic logic is_halt_of(input logic [31:0] i);
    is_halt_of = (i == INSTR_MPAUSE) || (i == INSTR_EBREAK) || (i == INSTR_ECALL);
  endfunction

  function automatic logic is_reg_write_op(input logic [31:0] i);
    logic [6:0] op;
    op = op_of(i);
    is_reg_write_op = (op == 7'b0110111) || (op == 7'b0010111) || (op == 7'b1101111) ||
                      (op == 7'b1100111) || (op == 7'b0000011) || (op == 7'b0010011) ||
                      (op == 7'b0110011);
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
  // 注意这里还要处理 WB→ID 的"写穿"：寄存器堆在本拍写、ID 在本拍读，
  // 如果只读 regs[]，读到的是写之前的值（同一个时钟沿同时发生）。
  // 教科书做法是"前半拍写、后半拍读"，RTL 里用一次旁路等价实现。
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
  logic [3:0]  ex_alu_op;
  logic [31:0] ex_imm_sel, ex_target, ex_pc_plus4, ex_wb_value;
  logic [31:0] fwd_a, fwd_b, alu_a, alu_b, alu_y;
  logic        alu_zero;

  assign ex_op        = op_of(ex_inst);
  assign ex_f3        = f3_of(ex_inst);
  assign ex_pc_plus4  = ex_pc + 32'd4;

  // 旁路：EX 的操作数可能来自 MEM 级（EX/MEM）或 WB 级（MEM/WB）
  always_comb begin
    fwd_a = ex_rs1_val;
    fwd_b = ex_rs2_val;
    // MEM 级更"新"，优先；但 MEM 级如果是 load，它的数据还没出来（靠 load-use 停顿解决）
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

    unique case (ex_op)
      7'b0110111: begin ex_reg_we = 1'b1; ex_imm_sel = imm_u_of(ex_inst); end   // lui
      7'b0010111: begin ex_reg_we = 1'b1; ex_imm_sel = imm_u_of(ex_inst); end   // auipc
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
        if (f7_of(ex_inst) == 7'b0000001) ex_illegal = 1'b1;   // M 扩展留给 L03b
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
      7'b0001111: ;                                                  // fence
      7'b1110011: if (is_halt_of(ex_inst)) ex_is_halt = 1'b1; else ex_illegal = 1'b1;
      default:    ex_illegal = 1'b1;
    endcase
  end

  // ALU 输入：a 端在 auipc 时换成 pc；b 端在 OP 类指令时用寄存器
  assign alu_a = (ex_op == 7'b0010111) ? ex_pc : fwd_a;
  assign alu_b = (ex_op == 7'b0110011) ? fwd_b : ex_imm_sel;

  alu32 u_alu (
      .a   (alu_a),
      .b   (alu_b),
      .op  (ex_alu_op),
      .y   (alu_y),
      .zero(alu_zero)
  );

  assign ex_target = ex_is_halt ? ex_pc :
                     ex_is_jalr ? ((fwd_a + imm_i_of(ex_inst)) & ~32'd1) :
                     ex_is_jal  ? (ex_pc + imm_j_of(ex_inst)) :
                                  (ex_pc + imm_b_of(ex_inst));
  assign ex_redirect = ex_valid & (ex_br_taken | ex_is_jal | ex_is_jalr | ex_is_halt);

  assign ex_wb_value = (ex_is_jal | ex_is_jalr) ? ex_pc_plus4 :
                       (ex_op == 7'b0110111)    ? imm_u_of(ex_inst) : alu_y;

  // ------------------------------------------------------------- MEM 级：LSU
  logic        lsu_req_valid, lsu_busy, lsu_done;
  logic [31:0] lsu_rdata;
  logic        mem_op, lsu_wait;

  assign mem_op        = mem_valid & (mem_is_load | mem_is_store);
  assign lsu_req_valid = mem_op & ~lsu_busy;
  assign lsu_wait      = mem_op & ~lsu_done;

  lsu u_lsu (
      .clk       (clk),
      .rst       (rst),
      .req_valid (lsu_req_valid),
      .req_write (mem_is_store),
      .req_addr  (mem_alu_y),
      .req_funct3(f3_of(mem_inst)),
      .req_wdata (mem_rs2_val),
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

  logic [31:0] mem_wb_value;
  assign mem_wb_value = mem_is_load ? lsu_rdata : mem_alu_y;

  // ------------------------------------------------------- 冒险检测（ID 级）
  logic load_use_stall;
  assign load_use_stall = ex_valid & ex_is_load & id_valid & (rd_of(ex_inst) != 5'd0) &
                          ((uses_rs1_of(id_inst) & (rs1_of(id_inst) == rd_of(ex_inst))) |
                           (uses_rs2_of(id_inst) & (rs2_of(id_inst) == rd_of(ex_inst))));

  // ------------------------------------------------------------ WB 级：提交
  // 两种停顿：
  //   stall_all    —— 等 LSU（结构冒险）：整条流水线冻结，含 MEM/WB。
  //                   连 WB 一起冻是必须的：停在 EX 的消费者可能还要用 WB 的结果做旁路。
  //   stall_bubble —— load-use（数据冒险）：只冻结 PC/IF 与 ID，并给 ID/EX 插一个气泡，
  //                   否则 EX 里的 load 也走不掉，会死锁。
  logic stall_all, stall_bubble;
  assign stall_all    = lsu_wait;
  assign stall_bubble = load_use_stall;

  assign o_retire_valid = wb_valid & ~stall_all & ~o_halted;
  assign o_retire_pc    = wb_pc;
  assign o_retire_inst  = wb_inst;
  assign o_retire_rd    = (wb_reg_we && rd_of(wb_inst) != 5'd0) ? rd_of(wb_inst) : 5'd0;
  assign o_retire_wdata = (wb_reg_we && rd_of(wb_inst) != 5'd0) ? wb_data : 32'h0;

  logic wb_is_halt;
  assign wb_is_halt = wb_valid & is_halt_of(wb_inst);

  // 访存指令在 MEM 级需要的是"地址"（rs1+imm），其它指令需要的是"结果"
  logic ex_imm_is_addr;
  assign ex_imm_is_addr = ex_is_load | ex_is_store;

`ifdef L03A_DEBUG
  // 调试用：把每拍 EX 级的操作数、旁路结果和停顿原因打出来
  always_ff @(posedge clk) begin
    if (!rst && ex_valid) begin
      $display("[EX] pc=%05x inst=%08x fwd_a=%08x fwd_b=%08x | MEM pc=%05x v=%b ld=%b st=%b wait=%b | WB v=%b rd=x%0d data=%08x | stall all=%b bubble=%b",
               ex_pc, ex_inst, fwd_a, fwd_b, mem_pc, mem_valid, mem_is_load, mem_is_store, lsu_wait,
               wb_valid, rd_of(wb_inst), wb_data, stall_all, stall_bubble);
    end
    if (!rst && (stall_all || stall_bubble)) begin
      $display("   [STALL] all=%b bubble=%b | ID pc=%05x v=%b inst=%08x | LSU busy=%b done=%b req=%b",
               stall_all, stall_bubble, id_pc, id_valid, id_inst, lsu_busy, lsu_done, lsu_req_valid);
    end
  end
`endif

  // ---------------------------------------------------------------- 时序更新
  always_ff @(posedge clk) begin
    if (rst) begin
      pc        <= 32'h0;
      stopped   <= 1'b0;
      o_halted  <= 1'b0;
      id_valid  <= 1'b0;
      ex_valid  <= 1'b0;
      mem_valid <= 1'b0;
      wb_valid  <= 1'b0;
      for (int unsigned i = 0; i < 32; i++) regs[i] <= 32'h0;
    end else if (stall_all) begin
      // 停顿：整条流水线冻结（含 MEM/WB）。
      // 为什么连 MEM/WB 也要冻？因为停在 EX 的指令可能还要用 WB 级的结果做旁路，
      // 如果让 WB 继续前进，旁路来源就消失了，消费者只能读到寄存器堆里的旧值。
      // 寄存器写回与 retire 在停顿期间被抑制/保持不变，不会重复提交。
    end else begin
      // ---------------- PC
      if (ex_redirect)  pc <= ex_target;
      else if (stopped) pc <= pc;
      else if (!stall_bubble) pc <= pc + 32'd4;

      // ---------------- IF/ID
      if (ex_redirect || stopped) begin
        id_valid <= 1'b0;                       // 冲刷：分支/跳转/停机之后取的都是错路
      end else if (stall_bubble) begin
        id_valid <= id_valid;                   // 冻结（消费者留在 ID 等一拍）
      end else begin
        id_pc    <= pc;
        id_inst  <= io_imem_rdata;
        id_valid <= 1'b1;
      end

      // ---------------- ID/EX
      if (ex_redirect || stall_bubble) begin
        ex_valid <= 1'b0;                       // 冲刷 / 插气泡
      end else begin
        ex_pc      <= id_pc;
        ex_inst    <= id_inst;
        ex_rs1_val <= id_rs1_val;
        ex_rs2_val <= id_rs2_val;
        ex_valid   <= id_valid;
      end

      // ---------------- EX/MEM
      mem_pc       <= ex_pc;
      mem_inst     <= ex_inst;
      mem_alu_y    <= ex_imm_is_addr ? alu_y : ex_wb_value;
      mem_rs2_val  <= fwd_b;
      // 注意：控制位必须与 valid 相与。否则"气泡"（被冲刷的指令）会带着
      // 上一条指令残留的 ex_reg_we 走进 MEM/WB，照样写寄存器堆，
      // 表现为"某个无关的寄存器被莫名改成别的值"。
      mem_reg_we   <= ex_reg_we   & ex_valid;
      mem_is_load  <= ex_is_load  & ex_valid;
      mem_is_store <= ex_is_store & ex_valid;
      mem_valid    <= ex_valid;

      // ---------------- MEM/WB
      wb_pc     <= mem_pc;
      wb_inst   <= mem_inst;
      wb_data   <= mem_wb_value;
      wb_reg_we <= mem_reg_we;
      wb_valid  <= mem_valid;

      // ---------------- 停机与写回
      if (wb_is_halt)            o_halted <= 1'b1;
      if (ex_valid & ex_is_halt) stopped  <= 1'b1;
      if (wb_valid && wb_reg_we && rd_of(wb_inst) != 5'd0) regs[rd_of(wb_inst)] <= wb_data;
      regs[0] <= 32'h0;
    end
  end

endmodule

`default_nettype wire

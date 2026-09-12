// CoralNPU 教学仓 L01 参考实现（复用版）：实例化 L00 的 alu32
//
// 和 refs/cpu_core.sv 功能完全一样（都能跑通 5/5 个用例），区别在于：
// 运算不再写在 cpu_core 内部，而是实例化 L00 作业里写的 alu32。
//
// 复用要点（也是硬件设计的通用技巧）：
//   1. 实例化语法：模块名 实例名 ( .端口(信号), ... );
//   2. **接口适配**：cpu_core 手里是 opcode/funct3/funct7，alu32 要的是 0..9 的 op，
//      中间需要一个「适配器」把指令字段翻译成 ALU 操作码；
//   3. **资源复用**：同一个 ALU 既算算术结果，也算访存地址（rs1+imm），
//      靠的是在输入端做多路选择，而不是复制两份运算逻辑；
//   4. 有些加法不值得复用：pc+4（自增）和分支目标 pc+imm 是结构性的加法，
//      用简单的 `+` 表达式即可，综合出来就是小的加法器。
//
// 运行检查：./learn check L01 --from refs/cpu_core_reuse.sv

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
    input  logic [31:0] io_dmem_rdata,
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

  // alu32 的操作码（与 L00 作业里的定义一致）
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

  // ------------------------------------------------------------- 架构状态
  logic [31:0] pc;
  logic [31:0] regs[0:31];

  // --------------------------------------------------------------- 取指
  assign io_imem_addr = pc;
  logic [31:0] inst;
  assign inst = io_imem_rdata;

  // --------------------------------------------------------------- 译码字段
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

  // ------------------------------------------- 实例化 L00 的 ALU（本次重点）
  logic [31:0] alu_a, alu_b, alu_y;
  logic [3:0]  alu_op;
  logic        alu_zero;

  alu32 u_alu (
      .a   (alu_a),
      .b   (alu_b),
      .op  (alu_op),
      .y   (alu_y),
      .zero(alu_zero)   // 单周期核用不到零标志（分支自己比较），留空也行
  );

  // ---------------------------------------------------------------- 控制
  logic [31:0] alu_result;
  logic [31:0] pc_plus4;
  logic [31:0] next_pc;
  logic        reg_we;
  logic        is_load, is_store;
  logic        halt_inst, illegal_inst;
  logic        br_taken;
  logic [3:0]  wmask;
  logic [31:0] store_data;

  assign pc_plus4 = pc + 32'd4;

  // 适配器：把 opcode/funct3/funct7 翻译成 alu32 的 0..9 操作码，
  // 同时选择送进 ALU 的两个操作数。
  always_comb begin
    // 默认：假设是访存地址计算 rs1 + imm_i（load 与 store 共用同一个加法器）
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

    case (opcode)
      // LUI：结果就是立即数本身，不占用 ALU
      7'b0110111: begin
        reg_we = 1'b1;
      end
      // AUIPC：pc + 高位立即数
      7'b0010111: begin
        alu_a  = pc;
        alu_b  = imm_u;
        alu_op = ALU_ADD;
        reg_we = 1'b1;
      end
      // JAL：下一条 PC 由 pc + imm_j 得到（结构性加法，不走 ALU）
      7'b1101111: begin
        next_pc = pc + imm_j;
        reg_we  = 1'b1;
      end
      // JALR：跳转目标 = ALU 算出的 rs1 + imm_i，最低位清零
      7'b1100111: begin
        alu_op  = ALU_ADD;
        next_pc = alu_y & ~32'd1;
        reg_we  = 1'b1;
      end
      // 条件分支：比较在分支逻辑里直接做（ALU 没有六种比较的组合结果）
      7'b1100011: begin
        case (funct3)
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
      // 载入：地址 = rs1 + imm_i（默认值已经算好），写回用内存数据
      7'b0000011: begin
        is_load = 1'b1;
        reg_we  = 1'b1;
      end
      // 存储：地址 = rs1 + imm_s
      7'b0100011: begin
        alu_b    = imm_s;
        is_store = 1'b1;
      end
      // OP-IMM：立即数运算，操作数 b 就是 imm_i
      7'b0010011: begin
        reg_we = 1'b1;
        case (funct3)
          3'b000:  alu_op = ALU_ADD;
          3'b010:  alu_op = ALU_SLT;
          3'b011:  alu_op = ALU_SLTU;
          3'b100:  alu_op = ALU_XOR;
          3'b110:  alu_op = ALU_OR;
          3'b111:  alu_op = ALU_AND;
          3'b001:  alu_op = ALU_SLL;   // 移位量由 alu32 自己取 b[4:0]
          3'b101:  alu_op = inst[30] ? ALU_SRA : ALU_SRL;
          default: illegal_inst = 1'b1;
        endcase
      end
      // OP：寄存器运算，操作数 b 是 rs2
      7'b0110011: begin
        reg_we = 1'b1;
        alu_b  = rs2_val;
        if (funct7 == 7'b0000001) illegal_inst = 1'b1;  // M 扩展属 L03
        case (funct3)
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
      7'b0001111: reg_we = 1'b0;   // FENCE / FENCE.I：空操作
      7'b1110011: begin
        if (inst == INSTR_MPAUSE || inst == INSTR_EBREAK || inst == INSTR_ECALL) halt_inst = 1'b1;
        else illegal_inst = 1'b1;
      end
      default: illegal_inst = 1'b1;
    endcase
  end

  // 写回值来源：LUI 直通立即数、JAL/JALR 写 pc+4、其余用 ALU 结果
  always_comb begin
    case (opcode)
      7'b0110111: alu_result = imm_u;
      7'b1101111: alu_result = pc_plus4;
      7'b1100111: alu_result = pc_plus4;
      default:    alu_result = alu_y;
    endcase
  end

  // 载入数据的字节选择与符号/零扩展
  logic [31:0] mem_word;
  logic [31:0] load_data;
  always_comb begin
    mem_word = io_dmem_rdata >> (8 * alu_y[1:0]);
    case (funct3)
      3'b000:  load_data = {{24{mem_word[7]}}, mem_word[7:0]};
      3'b001:  load_data = {{16{mem_word[15]}}, mem_word[15:0]};
      3'b100:  load_data = {24'b0, mem_word[7:0]};
      3'b101:  load_data = {16'b0, mem_word[15:0]};
      default: load_data = io_dmem_rdata;
    endcase
  end

  logic [31:0] wb_data;
  always_comb wb_data = is_load ? load_data : alu_result;

  always_comb begin
    case (funct3)
      3'b000:  wmask = 4'b0001 << alu_y[1:0];
      3'b001:  wmask = 4'b0011 << alu_y[1:0];
      default: wmask = 4'b1111;
    endcase
    store_data = rs2_val << (8 * alu_y[1:0]);
  end

  assign io_dmem_addr  = alu_y;     // ALU 的加法结果同时用作访存地址
  assign io_dmem_we    = is_store & ~o_halted & ~rst;
  assign io_dmem_wmask = wmask;
  assign io_dmem_wdata = store_data;

  // ---------------------------------------------------------------- 写回
  assign o_retire_valid = ~rst & ~o_halted;
  assign o_retire_pc    = pc;
  assign o_retire_inst  = inst;
  assign o_retire_rd    = (reg_we && rd != 5'd0) ? rd : 5'd0;
  assign o_retire_wdata = (reg_we && rd != 5'd0) ? wb_data : 32'h0;

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

  always_ff @(posedge clk) begin
    if (rst) o_halted <= 1'b0;
    else if (halt_inst) o_halted <= 1'b1;
  end

`ifndef SYNTHESIS
  always_ff @(posedge clk) begin
    if (!rst && illegal_inst && !o_halted) begin
      $display("[cpu_core] 非法指令 0x%08x @ pc=0x%08x", inst, pc);
      $finish;
    end
  end
`endif

endmodule

`default_nettype wire

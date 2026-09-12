// CoralNPU 教学仓 L01 参考实现：RV32I 单周期核
//
// 结构（与 L01 基础知识.pdf 的数据通路图一一对应）：
//   PC → 取指（组合读 ITCM）→ 译码 → 立即数生成 → 寄存器读 → ALU → 访存 → 写回
// 所有事情在一个周期内完成，所以叫「单周期」。
//
// 与上游 CoralNPU 的关系：
//   * 上游是 4 级流水、4 路派发、乱序退休（hdl/chisel/src/coralnpu/scalar/），
//     本文件用最小可用版本实现同样的指令语义；L03 再逐步加上流水与冒险处理。
//   * 停机指令 mpause 的编码与上游一致：0x08000073
//     （见 hdl/chisel/src/coralnpu/scalar/Decode.scala:1188）。
//
// 设计约定（重要）：
//   * 每个 always_comb 只驱动一组信号，避免多驱动（多个进程写同一个变量）。
//   * 所有控制信号都有默认值，避免锁存器。

`default_nettype none

module cpu_core (
    input  logic        clk,
    input  logic        rst,
    // 指令端口：组合读，地址当拍给、数据当拍回
    output logic [31:0] io_imem_addr,
    input  logic [31:0] io_imem_rdata,
    // 数据端口：组合读，写发生在时钟上升沿
    output logic [31:0] io_dmem_addr,
    output logic [3:0]  io_dmem_wmask,
    output logic [31:0] io_dmem_wdata,
    output logic        io_dmem_we,
    input  logic [31:0] io_dmem_rdata,
    // 可观测性端口：每条退休指令给出一行 trace
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

  // 立即数生成：五种格式各不相同，这是初学者最容易错的地方
  logic [31:0] imm_i, imm_s, imm_b, imm_u, imm_j;
  assign imm_i = {{20{inst[31]}}, inst[31:20]};
  assign imm_s = {{20{inst[31]}}, inst[31:25], inst[11:7]};
  assign imm_b = {{19{inst[31]}}, inst[31], inst[7], inst[30:25], inst[11:8], 1'b0};
  assign imm_u = {inst[31:12], 12'b0};
  assign imm_j = {{11{inst[31]}}, inst[31], inst[19:12], inst[20], inst[30:21], 1'b0};

  logic [31:0] rs1_val, rs2_val;
  assign rs1_val = (rs1 == 5'd0) ? 32'h0 : regs[rs1];
  assign rs2_val = (rs2 == 5'd0) ? 32'h0 : regs[rs2];

  // 算术右移辅助函数。
  // 不要写 `$signed(a) >>> b`：在 Verilog 里整个表达式一旦落在无符号上下文，
  // `>>>` 会退化成逻辑移位（初学者最常见的坑之一）。这里显式构造符号填充掩码。
  function automatic logic [31:0] asr(input logic [31:0] value, input logic [4:0] shamt);
    asr = (value >> shamt) | ({32{value[31]}} & ~(32'hFFFF_FFFF >> shamt));
  endfunction

  // ---------------------------------------------------------------- 执行
  logic [31:0] alu_y;        // ALU 结果（也是访存地址）
  logic [31:0] alu_result;   // 非载入指令的写回值
  logic [31:0] load_data;    // 载入指令的写回值
  logic [31:0] wb_data;      // 最终写回值
  logic [31:0] next_pc;
  logic        reg_we;
  logic        is_load, is_store;
  logic        halt_inst, illegal_inst;
  logic [3:0]  wmask;
  logic [31:0] store_data;
  logic        br_taken;

  // 主译码：把 opcode/funct3/funct7 翻译成数据通路动作
  always_comb begin
    // 默认值，避免锁存器
    alu_y        = 32'h0;
    alu_result   = 32'h0;
    next_pc      = pc + 32'd4;
    reg_we       = 1'b0;
    is_load      = 1'b0;
    is_store     = 1'b0;
    halt_inst    = 1'b0;
    illegal_inst = 1'b0;
    br_taken     = 1'b0;

    case (opcode)
      // LUI：把 20 位立即数放到高 20 位
      7'b0110111: begin
        alu_result = imm_u;
        reg_we     = 1'b1;
      end
      // AUIPC：PC + 高位立即数
      7'b0010111: begin
        alu_y      = pc + imm_u;
        alu_result = pc + imm_u;
        reg_we     = 1'b1;
      end
      // JAL：跳转并把返回地址写入 rd
      7'b1101111: begin
        alu_result = pc + 32'd4;
        next_pc    = pc + imm_j;
        reg_we     = 1'b1;
      end
      // JALR：寄存器间接跳转，最低位清零
      7'b1100111: begin
        alu_y      = (rs1_val + imm_i) & ~32'd1;
        alu_result = pc + 32'd4;
        next_pc    = (rs1_val + imm_i) & ~32'd1;
        reg_we     = 1'b1;
      end
      // 条件分支：6 种比较
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
        next_pc = br_taken ? (pc + imm_b) : (pc + 32'd4);
      end
      // 载入：地址 = rs1 + imm_i
      7'b0000011: begin
        alu_y   = rs1_val + imm_i;
        is_load = 1'b1;
        reg_we  = 1'b1;
      end
      // 存储：地址 = rs1 + imm_s，数据来自 rs2
      7'b0100011: begin
        alu_y    = rs1_val + imm_s;
        is_store = 1'b1;
      end
      // OP-IMM：立即数运算
      7'b0010011: begin
        reg_we = 1'b1;
        case (funct3)
          3'b000:  alu_y = rs1_val + imm_i;
          3'b010:  alu_y = ($signed(rs1_val) < $signed(imm_i)) ? 32'd1 : 32'd0;
          3'b011:  alu_y = (rs1_val < imm_i) ? 32'd1 : 32'd0;
          3'b100:  alu_y = rs1_val ^ imm_i;
          3'b110:  alu_y = rs1_val | imm_i;
          3'b111:  alu_y = rs1_val & imm_i;
          3'b001:  alu_y = rs1_val << inst[24:20];
          3'b101:  alu_y = inst[30] ? asr(rs1_val, inst[24:20]) : (rs1_val >> inst[24:20]);
          default: illegal_inst = 1'b1;
        endcase
        alu_result = alu_y;
      end
      // OP：寄存器运算
      7'b0110011: begin
        reg_we = 1'b1;
        if (funct7 == 7'b0000001) illegal_inst = 1'b1;  // M 扩展留给 L03
        case (funct3)
          3'b000:  alu_y = inst[30] ? (rs1_val - rs2_val) : (rs1_val + rs2_val);
          3'b001:  alu_y = rs1_val << rs2_val[4:0];
          3'b010:  alu_y = ($signed(rs1_val) < $signed(rs2_val)) ? 32'd1 : 32'd0;
          3'b011:  alu_y = (rs1_val < rs2_val) ? 32'd1 : 32'd0;
          3'b100:  alu_y = rs1_val ^ rs2_val;
          3'b101:  alu_y = inst[30] ? asr(rs1_val, rs2_val[4:0]) : (rs1_val >> rs2_val[4:0]);
          3'b110:  alu_y = rs1_val | rs2_val;
          3'b111:  alu_y = rs1_val & rs2_val;
          default: illegal_inst = 1'b1;
        endcase
        alu_result = alu_y;
      end
      // FENCE / FENCE.I：单周期核里当空操作
      7'b0001111: begin
        reg_we = 1'b0;
      end
      // SYSTEM：mpause / ebreak / ecall 停机，其余（CSR）留给 L03
      7'b1110011: begin
        if (inst == INSTR_MPAUSE || inst == INSTR_EBREAK || inst == INSTR_ECALL) halt_inst = 1'b1;
        else illegal_inst = 1'b1;
      end
      default: illegal_inst = 1'b1;
    endcase
  end

  // 载入数据的字节选择与符号/零扩展。
  // 数据端口一次返回的是「对齐后的 32 位字」，所以 lb 1(s5) 要先右移 8 位把
  // 目标字节挪到低 8 位，再做符号扩展。
  logic [31:0] mem_word;
  always_comb begin
    mem_word = io_dmem_rdata >> (8 * alu_y[1:0]);
    case (funct3)
      3'b000:  load_data = {{24{mem_word[7]}}, mem_word[7:0]};    // LB
      3'b001:  load_data = {{16{mem_word[15]}}, mem_word[15:0]};  // LH
      3'b100:  load_data = {24'b0, mem_word[7:0]};                // LBU
      3'b101:  load_data = {16'b0, mem_word[15:0]};               // LHU
      default: load_data = io_dmem_rdata;                         // LW
    endcase
  end

  // 写回值：载入走内存数据，其余走 ALU 结果
  always_comb wb_data = is_load ? load_data : alu_result;

  // 存储的字节掩码与数据对齐
  always_comb begin
    case (funct3)
      3'b000:  wmask = 4'b0001 << alu_y[1:0];  // SB
      3'b001:  wmask = 4'b0011 << alu_y[1:0];  // SH
      default: wmask = 4'b1111;                // SW
    endcase
    store_data = rs2_val << (8 * alu_y[1:0]);
  end

  assign io_dmem_addr  = alu_y;
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
  // 非法指令直接报错，方便定位译码漏洞
  always_ff @(posedge clk) begin
    if (!rst && illegal_inst && !o_halted) begin
      $display("[cpu_core] 非法指令 0x%08x @ pc=0x%08x", inst, pc);
      $finish;
    end
  end
`endif

endmodule

`default_nettype wire

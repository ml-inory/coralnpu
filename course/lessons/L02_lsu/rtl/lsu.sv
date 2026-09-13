// CoralNPU 教学仓 L02 骨架：Load/Store Unit
//
// ============================ 你来实现 ============================
// 核心（tests/core_wrapper.sv）已经接好，它只负责：
//   * 在 LSU 空闲时发出请求：req_valid=1、req_addr=rs1+imm、req_funct3、req_wdata；
//   * 在 LSU 报 busy 时冻结 PC 与寄存器写回；
//   * 在 LSU 报 done 的那一拍提交这条指令（写回 / 打印 trace / 前进 PC）。
//
// 你要做的是把一条访存指令变成 1~2 次对齐的存储器事务：
//
//   TODO 1  IDLE：收到 req_valid 时锁存请求，并算出第一笔事务的
//           addr/mask/data（对齐地址、字节掩码、数据左移）
//   TODO 2  REQ ：驱动 dmem_valid/addr/mask/data，等 dmem_ready
//   TODO 3  载入：把读回的字按地址低位重排，再按 funct3 做符号/零扩展
//   TODO 4  非对齐：当 off + size > 4 时，拆出第二笔事务（地址 +4），
//           用状态把两笔结果拼起来（这是 L02 的重点）
//
// 每完成一步就跑：./learn check L02
//   * 先让 01~05（L01 的对齐程序）通过；
//   * 再让 06_unaligned 通过。
// 详细说明见 作业说明.pdf；掩码与字节道的关系见 基础知识.pdf。
// ==================================================================

`default_nettype none

module lsu (
    input  logic        clk,
    input  logic        rst,
    // ------------------------------------------------ 来自核心的访存请求
    input  logic        req_valid,
    input  logic        req_write,
    input  logic [31:0] req_addr,
    input  logic [2:0]  req_funct3,
    input  logic [31:0] req_wdata,
    // ------------------------------------------------ 数据存储器（握手）
    output logic        dmem_valid,
    output logic        dmem_we,
    output logic [31:0] dmem_addr,
    output logic [3:0]  dmem_wmask,
    output logic [31:0] dmem_wdata,
    input  logic [31:0] dmem_rdata,
    input  logic        dmem_ready,
    // ------------------------------------------------ 回给核心
    output logic        busy,
    output logic        done,
    output logic [31:0] rdata
);

  typedef enum logic [1:0] {IDLE, REQ, FINISH} state_t;
  state_t state;

  // 请求锁存（TODO 1 里填）
  logic        is_write;
  logic [2:0]  funct3_r;
  logic [2:0]  size;        // 1/2/4 字节
  logic [1:0]  off;         // 地址在字内的偏移
  logic [31:0] wdata_r;
  logic        step;        // 0 = 第一笔，1 = 第二笔
  logic        need_two;    // 是否需要第二笔（跨字）

  logic [31:0] addr0, addr1;
  logic [3:0]  mask0, mask1;
  logic [31:0] data0, data1;

  logic [31:0] word0, word1;

  // 宽度与基掩码（已给，直接可用）
  function automatic logic [2:0] size_of(input logic [2:0] f3);
    case (f3)
      3'b000, 3'b100: size_of = 3'd1;
      3'b001, 3'b101: size_of = 3'd2;
      default:        size_of = 3'd4;
    endcase
  endfunction

  function automatic logic [3:0] base_mask(input logic [2:0] f3);
    case (f3)
      3'b000, 3'b100: base_mask = 4'b0001;
      3'b001, 3'b101: base_mask = 4'b0011;
      default:        base_mask = 4'b1111;
    endcase
  endfunction

  always_ff @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      step  <= 1'b0;
      word0 <= 32'h0;
      word1 <= 32'h0;
    end else begin
      // TODO 1 / TODO 2 / TODO 4：状态机
      case (state)
        IDLE: begin
          if (req_valid) begin
            state <= REQ;
            // 锁存
            is_write  <= req_write;
            funct3_r  <= req_funct3;
            size      <= size_of(req_funct3);
            off       <= req_addr[1:0];
            wdata_r   <= req_wdata;

            // 第一笔：字0
            addr0     <= {req_addr[31:2], 2'b00};
            mask0     <= base_mask(req_funct3) << req_addr[1:0];
            data0     <= req_wdata << (8 * req_addr[1:0]);

            // 第二笔：字1（只在 off + size > 4 时需要）
            addr1     <= {req_addr[31:2], 2'b00} + 32'd4;
            mask1     <= base_mask(req_funct3) >> (4 - req_addr[1:0]);
            data1     <= req_wdata >> (8 * (4 - req_addr[1:0]));

            step      <= 1'b0;
            need_two  <= (req_addr[1:0] + size_of(req_funct3)) > 4 ? 1'b1 : 1'b0;
          end
        end

        REQ: begin
          if (dmem_ready) begin
            // 读操作
            if (!is_write) begin
              if (!step)  word0 <= dmem_rdata;
              else        word1 <= dmem_rdata;
            end

            if (need_two && !step)  step <= 1'b1;
            else                    state <= FINISH;
          end
        end

        FINISH: state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end

  always_comb begin
    // TODO 2：把请求送出去，并在 dmem_ready 时结束这一笔
    dmem_valid = (state == REQ);
    dmem_we    = is_write;
    dmem_addr  = step ? addr1 : addr0;
    dmem_wmask = step ? mask1 : mask0;
    dmem_wdata = step ? data1 : data0;
    busy       = (state != IDLE);
    done       = (state == FINISH);      // ← 占位：假装立即完成，所以现在不会真的访存
  end

  logic [63:0] combined;
  logic [63:0] shifted;
  always_comb begin
    // TODO 3：字节重排 + 符号/零扩展
    combined = {word1, word0};
    shifted  = combined >> (8 * off);
    unique case (funct3_r)
      // lb
      3'b000: rdata = {{24{shifted[7]}}, shifted[7:0]};
      // lh
      3'b001: rdata = {{16{shifted[15]}}, shifted[15:0]};
      // lw
      3'b010: rdata = shifted;
      // lbu
      3'b100: rdata = {24'b0, shifted[7:0]};
      // lhu
      3'b101: rdata = {16'b0, shifted[15:0]};

      default: rdata = 32'h0;
    endcase
  end

endmodule

`default_nettype wire

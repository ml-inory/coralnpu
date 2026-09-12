// CoralNPU 教学仓 L02 参考实现：Load/Store Unit
//
// 职责：把一条访存指令翻译成 1~2 次"对齐的"存储器事务。
//   * 对齐访问（地址满足宽度要求）→ 1 次事务；
//   * 非对齐访问（跨字）→ 2 次事务，由状态机分两步完成；
//   * 存储器的响应可能有延迟（ready=0 表示还忙）→ 状态机负责等待；
//   * 载入完成时把字节重排 + 符号/零扩展后的结果交给核心。
//
// 与上游的关系：上游 CoralNPU 的 LSU 用"槽表"（slot table）把一次操作拆成
// 若干字节条目，逐条完成并翻转 active 位（见 doc/microarch/lsu.md）。
// 本课用状态机 + 两次事务实现同样的对外语义，是它的最小版本。

`default_nettype none

module lsu (
    input  logic        clk,
    input  logic        rst,
    // ------------------------------------------------ 来自核心的访存请求
    input  logic        req_valid,    // 有一条访存指令要执行（核心在 LSU 空闲时给一个脉冲）
    input  logic        req_write,    // 1 = store，0 = load
    input  logic [31:0] req_addr,     // 字节地址 = rs1 + imm
    input  logic [2:0]  req_funct3,   // 决定宽度与符号扩展
    input  logic [31:0] req_wdata,    // store 的原始数据（未对齐）
    // ------------------------------------------------ 数据存储器（握手）
    output logic        dmem_valid,
    output logic        dmem_we,
    output logic [31:0] dmem_addr,
    output logic [3:0]  dmem_wmask,
    output logic [31:0] dmem_wdata,
    input  logic [31:0] dmem_rdata,
    input  logic        dmem_ready,
    // ------------------------------------------------ 回给核心
    output logic        busy,         // 1 = 还没做完，核心必须冻结
    output logic        done,         // 1 = 本周期完成，rdata 有效
    output logic [31:0] rdata         // 已完成扩展的载入结果
);

  typedef enum logic [1:0] {IDLE, REQ, FINISH} state_t;
  state_t state;

  // 请求锁存
  logic        is_write;
  logic [2:0]  funct3_r;
  logic [2:0]  size;        // 访问宽度（字节数）
  logic [1:0]  off;         // 地址在一个字内的偏移
  logic [31:0] wdata_r;
  logic        step;        // 0 = 第一笔事务，1 = 第二笔
  logic        need_two;    // 是否需要第二笔事务（跨字）

  // 两笔事务的参数
  logic [31:0] addr0, addr1;
  logic [3:0]  mask0, mask1;
  logic [31:0] data0, data1;

  // 载入数据缓冲
  logic [31:0] word0, word1;

  function automatic logic [2:0] size_of(input logic [2:0] f3);
    case (f3)
      3'b000, 3'b100: size_of = 3'd1;   // lb / lbu
      3'b001, 3'b101: size_of = 3'd2;   // lh / lhu
      default:        size_of = 3'd4;   // lw / sw
    endcase
  endfunction

  function automatic logic [3:0] base_mask(input logic [2:0] f3);
    case (f3)
      3'b000, 3'b100: base_mask = 4'b0001;
      3'b001, 3'b101: base_mask = 4'b0011;
      default:        base_mask = 4'b1111;
    endcase
  endfunction

  // ---------------------------------------------------------------- 状态机
  always_ff @(posedge clk) begin
    if (rst) begin
      state   <= IDLE;
      step    <= 1'b0;
      need_two <= 1'b0;
      word0   <= 32'h0;
      word1   <= 32'h0;
    end else begin
      unique case (state)
        IDLE: begin
          if (req_valid) begin
            logic [2:0] sz;
            sz       = size_of(req_funct3);
            size     <= sz;
            off      <= req_addr[1:0];
            is_write <= req_write;
            funct3_r <= req_funct3;
            wdata_r  <= req_wdata;
            addr0    <= {req_addr[31:2], 2'b00};
            addr1    <= {req_addr[31:2], 2'b00} + 32'd4;
            mask0    <= base_mask(req_funct3) << req_addr[1:0];
            data0    <= req_wdata << (8 * req_addr[1:0]);
            need_two <= ({1'b0, req_addr[1:0]} + sz) > 3'd4;
            mask1    <= base_mask(req_funct3) >> (3'd4 - {1'b0, req_addr[1:0]});
            data1    <= req_wdata >> (8 * (3'd4 - {1'b0, req_addr[1:0]}));
            step     <= 1'b0;
            if (!req_write) begin
              word0 <= 32'h0;
              word1 <= 32'h0;
            end
            state <= REQ;
          end
        end
        REQ: begin
          if (dmem_ready) begin
            if (!is_write) begin
              if (!step) word0 <= dmem_rdata;
              else       word1 <= dmem_rdata;
            end
            if (need_two && !step) step  <= 1'b1;
            else                   state <= FINISH;
          end
        end
        FINISH: state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end

  // -------------------------------------------------------------- 对外输出
  always_comb begin
    dmem_valid = 1'b0;
    dmem_we    = 1'b0;
    dmem_addr  = 32'h0;
    dmem_wmask = 4'b0000;
    dmem_wdata = 32'h0;
    busy       = (state != IDLE);
    done       = (state == FINISH);

    if (state == REQ) begin
      dmem_valid = 1'b1;
      dmem_we    = is_write;
      if (!step) begin
        dmem_addr  = addr0;
        dmem_wmask = mask0;
        dmem_wdata = data0;
      end else begin
        dmem_addr  = addr1;
        dmem_wmask = mask1;
        dmem_wdata = data1;
      end
    end
  end

  // 载入结果的字节重排与扩展
  logic [63:0] combined;
  logic [63:0] shifted;
  always_comb begin
    combined = {word1, word0};
    shifted  = combined >> (8 * off);
    unique case (funct3_r)
      3'b000:  rdata = {{24{shifted[7]}}, shifted[7:0]};    // lb
      3'b001:  rdata = {{16{shifted[15]}}, shifted[15:0]};  // lh
      3'b100:  rdata = {24'b0, shifted[7:0]};               // lbu
      3'b101:  rdata = {16'b0, shifted[15:0]};              // lhu
      default: rdata = shifted[31:0];                       // lw
    endcase
  end

endmodule

`default_nettype wire

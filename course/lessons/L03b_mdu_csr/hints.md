# L03b 分级提示

## 提示 1：高位乘法怎么写

```systemverilog
logic [63:0]        uprod;      assign uprod    = a * b;                    // 无符号×无符号
logic signed [31:0] sa, sb;     assign sa = a; assign sb = b;
logic signed [63:0] sprod;      assign sprod    = sa * sb;                  // 有符号×有符号
logic signed [63:0] sprod_su;   assign sprod_su = sa * $signed({1'b0, b});  // 有符号×无符号
```

`mulh=sprod[63:32]`、`mulhsu=sprod_su[63:32]`、`mulhu=uprod[63:32]`。

## 提示 2：除法的三个边界

```systemverilog
3'b100: begin                                     // div
  if (b == 32'd0)                                    y = 32'hFFFF_FFFF;
  else if (a == 32'h8000_0000 && b == 32'hFFFF_FFFF) y = 32'h8000_0000;
  else                                               y = sa / sb;
end
3'b110: begin                                     // rem
  if (b == 32'd0)                                    y = a;
  else if (a == 32'h8000_0000 && b == 32'hFFFF_FFFF) y = 32'h0;
  else                                               y = sa % sb;
end
```

`divu`/`remu` 不需要溢出判断，但同样要挡除零。

## 提示 3：CSR 读端口

```systemverilog
always_comb begin
  unique case (raddr)
    12'h300: rdata = mstatus;
    12'h301: rdata = 32'h4000_1100;   // misa 只读
    12'h305: rdata = mtvec;
    12'h340: rdata = mscratch;
    12'h341: rdata = mepc;
    12'h342: rdata = mcause;
    12'h343: rdata = mtval;
    12'hF14: rdata = 32'h0;           // mhartid 只读
    default: rdata = 32'h0;
  endcase
end
```

## 提示 4：CSR 写端口与异常提交

```systemverilog
if (we) begin
  unique case (waddr)
    12'h300: mstatus  <= wdata;
    12'h305: mtvec    <= wdata;
    12'h340: mscratch <= wdata;
    12'h341: mepc     <= wdata;
    12'h342: mcause   <= wdata;
    12'h343: mtval    <= wdata;
    default: ;                       // misa / mhartid 只读
  endcase
end
if (trap_en) begin                   // 写在后面 → 优先级更高
  mepc   <= trap_epc;
  mcause <= trap_cause;
  mtval  <= 32'h0;
end
```

## 提示 5：异常为什么超时

如果 `09_exception.S` 超时、而且 trace 里反复出现同一条 pc，说明 `mret` 回到了
触发异常的指令本身：异常处理程序必须先改 `mepc`：

```asm
csrr t2, mepc
addi t2, t2, 4      # 跳过触发异常的 4 字节指令
csrw mepc, t2
mret
```

## 提示 6：CSR 也有冒险

`csrw mepc, t2` 的写发生在 WB 级，而 `mret` 在 EX 级就要读 mepc——
所以核心里有 CSR 旁路（`ex_csr_rdata_f` / `csr_mepc_f`）。
如果你自己改核心，记得保留这段；否则 `mret` 会返回旧地址。

参考实现在 `course/lessons/L03b_mdu_csr/refs/`。

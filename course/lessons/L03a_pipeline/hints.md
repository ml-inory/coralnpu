# L03a 分级提示

## 提示 1：先让它"不流水"

如果一上来就报第 2 条指令错，说明旁路还没接。先把 TODO 1 做出来：

```systemverilog
fwd_a = ex_rs1_val;
fwd_b = ex_rs2_val;
if (mem_valid && mem_reg_we && !mem_is_load && rd_of(mem_inst) != 0 && rd_of(mem_inst) == rs1_of(ex_inst))
  fwd_a = mem_alu_y;
else if (wb_valid && wb_reg_we && rd_of(wb_inst) != 0 && rd_of(wb_inst) == rs1_of(ex_inst))
  fwd_a = wb_data;
```

`fwd_b` 照抄一遍（把 `rs1` 换成 `rs2`）。做完 `01_arith.S` 应该能过。

## 提示 2：为什么还需要 WB→ID

寄存器堆在 WB 级写、ID 级读，同一个时钟沿。ID 读到的永远是"写之前"的值，
而这时已经没有更晚的旁路来源了（生产者马上要离开流水线）。所以：

```systemverilog
id_bypass_rs1 = wb_valid & wb_reg_we & (rd_of(wb_inst) != 0) && (rd_of(wb_inst) == rs1_of(id_inst));
```

## 提示 3：load-use 的"冻结 + 气泡"

条件：EX 是 load，ID 的指令马上要用它的结果。

处理：**冻 PC/IF**（消费者留在 ID），**给 ID/EX 插气泡**（`ex_valid <= 0`），
**让 EX/MEM 正常前进**（load 进入 MEM）。

::: {.warn}
如果这里把整条流水线都冻住，load 也走不掉，`load_use_stall` 会一直为 1 → 死循环。
:::

## 提示 4：冲刷谁、重定向到哪

```systemverilog
ex_redirect = ex_valid & (ex_br_taken | ex_is_jal | ex_is_jalr | ex_is_halt);
```

* IF/ID 与 ID/EX 的有效位清 0（错路指令）；
* `pc <= ex_target`（`jal` 用 `pc+imm_j`，`jalr` 用 `(rs1+imm)&~1`，分支用 `pc+imm_b`，
  停机指令就停在原地）。

## 提示 5：气泡的控制位

```systemverilog
mem_reg_we   <= ex_reg_we   & ex_valid;
mem_is_load  <= ex_is_load  & ex_valid;
mem_is_store <= ex_is_store & ex_valid;
```

漏掉 `& ex_valid` 的典型症状：**某个跟出错指令毫不相关的寄存器被改成了别的值**。

## 提示 6：等 LSU 时要冻整条流水线

```systemverilog
stall_all = lsu_wait;            // MEM 级是一条还没完成的访存
```

而且冻结要**包含 MEM/WB**：否则停在 EX 的消费者还在等 WB 的旁路结果，
生产者却已经离开流水线，消费者只能读到旧值。

同时记得把 retire 门控起来：`o_retire_valid = wb_valid & ~stall_all & ~o_halted;`
否则同一个 WB 指令会被 trace 记录好几拍。

参考实现在 `course/lessons/L03a_pipeline/refs/pipeline_core.sv`。

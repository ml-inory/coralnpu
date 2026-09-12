# L01 分级提示

提示按顺序给：先自己想，卡住超过 20 分钟再看下一条。

## 提示 1：从哪条指令开始

不要一上来写全指令集。先把 `01_arith.S` 的第一条指令跑对：

```
00000000 00018117 02 00018000    auipc sp, 0x18
```

它对你的要求是：PC 会前进、U 型立即数会拼、`o_retire_rd/wdata` 会反映写回。
把这三件事做对，trace 就会往前走一步，检查器的失败位置会自然向后移。

## 提示 2：立即数的四种格式

```systemverilog
imm_i = {{20{inst[31]}}, inst[31:20]};
imm_s = {{20{inst[31]}}, inst[31:25], inst[11:7]};
imm_b = {{19{inst[31]}}, inst[31], inst[7], inst[30:25], inst[11:8], 1'b0};
imm_u = {inst[31:12], 12'b0};
imm_j = {{11{inst[31]}}, inst[31], inst[19:12], inst[20], inst[30:21], 1'b0};
```

B 型和 J 型的位序是为了让硬件尽量少走线而设计的，位不连续是正常的。
注意所有立即数都要做符号扩展，只有 U 型不需要。

## 提示 3：写掩码与字节对齐

数据端口一次收/发 32 位（一个字）。`sb`/`sh` 要考虑地址的低 2 位：

```systemverilog
wmask = (funct3 == 3'b000) ? (4'b0001 << alu_y[1:0]) :
        (funct3 == 3'b001) ? (4'b0011 << alu_y[1:0]) : 4'b1111;
store_data = rs2_val << (8 * alu_y[1:0]);
```

载入方向反过来：先把整字右移 `8*alu_y[1:0]` 位，再取需要的字节/半字。

## 提示 4：算术右移与 Verilog 的坑

`$signed(a) >>> b` 在很多工具里会因为上下文变成逻辑移位（结果高位补 0），
这是初学者最常踩的坑。稳妥写法是显式构造符号填充掩码：

```systemverilog
asr = (value >> shamt) | ({32{value[31]}} & ~(32'hFFFF_FFFF >> shamt));
```

## 提示 5：分支与跳转

* `jal`/`jalr` 都要把 `PC+4` 写回 `rd`；`rd` 是 x0 时不要写。
* `jalr` 的目标地址最低位必须清零：`(rs1 + imm) & ~32'd1`。
* 分支不跳时 `next_pc = PC+4`，跳时 `next_pc = PC + imm_b`。

## 提示 6：到底怎么调

单条指令级别调试时，把 trace 和黄金模型对齐看最快：

```bash
python3 course/lessons/L01_scalar/tests/checks.py --only 01   # 跑到第一条不一致
vvp course/work/L01/sim.vvp +PROGRAM=... +TRACE=/tmp/t.txt     # 看波形/加 $display
```

参考实现在 `course/lessons/L01_scalar/refs/cpu_core.sv`，
`./learn unlock L01` 可以解锁对照（建议先自己跑通 3 个用例）。

## 提示 7：想复用 L00 的 alu32

可以，检查器会自动编译 `course/lessons/L00_setup/rtl/alu32.sv`：

```systemverilog
  alu32 u_alu (.a(alu_a), .b(alu_b), .op(alu_op), .y(alu_y), .zero(alu_zero));
```

三个容易接错的地方：

1. `alu_a` 不是永远等于 `rs1_val`——`auipc` 要用 `pc`；
2. `alu_b` 在 OP-IMM 里是 `imm_i`，在 OP 里是 `rs2_val`，存储指令里是 `imm_s`；
3. `add`/`sub` 与 `srl`/`sra` 靠 `inst[30]` 区分，别忘了。

完整示例见 `refs/cpu_core_reuse.sv`，作业说明第 9 节有对照表和取舍说明。

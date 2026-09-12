# L02 分级提示

## 提示 1：从"一次对齐访问"开始

先别管延迟和非对齐。目标：让 `03_mem.S` 在 `latency=0` 下通过。

```
IDLE: req_valid=1 → 锁存、算参数、state<=REQ
REQ : dmem_valid=1, addr={addr[31:2],2'b00}, mask=base_mask<<off, data=wdata<<(8*off)
      dmem_ready=1 → 读：word0<=dmem_rdata；写：什么都不存；state<=FINISH
FINISH: done=1 → 下一拍 state<=IDLE
```

## 提示 2：为什么 latency=2 会挂

`ready` 为 0 时，你的输出必须**保持不变**，而且**不能采样 dmem_rdata**——
那时的数据还没准备好。把"采样"和"进入下一状态"都放在 `dmem_ready` 成立的分支里。

一个常见的错法：

```systemverilog
// 错：不管 ready 就采样，latency=0 时看起来对，latency=2 时采样到旧数据
word0 <= dmem_rdata;
```

## 提示 3：非对齐要拆两笔

判断条件：`(off + size) > 4`。

两笔的参数：

```systemverilog
addr0 = {addr[31:2], 2'b00};   addr1 = addr0 + 4;
mask0 = base_mask << off;      mask1 = base_mask >> (4 - off);
data0 = wdata << (8*off);      data1 = wdata >> (8*(4-off));
```

用一个 `step` 位记住"现在是第一笔还是第二笔"，第一笔完成且 `need_two` 时切到 `step=1`，
否则直接进 `FINISH`。

## 提示 4：载入结果的拼接

```systemverilog
combined = {word1, word0};              // 64 位，低 32 位是第一笔
shifted  = combined >> (8 * off);       // 目标字节挪到最低位
```

然后按 `funct3` 取 1/2/4 字节并扩展。**单笔事务时 `word1` 保持 0**，公式依然成立。

## 提示 5：`done` 的时序

`done` 只应该拉高一拍：在 `FINISH` 状态拉高，下一拍回 `IDLE`。
如果它持续多拍，核心会把同一条指令提交两次，检查器会报"trace 行数不同"。

## 提示 6：还不行就看事务

```systemverilog
always_ff @(posedge clk)
  if (!rst && dmem_valid && dmem_ready)
    $display("[lsu] %s addr=%08x mask=%b data=%08x step=%0d",
             dmem_we ? "WR" : "RD", dmem_addr, dmem_wmask, dmem_wdata, step);
```

对着 `06_unaligned.S` 的注释逐条核对：

* `sh 0xBEEF, 1(s5)` → 1 笔，`addr=A`，`mask=0110`，`data=0x0000BEEF<<8`
* `sw 0xAABBCCDD, 3(s5)` → 2 笔：`mask=1000` 后接 `mask=0111`

参考实现在 `course/lessons/L02_lsu/refs/lsu.sv`，`./learn unlock L02` 可以查看路径。

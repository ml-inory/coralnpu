# L01 · RV32I 单周期核

**目标**：从零写出一颗能跑真实 C 程序的 RISC-V 核心。

## 前置

完成 L00（`./learn check L00` 通过）。你需要的工具链在 L00 已经装好。

## 教材

* [`pdf/基础知识.pdf`](pdf/基础知识.pdf)：单周期数据通路、RV32I 指令集与编码、
  内存与调用约定、Verilog 陷阱、与上游 CoralNPU 的差距、参考资料
* [`pdf/作业说明.pdf`](pdf/作业说明.pdf)：7 个 Step 的任务分解、验收标准、
  调试五招、常见坑清单、进阶挑战

## 你的任务

只改一个文件：[`rtl/cpu_core.sv`](rtl/cpu_core.sv)（6 个 TODO）。

| TODO | 内容 | 对应知识 |
| --- | --- | --- |
| 1 | 立即数生成（I/S/B/U/J） | 基础知识 3.2 节 |
| 2 | 译码：funct3/funct7 → ALU 操作 | 3.3 节指令语义表 |
| 3 | ALU：算术/逻辑/移位/比较 | 2.2、3.3 节 |
| 4 | 控制：写回、访存、分支跳转 | 1.2 节数据通路 |
| 5 | 访存：掩码、字节选择、符号扩展 | 4.2 节 |
| 6 | trace：`o_retire_rd` / `o_retire_wdata` | 第 5 章 |

## 验收

```bash
./learn check L01              # 全部用例
./learn check L01 --only 03    # 只跑访存用例
./learn hint L01 2             # 卡住时的第 2 条提示
./learn unlock L01             # 跑通大部分用例后再对照参考实现
```

期望：`5/5 个用例通过`，包括一个用真实 `riscv64-unknown-elf-gcc` 编译的 C 程序。

## 学完之后你应该能回答

* `jalr` 为什么要清最低位？`jal` 和 `jalr` 有什么区别？
* `lb 1(s5)` 在数据端口上会读到什么？为什么要先右移整字？
* 为什么 `$signed(a) >>> b` 可能出错？
* 上游 CoralNPU 比你的核多了哪些能力（流水线、派发、乱序退休、slot 访存）？


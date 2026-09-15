# L03b · M 扩展、CSR 与异常

**目标**：给 L03a 的流水线核加上三样东西：

1. **M 扩展**（乘除法）：`mul/mulh/mulhsu/mulhu` 与 `div/divu/rem/remu`；
2. **CSR 与 Zicsr**：`csrrw/csrrs/csrrc` 及其立即数形式，最小 CSR 集合；
3. **异常**：`ecall` / 非法指令触发异常 → 跳到 `mtvec` → `mret` 返回。

## 前置

`./learn check L03a` 通过（L03b 复用你 L03a 的流水线、L02 的 LSU、L00 的 ALU）。

## 教材

* [`pdf/基础知识.pdf`](pdf/基础知识.pdf)：M 扩展的语义与三个边界情况、CSR 的读写语义、
  异常进入/返回的完整流程、与上游的对照
* [`pdf/作业说明.pdf`](pdf/作业说明.pdf)：两个模块的接口与分步任务、调试方法、常见坑

## 你的任务

**改两个文件**（核心 `tests/core_l03b.sv` 由课程提供）：

| 文件 | 内容 |
| --- | --- |
| [`rtl/mdu.sv`](rtl/mdu.sv) | 8 条 M 扩展指令；重点是符号扩展、除零、溢出三个边界 |
| [`rtl/csr_file.sv`](rtl/csr_file.sv) | 最小 CSR 寄存器堆：读端口（组合）+ 写端口（WB 提交）+ 异常提交 |

## 验收

```bash
./learn check L03b              # 期望 18/18（9 个程序 × 2 种存储器延迟）
./learn check L03b --only 09    # 只看异常流程
./learn hint L03b 2             # 卡住时的提示
```

回归：L01/L02/L03a 的 6 个程序也会一起跑，确保新功能没有破坏旧行为。

## 学完之后你应该能回答

* `mulh` 和 `mulhu` 为什么结果不同？怎么用 Verilog 得到 64 位乘积？
* 除以零时 RISC-V 规定返回什么？为什么不能直接写 `a / b`？
* `csrrs rd, csr, x0` 为什么不能写 CSR？这条规定防的是什么？
* 异常发生时，`mepc`/`mcause` 是谁写的、什么时候写的？
* `mret` 之后为什么能回到触发异常的指令的下一条？（谁改了 mepc？）

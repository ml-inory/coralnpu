# L00 · 环境、工具链与仓库地图

**目标**：装好工具链，理解「写 RTL → 仿真 → 对拍」这个闭环，写出你的第一个硬件模块。

## 开始之前

```bash
./learn doctor          # 必须全绿（verilator 可选）
./learn pdf L00         # 如果 pdf/ 里已经有 PDF 可以跳过
```

## 教材

* [`pdf/基础知识.pdf`](pdf/基础知识.pdf)：这门课要造什么、仓库地图、地址映射、Verilog 最小必备
* [`pdf/作业说明.pdf`](pdf/作业说明.pdf)：4 个作业的完整说明、调试方法与常见坑

## 你的任务

1. **环境自检**：`./learn doctor` 全绿；
2. **仓库地图问答**：填 [`answers.md`](answers.md) 里的 5 个 TODO；
3. **写第一个 RTL 模块**：[`rtl/alu32.sv`](rtl/alu32.sv)（3 个 TODO）；
4. **端到端跑通**：把 `tests/programs/hello.c` 编译并在黄金模型上执行。

## 验收

```bash
./learn check L00        # 期望：4/4 个作业通过
```

## 学完之后你应该能回答

* ITCM 和 DTCM 分别在哪、装什么？
* 一条 C 语句是怎么变成 ITCM 里的机器码的？
* 裸机程序怎么停机？为什么是 `mpause`？
* 组合逻辑和时序逻辑在 Verilog 里分别怎么写？


# 课程路线图

从「没写过 RTL」到「自己造出一颗能跑神经网络的 NPU」，一共 10 个阶段。
L00–L04 已完成教材与检查器（L04：AXI 外壳与 5 步启动流程），后续阶段按同一套结构陆续补齐。

## 阶段总览

| 阶段 | 主题 | 你实现什么 | 验收方式 | 上游锚点 |
| --- | --- | --- | --- | --- |
| P0 | 预备课（可跳过） | 命令行 / 编译链接 / 数字逻辑 / Verilog / RISC-V 的最小集 | 5 个模块通过（含 3 个 RTL 小练习） | —（纯前置知识） |
| L00 | 环境与仓库地图 | 工具链、第一个 RTL 模块（ALU） | 4 个作业全通过 | `utils/coralnpu.dockerfile`、`doc/integration_guide.md` |
| L01 | RV32I 单周期核 | 取指/译码/执行/访存/写回 | 5 个用例（含真实 C 程序）全通过 | `scalar/Decode.scala`、`scalar/Alu.scala` |
| L02 | 访存子系统 | 字节/半字掩码、非对齐、slot 式访存状态机 | 访存边界用例 + 与上游时序对照 | `doc/microarch/lsu.md` |
| L03 | 流水线与冒险 | 4 级流水、记分板、退休缓冲、M 扩展、CSR、异常 | csr/exceptions/isa 测试子集 | `doc/microarch/dispatch.md`、`RetirementBuffer.scala` |
| L04 | AXI 外壳与启动 | AXI 从/主接口、RESET/PC_START/STATUS CSR | 按上游 5 步启动流程加载 ELF | `doc/integration_guide.md`、`CoreAxiCSR.scala` |
| L05 | 浮点单元 | fregfile、fcsr、加减乘 | 跑通 `hello_world_add_floats.cc` | `float/FloatCore.scala` |
| L06 | 向量核（RVV） | vsetvl/vtype、stripmining、掩码、vstart、向量访存 | 跑通 `rvv_add_intrinsic.cc` 与向量测试子集 | `rvv/RvvCore.scala`、`hdl/verilog/rvv/design/` |
| L07 | 矩阵引擎（Zvt） | 外积 MAC、8×8 累加器、vtmmu/vtmms/vtfmm、mset*/vtmv | matmul 结果与 numpy 一致 | `vme_test/vme_matmul_test_program.cc`、`Zvt/` |
| L08 | 总线与外设 | TileLink-UL 交叉开关、GPIO/SPI、描述符链表 DMA | DMA 集成测试（含轮询流控） | `doc/peripherals/dma.md`、`bus/DmaEngine.scala` |
| L09 | 软件栈与模型 | 链接脚本、启动代码、RVV intrinsic、TFLite Micro | 小模型端到端出结果 | `doc/tutorials/npusim_mobilenet_tutorial.md` |
| L10 | 验证方法学与毕业项目 | cocotb/Verilator 回归、随机指令、对拍 | 自选模型跑通 + 回归全绿 | `tests/cocotb/`、`tests/uvm/`、`fpga/` |

## 三个阶段块

**第一块：标量核（L00–L04）** —— 目标是把「处理器是怎么工作的」彻底搞清楚。
完成时你拥有一个能启动、能跑 C 程序、有流水线和异常处理的 RISC-V 核心。

**第二块：算力（L05–L07）** —— 目标是理解 AI 加速器到底加速了什么。
浮点让你能算，向量让你能并行算逐元素操作，矩阵引擎让你能用外积结构把 MAC 阵列喂满。

**第三块：系统与软件（L08–L10）** —— 目标是让整台机器能跑真实模型。
总线与外设解决数据进出，软件栈解决模型怎么落到硬件上，验证方法学解决「怎么确信它是对的」。

## 每节课的固定结构

```
lessons/L0x_<主题>/
├── README.md          课程入口（本课目标、怎么开始）
├── basics.md          基础知识（→ pdf/基础知识.pdf）
├── homework.md        作业说明（→ pdf/作业说明.pdf）
├── rtl/               你要实现的 RTL（骨架带 TODO）
├── refs/              参考实现（默认不建议先看）
├── tests/             检查器、测试程序、仿真平台
├── diagrams/          插图（脚本生成，保证与代码一致）
└── pdf/               渲染出的 PDF
```

## 三层验证体系

| 层 | 工具 | 反馈时间 | 用途 |
| --- | --- | --- | --- |
| A 层 | Python 黄金模型 | 毫秒 | 单条指令语义、算法级正确性 |
| B 层 | iverilog | 秒 | 你的 RTL 与黄金模型逐指令对拍（主循环） |
| C 层 | Bazel + cocotb / Verilator | 分钟 | 与上游验证环境对齐（L04 之后逐步引入） |

课程约定：**A 层和 B 层必须能在 2 核笔记本上 60 秒内跑完**，否则检查器要标注为慢速可选。

## 参考实现与自动检查

每节课的参考实现都放在 `refs/`，并且课程 CI 会用 `./learn check <课> --ref` 验证它——
这样课程本身不会腐烂：如果某个检查器写错了，参考实现也会失败。

# 第 0 章　为什么需要这一册

一个仓库不是一套知识。CoralNPU 里有 7 万行 SystemVerilog、3.5 万行 Chisel、上千行文档，
但它们回答的是「**我们这么做**」，不回答「**为什么应该这么做、换一个场景该怎么做**」。

如果你只是照着这个仓库抄一遍，你会得到「会改 CoralNPU」的能力；
如果你掌握的是它背后的原理、标准与设计模式，你会得到「能设计任何处理器与加速器部件」的能力。
这一册就是为后者写的——它给整门课装上骨架，并告诉你每一块知识在更大的版图里位于哪里。

三条原则贯穿全部课程：

1. **原理先行**：先问「这个问题在体系结构/数字设计里叫什么」，再看这个仓库怎么解；
2. **标准为纲**：ISA、总线、Verilog、验证方法都有公开标准，标准是普适性的锚点，仓库只是实现之一；
3. **迁移为验**：学完一课的标志不是「我的 RTL 通过了检查」，而是「我能把它讲给另一个场景听」。

![五根支柱](diagrams/knowledge_pillars.svg)

# 第 1 章　五根支柱

## 1.1 数字与硬件设计（Digital Design）

**核心问题**：怎么把逻辑功能变成可靠、可实现、可验证的电路？

必须掌握的概念：组合逻辑与时序逻辑的分界、时钟与复位策略、状态机（Moore/Mealy）、
位宽与符号扩展、可综合子集与不可综合构造、时序收敛与关键路径、功耗与时钟门控、跨时钟域与同步器。

**权威来源**

* Harris & Harris《Digital Design and Computer Architecture: RISC-V Edition》
  <https://shop.elsevier.com/books/digital-design-and-computer-architecture/harris/978-0-12-820064-3>
* Weste & Harris《CMOS VLSI Design》（想往后端走时读）
* IEEE 1800 SystemVerilog 标准 <https://standards.ieee.org/ieee/1800/6379/>
* HDLBits 练习 <https://hdlbits.01xz.net/wiki/Main_Page>

**在本课程中**：L00（组合/时序、ALU）、L01（时序状态与复位）、L03（流水线寄存器、关键路径）。

## 1.2 计算机体系结构（Computer Architecture）

**核心问题**：指令集（ISA）如何变成微架构（microarchitecture）？性能从哪里来？

必须掌握的概念：ISA 与 ABI、指令编码与译码、取指/译码/执行/访存/写回、
流水线与冒险（结构/数据/控制）、记分板与重排序、分支预测、
存储层次与访存一致性、异常与中断、虚拟内存与特权级。

**权威来源**

* Hennessy & Patterson《Computer Architecture: A Quantitative Approach》
  <https://shop.elsevier.com/books/computer-architecture/hennessy/978-0-12-811905-1>
  （量化分析的方法论：Amdahl 定律、CPI、roofline 的思想源头）
* Patterson & Hennessy《Computer Organization and Design: RISC-V Edition》
  <https://www.elsevier.com/books/computer-organization-and-design-risc-v-edition/patterson/978-0-12-820331-6>
* RISC-V 指令集规范 <https://riscv.org/technical/specifications/>　·　源码 <https://github.com/riscv/riscv-isa-manual>
* Berkeley CS61C <https://inst.eecs.berkeley.edu/~cs61c/>（公开课与实验）

**在本课程中**：L01（ISA → 数据通路）、L03（流水线与冒险）、L04（异常与系统接口）。

## 1.3 AI 加速器与机器学习系统（Accelerators & ML Systems）

**核心问题**：神经网络的算力需求怎么映射到硬件？瓶颈在算、在访存、还是在数据搬运？

必须掌握的概念：数据并行（SIMD/SIMT）、脉动阵列与外积结构、权重固定/输出固定/行固定数据流、
分块与复用（tiling、reuse）、量化与定点算术、稀疏与压缩、
性能模型（roofline、算术强度 arithmetic intensity）、算子融合与编译器栈。

**权威来源**

* Sze 等《Efficient Processing of Deep Neural Networks: A Tutorial and Survey》
  <https://arxiv.org/abs/1703.09039>（加速器数据流与复用分析的经典综述）
* Eyeriss 项目（MIT，权重固定数据流的代表） <https://eyeriss.mit.edu/>
* Gemmini（Berkeley，脉动阵列生成器） <https://github.com/ucb-bar/gemmini>
* NVDLA（NVIDIA 开源加速器） <https://github.com/nvdla/hw>
* TVM / VTA（编译器与加速器协同） <https://tvm.apache.org/>　·　<https://github.com/apache/tvm-vta>

**在本课程中**：L05（浮点）、L06（SIMD 向量核）、L07（外积 MAC 阵列）、L09（模型落地）。

## 1.4 系统与互连（Systems & Interconnect）

**核心问题**：模块之间怎么通信，整台机器怎么启动、怎么被配置？

必须掌握的概念：握手协议（valid/ready）、总线事务与突发、主从与地址解码、
仲裁与服务质量、DMA 与描述符链表、中断与中断控制器、时钟与复位域、
存储器映射与 MMIO、SoC 集成与启动流程。

**权威来源**

* Arm AMBA AXI 规范 <https://developer.arm.com/documentation/ihi0022/latest/>（工业界最常用的片上总线之一）
* TileLink 规范 <https://github.com/chipsalliance/tilelink>（RISC-V 生态常用，CoralNPU 内部交叉开关用它）
* OpenTitan（开源 SoC 与安全外设实例） <https://opentitan.org/>
* Chipyard（从核到 SoC 的集成框架） <https://github.com/ucb-bar/chipyard>

**在本课程中**：L04（AXI 外壳与启动）、L08（交叉开关、外设、DMA）。

## 1.5 工程方法学（Methodology）

**核心问题**：谁来判断你的设计是对的？你怎么知道它明天还是对的？

必须掌握的概念：黄金模型与参考实现、定向测试与随机测试、覆盖率的含义与陷阱、
形式验证（等价性、性质检查）、回归与持续集成、版本与可复现性、
性能建模与基准测试方法。

**权威来源**

* cocotb（Python 验证框架，本仓库正在用） <https://docs.cocotb.org/>
* UVM（工业界验证方法学） <https://www.accellera.org/downloads/standards/uvm>
* riscv-tests（RISC-V 官方一致性测试） <https://github.com/riscv-software-src/riscv-tests>
* riscv-dv（随机指令流生成器） <https://github.com/chipsalliance/riscv-dv>
* SymbiYosys（形式验证入门工具） <https://github.com/YosysHQ/sby>

**在本课程中**：L00（对拍闭环）、每节课的检查器、L10（完整验证方法学）。

# 第 2 章　知识坐标：本课程与经典课程/教材的对应

如果你想补课，下面的对照表告诉你每节课对应哪些公开课程的哪一部分。**不必按顺序全读**，
在卡住的时候当作查阅入口用。

| 本课程阶段 | DDCA（Harris） | COD（Patterson） | H&P 量化方法 | CS61C / 其他 |
| --- | --- | --- | --- | --- |
| L00 环境与 RTL 入门 | 第 3–5 章 | 第 1–2 章 | — | CS61C 第 1–2 周；HDLBits |
| L01 单周期核 | 第 7 章 | 第 4 章 | 附录 C | CS61C 第 3–4 周 |
| L02 访存子系统 | 第 8 章 | 第 5 章 | 第 2 章（存储层次） | CS61C 第 5 周 |
| L03 流水线与冒险 | 第 7.5 节 | 第 4.5–4.8 节 | 第 3 章 | CS61C 第 6–7 周 |
| L04 AXI 与启动 | — | — | 第 6 章（存储系统） | AMBA 规范、OpenTitan 文档 |
| L05 浮点单元 | 第 5.3 节 | 第 3.5 节 | 附录 J | IEEE 754 规范 |
| L06 向量核 | — | 第 6 章（并行处理器） | 第 4–5 章（数据级并行） | RISC-V V 扩展规范 |
| L07 矩阵引擎 | — | — | 第 7 章（领域专用架构） | Sze 综述、Eyeriss、Gemmini |
| L08 总线外设与 DMA | — | 第 6.5 节（I/O） | 第 6 章 | AMBA / TileLink 规范 |
| L09 软件栈与模型 | — | 第 2.1 节 | — | TVM/MLIR/IREE 文档 |
| L10 验证方法学 | — | — | 附录（性能评估） | cocotb / UVM / riscv-tests |

（DDCA =《Digital Design and Computer Architecture: RISC-V Edition》；
COD =《Computer Organization and Design: RISC-V Edition》；
H&P =《Computer Architecture: A Quantitative Approach》。）

# 第 3 章　十个阶段 × 五根支柱

每一行给出：**本阶段的通用主题**（可迁移的知识）、**可迁移能力**（学完能做什么别的事）、
**本仓库实例**（我们借它练习的具体对象）、**外部对照对象**（该怎么检验普适性）。

| 阶段 | 通用主题 | 可迁移能力 | 本仓库实例 | 外部对照对象 |
| --- | --- | --- | --- | --- |
| L00 | 抽象层次、工具链、对拍方法 | 能搭建任意 RTL 项目的验证闭环 | `course/tools/`、`utils/coralnpu.dockerfile` | 任意 RTL 项目（Verilator/cocotb 教程） |
| L01 | ISA → 数据通路、译码 | 能实现并验证任一 RV32I 核心 | `scalar/Decode.scala`、`Alu.scala` | PicoRV32、Ibex、CV32E40P |
| L02 | 访存路径设计（地址生成、掩码、非对齐、outstanding） | 能设计任意处理器的 load/store 通路 | `doc/microarch/lsu.md`、`Lsu.scala` | Rocket/CVA6 的 LSU、AMBA 的 burst 语义 |
| L03 | 流水线、冒险、乱序退休、乘除法 | 能做流水线重构与风险分析 | `RetirementBuffer.scala`、`Mlu.scala` | BOOM、CVA6、XiangShan |
| L04 | 系统接口、启动与配置 | 能把核集成进任意 SoC | `doc/integration_guide.md`、`CoreAxiCSR.scala` | OpenTitan、Chipyard |
| L05 | 浮点算术与舍入 | 能实现/复用 IEEE-754 运算单元 | `float/FloatCore.scala` | Berkeley HardFloat、cvfpu |
| L06 | 数据级并行、可变长向量 | 能把标量算法向量化并验证 | `rvv/RvvCore.scala`、`hdl/verilog/rvv/` | RISC-V V 规范、RVV intrinsic 文档 |
| L07 | 领域专用架构、数据流与复用 | 能做加速器性能建模与阵列设计 | `Zvt/zvt_pe_array.sv`、`vme_test/` | Eyeriss、Gemmini、NVDLA |
| L08 | 互连协议、外设与 DMA | 能设计总线从设备与数据搬运引擎 | `bus/DmaEngine.scala`、`doc/peripherals/dma.md` | AMBA AXI-Stream、OpenTitan IP |
| L09 | 编译器/运行时与硬件协同 | 能把模型落到硬件并量化性能 | `sw/opt/litert-micro/`、`npusim` 教程 | TVM、MLIR、IREE |
| L10 | 验证方法论与回归体系 | 能设计一套让人相信的验证方案 | `tests/cocotb/`、`tests/uvm/` | UVM、riscv-dv、riscv-tests |

# 第 4 章　通用设计模式库

硬件设计里真正「可迁移」的东西是一批反复出现的模式。下表是整门课的模式索引——
**每学到一个新模式，回来在表里记下你第一次真正理解它的位置**。

| 模式 | 一句话定义 | 首次出现 | 之后在哪里复用 | 现实世界的同构物 |
| --- | --- | --- | --- | --- |
| 有限状态机（FSM） | 用状态变量描述时序行为 | L01（隐含）、L02 | 访存、DMA、总线从设备、握手 | 所有控制逻辑 |
| valid/ready 握手 | 上下游用两根线达成传送共识 | L01 端口契约 | 总线、FIFO、流水线级间 | AXI/TileLink 通道 |
| 背压（backpressure） | 下游没准备好时上游必须停 | L02 | 向量派发、DMA、总线 | 网络流控 |
| FIFO 与信用 | 解耦生产者与消费者的速率差 | L03 | 指令队列、DMA 描述符 | 生产者-消费者队列 |
| 流水线寄存器 | 用寄存器切分组合逻辑，提高吞吐 | L03 | 取指/译码/执行、MAC 阵列 | 工业流水线 |
| 旁路（bypass/forwarding） | 结果未写回就先给下游用 | L03 | 数据冒险、访存-执行 | 缓存一致性转发 |
| 记分板（scoreboard） | 追踪在途指令与寄存器依赖 | L03 | 乱序派发、访存依赖 | 数据库事务依赖跟踪 |
| 重排序缓冲（ROB） | 顺序提交、乱序完成 | L03 | 乱序退休、异常精确性 | 分布式系统的提交日志 |
| 地址解码 + 字节掩码 | 由地址低位决定操作哪几个字节 | L01–L02 | 访存、总线、外设寄存器 | 内存映射 I/O |
| 符号/零扩展与位宽截断 | 跨位宽传递数据时的两种约定 | L01 | 浮点、向量、DMA 打包 | 类型转换 |
| 广播 + 归约 | 一份数据发给多个计算单元，再合并结果 | L07 | 外积阵列、SIMD 归约 | MapReduce、集合通信 |
| 外积 / 脉动阵列 | 用二维数据复用替代寄存器堆访问 | L07 | 卷积、矩阵乘、注意力 | 谷歌 TPU 的 MXU 结构 |
| 双缓冲 / 预取 | 计算当前块时把下一块搬进来 | L08–L09 | DMA、缓存、流水化数据搬运 | 操作系统页预取 |
| 描述符链表 | 用内存里的链表描述一批任务 | L08 | DMA、加速器任务队列 | 网卡的 TX/RX ring |
| CSR / MMIO | 用寄存器地址空间做控制面 | L04 | 全部外设、调试模块 | 设备驱动模型 |
| 超时与看门狗 | 用时间上界把「卡死」变成可检测事件 | 检查器 | 总线、DMA、仿真平台 | 服务健康检查 |

# 第 5 章　标准与参考实现：普适性的锚点

判断一个知识是否「通用」，最实用的办法是问：**它有公开标准吗？有独立实现吗？**

| 领域 | 标准/规范 | 独立参考实现（用来交叉验证） |
| --- | --- | --- |
| 指令集 | RISC-V 非特权/特权规范 <https://riscv.org/technical/specifications/> | spike <https://github.com/riscv-software-src/riscv-isa-sim>、QEMU <https://www.qemu.org/>、riscv-tests |
| ABI 与汇编 | RISC-V psABI、汇编手册 <https://github.com/riscv-non-isa/riscv-asm-manual> | GNU 工具链（`as`/`objdump`） |
| 硬件描述语言 | IEEE 1800（SystemVerilog） | iverilog、Verilator <https://verilator.org/> |
| 片上总线 | AMBA AXI <https://developer.arm.com/documentation/ihi0022/latest/>、TileLink <https://github.com/chipsalliance/tilelink> | Chipyard、OpenTitan、上游 CoralNPU 自己的 TL-UL 实现 |
| 验证方法 | UVM、cocotb、riscv-dv | 上游 `tests/cocotb/`、`tests/uvm/` |
| 浮点 | IEEE 754 | Berkeley HardFloat、上游 `float/FloatCore.scala` |
| 加速器架构 | Sze 综述、数据流分类 | Eyeriss、Gemmini、NVDLA、上游 Zvt |

**读到这里的结论**：CoralNPU 在每一栏里都是「实现之一」。你的知识只有当你能把它
映射回左边那一列的**标准术语**、并用右边那一列的**独立实现**验证过，才算真正通用。

# 第 6 章　三角验证：怎么确信自己学的不是「仓库方言」

![三角验证](diagrams/verification_triangle.svg)

自己写的黄金模型 + 自己写的 RTL + 自己写的检查器，三者可能一起错——
这就是「共同失效模式」。三个角互相牵制才能降低这种风险：

1. **自有黄金模型**：语义清晰、可单步、可打印，但它的正确性依赖你的理解；
2. **标准工具链**：GNU `as`/`objdump` 是独立实现的编码器与解码器，
   课程的 `conformance` 检查就是用它来交叉验证我们的编码表与反汇编器（见第 6.2 节）；
3. **第三方参考实现**：spike、QEMU、上游 RTL、其他开源核，用来验证语义与系统行为。

## 6.1 三层交叉验证

| 层 | 验证什么 | 本课程怎么用 | 你可以自己做的 |
| --- | --- | --- | --- |
| 编码级 | 机器码与指令的对应关系 | `conformance.py` 对比 GNU as/objdump | 随便写一条指令，看汇编器编出来的码 |
| 语义级 | 执行结果（寄存器/内存） | 黄金模型 vs 你的 RTL trace 对拍 | 把同一个 ELF 放到 spike/QEMU 上跑，比最终内存 |
| 系统级 | 启动、总线、外设行为 | L04 之后引入，对照上游集成流程 | 用上游 cocotb 测试跑你的等价实现 |

## 6.2 一个真实的例子：为什么上游要自己做模拟器

CoralNPU 用 `mpause`（`0x08000073`）这条**自定义指令**来停机
（见 `hdl/chisel/src/coralnpu/scalar/Decode.scala:1188` 与 `toolchain/crt/coralnpu_start.S:144`）。
标准模拟器（spike、QEMU）不认识这条指令，会当成非法指令——
所以上游需要自己的模拟器（`third_party/coralnpu_mpact`、`sw/coralnpu_sim`）。

这个例子把「普适」与「专有」的边界讲得很清楚：

* **普适的部分**：RV32I 的绝大部分指令、ABI、地址约定、调试接口——换任何工具都能验证；
* **专有的部分**：自定义指令、私有 CSR、特定的内存映射——必须用配套工具，也必须写进文档。

工程上的建议也因此很具体：**尽量把设计建立在标准之上，把专有扩展隔离成小而清晰的一层**。

# 第 7 章　每课三问与迁移作业

## 7.1 三问

每节课结束后，用这三个问题检验自己：

1. **标准怎么定义？** 这个功能在 RISC-V 规范 / IEEE 标准 / AMBA 规范里叫什么？边界条件是什么？
2. **别人怎么做？** 至少找出两个不同的实现（另一个开源核、另一种总线、另一个加速器），
   说出它们的选择与代价。
3. **换场景怎么办？** 如果约束变了（更低功耗、更高频率、更大位宽、要支持虚拟化），
   我的设计哪一部分必须改、哪一部分可以保留？

## 7.2 迁移作业的三种形式

每节课的《作业说明.pdf》末尾都有迁移作业，形式固定为三种之一：

* **跨实现对照**：读另一个开源实现的同类模块，列出与你实现的 3 处差异并解释原因；
* **跨层验证**：把同一份程序/向量喂给独立实现（spike、QEMU、GNU 工具、上游 RTL），比较结果；
* **跨场景重构**：改变一个约束（位宽、流水级数、协议、数据流），说明你的设计要怎么改。

迁移作业不计入自动验收，但**它是这门课真正的产出**。

# 第 8 章　结课能力清单

学完十个阶段，你应该能**独立完成**下面这些事（每条都可以被第三方验证）：

1. 从零实现一颗 RV32I 核心，并说明它与标准的一致性边界；
2. 为自己的设计建立黄金模型与自动对拍流程，并解释共同失效模式的风险；
3. 把单周期改成流水线，识别并解决结构/数据/控制冒险；
4. 实现并验证乘除法、CSR、异常与中断；
5. 用 AXI 或 TileLink 把核心接入 SoC，完成启动、停机与状态上报；
6. 实现 IEEE-754 基本运算，解释舍入模式与异常标志；
7. 实现可变长向量（RVV）核心，并说明 stripmining 与掩码的语义；
8. 设计外积/脉动阵列，用复用分析解释它为什么比逐元素计算省带宽；
9. 设计总线从设备与 DMA，处理握手、背压、超时与错误上报；
10. 把一个量化后的模型落到硬件上，并用 roofline 分析指出瓶颈；
11. 设计一套包含定向、随机、形式与覆盖率的验证方案；
12. 用标准术语写出一份微架构文档，让别人能据此复现你的设计。

# 第 9 章　延伸路线

## 9.1 想往研究走

* 读 Sze 综述 <https://arxiv.org/abs/1703.09039>，再挑一条线深入：
  数据流与复用（Eyeriss）、可重构阵列（Gemmini）、稀疏与压缩、浮点与混合精度；
* 跟踪 ISCA / MICRO / HPCA / ASPLOS 的加速器与架构方向；
* 复现一篇论文的硬件结构，并用本课程学到的验证方法给出可信的对比数据。

## 9.2 想往工业界走

* **SoC 集成**：Chipyard <https://github.com/ucb-bar/chipyard>、OpenTitan <https://opentitan.org/>；
* **验证**：UVM、riscv-dv、形式验证（sby）、覆盖率驱动回归；
* **后端与物理实现**：综合、时序收敛、DFT、低功耗（本课程不涉及，但你需要知道边界在哪）；
* **编译与运行时**：MLIR <https://mlir.llvm.org/>、IREE <https://iree.dev/>、TVM <https://tvm.apache.org/>，
  它们决定「模型怎么变成你硬件上的指令」。

## 9.3 想做对比研究

把同一段算法在下列实现上跑一遍，比较面积/功耗/性能的取舍——
这是训练「体系判断力」最有效的方式：

* 小面积 MCU 核：PicoRV32 <https://github.com/YosysHQ/picorv32>
* 低功耗嵌入式核：Ibex <https://github.com/lowRISC/ibex>、CV32E40P <https://github.com/openhwgroup/cv32e40p>
* 应用级乱序核：CVA6 <https://github.com/openhwgroup/cva6>、BOOM <https://github.com/riscv-boom/riscv-boom>、
  XiangShan <https://github.com/OpenXiangShan/XiangShan>
* 领域加速器：Gemmini、NVDLA、Eyeriss

# 第 10 章　常见误区

| 误区 | 为什么错 | 正确做法 |
| --- | --- | --- |
| 把某个仓库的写法当原理 | CoralNPU 的 slot 式 LSU、CoralNPU 的外积结构都只是众多实现之一 | 先找标准与文献里的通用做法，再看这个仓库为什么这么选 |
| 只学工具不学规范 | 工具会过时，规范才是接口 | 每学一个功能，回到规范里找对应章节 |
| 只跑通不迁移 | 通过检查器可能只是「适配了这个检查器」 | 做迁移作业，用独立实现验证 |
| 一开始就追求性能 | 没有正确的功能，性能数字没有意义 | 先功能对拍，再谈流水线与面积 |
| 把仿真通过当成流片可用 | 仿真不含时序、功耗、可测性、跨时钟域 | 明确本课程的边界（见第 8 章之后的自查） |
| 迷信「自研」 | 自研的模型可能与你自己的误解同源 | 三角验证：自有模型 + 标准工具 + 第三方实现 |

## 本课程的边界（诚实的说明）

这门课**不覆盖**：物理设计（综合/布局布线/时序收敛/DFT）、模拟与混合信号、
低功耗设计方法学、形式化等价性验证、大规模 SoC 的性能建模工具链、
以及真正流片所需的工艺与 IP 集成工作。

这些是「知道存在、知道该找谁、知道怎么入门」就够用的部分；
本课程的目标是让你在**架构、微架构、RTL、验证**这条主线上达到能独立设计与自证的深度。

# 第 11 章　怎么用这一册

* 开始一门课前：看第 3 章对应行，明确「通用主题」与「外部对照对象」；
* 学完一门课后：做第 7 章的「三问」，并把新模式记进第 4 章的模式表；
* 卡住的时候：回到第 1 章找该支柱的权威来源，而不是只翻本仓库的实现；
* 全部学完后：用第 8 章的能力清单逐条打勾，缺哪条就回到对应阶段补。

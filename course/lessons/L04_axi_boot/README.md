# L04 · AXI 外壳与启动流程

**目标**：给 L03b 的核心套上一圈"系统外壳"，让它从"仿真里自己跑"变成
"被主机通过总线启动、数据访问走总线"的真实 SoC 部件：

1. **AXI4-Lite 从接口**（主机侧）：外部主机可以写 ITCM、读写三个控制寄存器；
2. **AXI4 主接口**（核心侧）：核心的每一次 load/store 都变成一笔 AXI 事务；
3. **启动控制**：`RESET_CONTROL` / `PC_START` / `STATUS`，按上游的 5 步流程启动核心。

## 前置

`./learn check L03b` 通过（L04 复用你的流水线核、LSU、M 扩展与 CSR）。

## 教材

* [`pdf/基础知识.pdf`](pdf/基础知识.pdf)：AXI 的五通道与握手规则、主/从接口怎么接、
  地址译码与响应码、时钟门控与同步复位、上游的 5 步启动流程、与 `CoreAxiCSR.scala` 的对照
* [`pdf/作业说明.pdf`](pdf/作业说明.pdf)：两个模块的接口契约、分步任务、调试方法与常见坑

上游对照（做完再看更像"对答案"）：[`doc/integration_guide.md`](../../../doc/integration_guide.md)、
[`hdl/chisel/src/coralnpu/CoreAxiCSR.scala`](../../../hdl/chisel/src/coralnpu/CoreAxiCSR.scala)

## 你的任务

改两个文件（核心、ITCM、测试平台由课程提供）：

| 文件 | TODO | 内容 |
| --- | --- | --- |
| [`rtl/axi_lite_slave.sv`](rtl/axi_lite_slave.sv) | 5 个 | 五条 AXI 通道的握手：AW/W 捕获、`o_wr_en` 脉冲与 B 响应、AR 保持、R 响应 |
| [`rtl/axi_boot_shell.sv`](rtl/axi_boot_shell.sv) | 6 个 | 地址译码、ITCM 例化、三个控制寄存器、启动控制、核心侧路由、AXI 主状态机 |

课程提供：`tests/tb_axi.sv`（主机 BFM + 系统存储器模型 + trace 采集）、
`tests/core_l04.sv`（= L03b 的核 + `o_fault` 输出 + `i_pc_start`）、
`tests/tcm.sv`（ITCM：一个主机写口 + 三个组合读口）。

## 验收

```bash
./learn check L04              # 期望 10/10（5 个程序 × 2 种总线延迟）
./learn check L04 --only 10    # 只看 5 步启动流程
./learn check L04 --ref        # 参考实现
./learn hint L04 3             # 卡住时的分级提示
```

判定标准是"黄金模型逐条对拍 + 启动流程断言"：trace 与 DTCM 要和 Python 黄金模型
完全一致，**并且**主机 5 步必须都走通（ITCM 写入、PC_START 读回、先释放门控再释放复位、
STATUS 观察到 HALTED/FAULT、未映射地址返回 SLVERR、`m_axi` 上真的有事务）。

## 学完之后你应该能回答

* AXI 的 VALID 和 READY 为什么必须"各管各的"？谁不能等谁？写错了会怎样？
* 主机写一个寄存器要经过哪几步握手？B 响应为什么不能用"一拍脉冲"？
* 上游 5 步启动流程里，为什么必须先释放时钟门控、再释放复位？
* 在这套外壳里，核心**取指**和核心**数据访问**走的路一样吗？为什么？
* `m_axi` 上的 SLVERR 说明什么？外壳怎么把它变成主机能看到的 `STATUS.FAULT`？

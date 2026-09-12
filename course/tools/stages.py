"""课程阶段注册表：CLI、进度、PDF 渲染都从这里取信息。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stage:
    code: str          # L01
    title: str         # 阶段标题
    directory: str     # learn/lessons/ 下的目录名
    summary: str       # 一句话说明学员要做什么
    anchors: list[str] = field(default_factory=list)  # 仓库里的对照实现/文档
    ready: bool = False  # 课程内容是否已经写好
    has_check: bool = True


STAGES: list[Stage] = [
    Stage(
        code="P0",
        title="预备课：零基础桥接",
        directory="P0_prep",
        summary="补齐读懂作业说明所需的前置：命令行、编译链接、数字逻辑、Verilog、RISC-V。可跳过。",
        anchors=[
            "course/lessons/P0_prep/basics.md",
            "course/lessons/P0_prep/rtl/majority.sv",
        ],
        ready=True,
    ),
    Stage(
        code="L00",
        title="环境、工具链与仓库地图",
        directory="L00_setup",
        summary="装好工具链，跑通「写 RTL → 仿真 → 对拍」闭环的最小例子。",
        anchors=[
            "README.md",
            "utils/coralnpu.dockerfile",
            "doc/integration_guide.md",
        ],
        ready=True,
    ),
    Stage(
        code="L01",
        title="RV32I 单周期核",
        directory="L01_scalar",
        summary="从零写出取指/译码/执行/写回，跑通汇编与真实 C 程序。",
        anchors=[
            "hdl/chisel/src/coralnpu/scalar/Decode.scala",
            "hdl/chisel/src/coralnpu/scalar/Alu.scala",
            "hdl/chisel/src/coralnpu/scalar/Regfile.scala",
            "doc/microarch/microarch.md",
        ],
        ready=True,
    ),
    Stage(
        code="L02",
        title="访存子系统（LSU 与槽表）",
        directory="L02_lsu",
        summary="实现字节/半字掩码、非对齐处理、以及上游那种「槽表」式访存状态机。",
        anchors=["doc/microarch/lsu.md", "hdl/chisel/src/coralnpu/scalar/Lsu.scala"],
    ),
    Stage(
        code="L03",
        title="流水线、冒险、M 扩展、CSR 与异常",
        directory="L03_pipeline",
        summary="把单周期改成 4 级流水，加记分板、退休缓冲、乘除法器和 Zicsr。",
        anchors=[
            "doc/microarch/dispatch.md",
            "doc/microarch/mlu.md",
            "hdl/chisel/src/coralnpu/RetirementBuffer.scala",
            "hdl/chisel/src/coralnpu/scalar/FaultManager.scala",
        ],
    ),
    Stage(
        code="L04",
        title="AXI 外壳与启动流程",
        directory="L04_axi_boot",
        summary="给核心加上 AXI 从/主接口、RESET/PC_START/STATUS CSR，按上游 5 步启动流程跑自己的程序。",
        anchors=["doc/integration_guide.md", "hdl/chisel/src/coralnpu/CoreAxiCSR.scala"],
    ),
    Stage(
        code="L05",
        title="浮点单元（F 扩展）",
        directory="L05_float",
        summary="实现 fregfile、fcsr 与加法乘法，跑通上游的 hello_world_add_floats。",
        anchors=["examples/hello_world_add_floats.cc", "hdl/chisel/src/coralnpu/float/FloatCore.scala"],
    ),
    Stage(
        code="L06",
        title="向量核（RVV / Zve32x）",
        directory="L06_vector",
        summary="实现 vtype/vl、stripmining、掩码与 vstart、向量访存、vadd/vwmul。",
        anchors=[
            "examples/rvv_add_intrinsic.cc",
            "hdl/chisel/src/coralnpu/rvv/RvvCore.scala",
            "hdl/verilog/rvv/design/rvv_backend.sv",
        ],
    ),
    Stage(
        code="L07",
        title="矩阵引擎（Zvt / VME）",
        directory="L07_matrix",
        summary="实现 8x8 累加器、外积 MAC、vtmmu/vtmms/vtfmm 与 mset*/vtmv 指令。",
        anchors=[
            "tests/cocotb/vme_test/vme_matmul_test_program.cc",
            "hdl/verilog/rvv/design/Zvt/zvt_pe_array.sv",
        ],
    ),
    Stage(
        code="L08",
        title="总线、外设与 DMA",
        directory="L08_soc",
        summary="实现 TileLink-UL 交叉开关、GPIO/SPI 等外设，以及描述符链表 DMA。",
        anchors=["doc/peripherals/dma.md", "doc/sw/dma.md", "hdl/chisel/src/bus/DmaEngine.scala"],
    ),
    Stage(
        code="L09",
        title="软件栈与端到端模型",
        directory="L09_software",
        summary="链接脚本、启动代码、HTIF 半主机、RVV intrinsic 与 TFLite Micro 集成。",
        anchors=[
            "doc/tutorials/npusim_mobilenet_tutorial.md",
            "toolchain/coralnpu_tcm.ld.tpl",
            "sw/opt/litert-micro",
        ],
    ),
    Stage(
        code="L10",
        title="验证方法学与毕业项目",
        directory="L10_verification",
        summary="cocotb/Verilator 回归、随机指令流、与参考模型对拍，最后跑通自选模型。",
        anchors=["tests/cocotb/README.md", "tests/uvm/README.md", "fpga/README.md"],
    ),
]


def by_code(code: str) -> Stage | None:
    code = code.upper()
    for stage in STAGES:
        if stage.code == code:
            return stage
    return None


def all_codes() -> list[str]:
    return [s.code for s in STAGES]

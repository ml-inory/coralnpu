# 已撤回的材料

这里存放 2026-09-12 那次「体系化 / 普适性」改造中被撤回的内容，不属于课程主线，
`./learn` 与 PDF 渲染都不会碰它们。保留只是为了以后想用时不必重写。

* `KNOWLEDGE_MAP.md`：课程总纲式的知识地图（五根支柱、十个阶段矩阵、设计模式库、
  标准清单、三角验证、延伸路线）。
* `conformance.py`：用 GNU as / objdump 交叉验证课程编码表的脚本（L01 用）。
  它当时是跑通的：46/46 条指令编码与助记符一致。

要恢复某一项，把它移回原来的位置即可：

| 文件 | 原位置 |
| --- | --- |
| `KNOWLEDGE_MAP.md` | `course/KNOWLEDGE_MAP.md` |
| `conformance.py` | `course/lessons/L01_scalar/tests/conformance.py` |

当时对课程 Markdown 的改动（每课新增「第 0 章 普适坐标」与「第 8 章 迁移」）已从
`basics.md` / `homework.md` 中移除，正文可在 git 历史之外的本对话记录里找回。

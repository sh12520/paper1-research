---
name: paper1-navigate
description: Navigate the Paper 1 repository when resuming a research direction, tracing a claim to evidence, finding related work, or reviewing cross-machine handoffs. Use for RDINP, CS-ODS, and OPV2V research assets in this repository.
---

# 论文 1 研究导航

从仓库根的 [AGENTS.md](../../../AGENTS.md) 找入口。读 [全局当前推进](../../../docs/current-research.md) 核对当前项目优先级和下一验证条件。目标是某条独立方向时，直接读 [方向目录](../../../research/README.md) 及该方向的 CURRENT 和 EVIDENCE，保留该方向的适用边界。

- 验证已有判断时，从 [证据索引](../../../docs/evidence-index.md) 定位报告，记录指标、分母和条件，按任务 ID、帧键或实例 ID 下钻到一条源记录。区分真实计算计时、链路模型、受控故障和独立确认，明确比较是否执行。
- 找失败或前置经验时，先查 [历史经验](../../../docs/research-lessons.md)，再到 [共享文献目录](../../../literature/README.md) 核对稳定引文。引用技术结论时定位原文表、节或固定代码版本。
- 稀疏工作树缺文件时，用 `git show HEAD:仓库内路径` 读取已跟踪原件。需要一组文件时，按 [全局索引](../../../docs/research-index.md) 补取具体目录。用提交和摘要区分共享原件、本机专有依赖和真正缺失的产物。
- 需要运行共享核验或使用 autoresearch 流程时，从 [研究工具入口](../../../research/README.md) 选任务。读到历史回执或服务模板时，先分辨已封存、当前受阻与实际授权可执行的状态。

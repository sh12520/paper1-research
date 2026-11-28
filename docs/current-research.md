# 当前推进

2026-11-28 作者已将 GOAL-1 转向 **动态无线与边缘算力下的结构化限时意图协商和快慢环履约**。第一步完成 810 组四方法配对与同菜单机制归因。带本地兜底的三组均按期交付。修正复算后，快切相对同菜单下的固定档提高了平均效用，紧截止期条件下更明显。协议原型接入待作者审阅。[复算与归因报告](../rdinp/experiments/structured-fast-slow/STEP1_REVIEW.md) · [现行 GOAL](proposals/GOAL.md) · [专家审阅提示词](EXTERNAL_RESEARCH_EXPERT_PROMPT.md)

## 本阶段的复用入口

- 网络侧按 [5G-LENA 前传容量事件](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/native_replay/OptimizeRBs/capacity-events.csv)重放容量变化。无线突发丢包和抖动另行建模并标明参数。
- 任务侧复用[图像工作负载](../rdinp/experiments/service-worker/image_workload.py)、基准槽位校准和原配对口径。按主边缘、轻边缘和本地档分别记录计算时长、有效载荷、质量及证据来源。
- 协议侧复用 [RDINP 消息 Schema](../rdinp/protocol/c2/message.schema.json)、[约束 Schema](../rdinp/protocol/c2/contracts.schema.json)和[四阶段语义](../rdinp/protocol/c2/CONTRACT.md)作为控制成本与状态约束的依据。第一阶段用事件执行，第二阶段接新多档条款。

## 已冻结的历史诊断

原 G1-A 的 144 个配对及其判定、公开回退点条件论证和全部轨迹证据均可复核。单机取消、SQLite 释槽和 Caddy 排空支线按作者决定封存。其旧专家建议与开题评审版用于追溯此前决策。 [原 G1-A 判定](../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md) · [开题审阅入口](proposals/README.md)

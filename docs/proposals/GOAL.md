# RDINP 研究目标与阶段门禁

2026-11-28 作者决定将小论文（GOAL-1）的技术切入点调整为 **《面向动态无线与边缘算力的结构化限时意图协商与快慢环履约机制》**。

## GOAL-1　结构化多档意图与快慢环履约

研究多终端共享波动无线链路和有限边缘槽位时，预先约定主档、轻量边缘档和本地回退的执行条件，能否在硬截止期内提高实际交付并降低重协商开销。慢环依据因果可观测的链路和队列信息准入并承诺条款。快环依据已约定条件降级或回退，由任务身份和唯一代际约束结果采用。

1. **先做 Python 离散事件对照。** 使用 5G-LENA 前传容量事件、单独设置的无线突发丢包／抖动和边缘多槽队列。在共同任务、链路与资源输入上比较 Fixed-Intent、Reactive Re-Negotiation、Static Local Fallback 和 Structured Fast-Slow RDINP。前传容量事件作为前传预算使用。原始测量与开发模型参数分开标注。
2. **交付首批趋势供作者确认。** 扫描链路扰动、并发负载和截止紧迫度。以全部释放任务为分母，报告按期完成与各档占比、有效效用、期限违约、控制字节、协商轮次及其耗时。反应式方案使用相同可执行档位，协议时延与控制流量按共用链路记账。
3. **Step 2 原型与实测门禁。** 作者已授权连续推进。独立版本实现会话租期、多档许可、即时准入和跨代际去重。在固定 400 ms 配对任务上，平均净效用差 +0.0040，六项安全验收通过，进入 Step 3。[原型规范](../../rdinp/protocol/permit-v1/README.md) · [原型实测](../../rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/RESULTS.md)
4. **Step 3 中文初稿与复现。** 论文分开陈述仿真和真实协议实测。主要实测效应的探索性配对区间跨零，保留失期样本和分工况结果。[中文初稿](../../rdinp/experiments/permit-prototype/paper/RDINP_中文小论文初稿.md) · [复现入口](../../rdinp/experiments/permit-prototype/README.md)

5. **16 种子补测与定稿。** 完成三种固定链路和三种同许可策略的配对。动态降容的效用差区间为正，持续降半仍跨零，未达到两条受扰链路均获益的判据。定稿聚焦控制成本、条件切档和回退边界，并保留两轮试验原始结果。[补测报告](../../rdinp/experiments/permit-prototype/evidence/step2-expansion-20261128-r01/RESULTS.md)

## 已冻结的原 G1-A 支线

原固定公开回退点的单机取消诊断保留历史原判 `INCONCLUSIVE_REQUIRES_MANUAL_REVIEW`、原判定规则和封存记录。作者已结束该支线的后续验证。私有提前放弃与 HTTP CANCEL、SQLite 释槽尾段及 Caddy 在途排空留作历史边界材料。原目标文本可在 `b560fa20` 查看。 [原 G1-A 判定](../../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md) · [原证据包说明](../../rdinp/experiments/durable-worker/evidence/g1a-20261128/README.md)

## GOAL-2　硕士论文扩展

GOAL-1 形成可投稿初稿及复现实验包后，由作者确认扩展。将多档条款、快慢环机制和配对证据整合进硕士论文，再评估独立端点、时钟误差和业务载荷。频谱资源先落实为协议接口与约束表达，动态发现按实际条件扩展。

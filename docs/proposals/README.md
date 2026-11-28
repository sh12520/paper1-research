# RDINP 开题与研究目标审阅

硕士论文题目为《面向6G智能体网络的限时意图协商与服务履约保障机制研究》。对外审阅从[最新专家提示词](../EXTERNAL_RESEARCH_EXPERT_PROMPT.md)进入。小论文的现行范围与证据如下。

| 顺序 | 材料 | 审阅重点 |
| --- | --- | --- |
| 1 | [研究目标](GOAL.md) | 动态无线与边缘算力下的结构化限时协商与快慢环履约 |
| 2 | [中文小论文初稿](../../rdinp/experiments/permit-prototype/paper/RDINP_中文小论文初稿.md) | 当前论文主张、图表与证据边界 |
| 3 | [Step 2 配对实测](../../rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/RESULTS.md) | 真实协议成本、400 ms 配对效用、探索区间和安全测试 |
| 4 | [Step 1 修正复算与归因](../../rdinp/experiments/structured-fast-slow/STEP1_REVIEW.md) | 配对仿真、紧截止期下的效用差值与同菜单对照 |
| 5 | [硕士开题报告评审版](RDINP_硕士学位论文开题报告_评审版.md) | 既有题目、研究基础与待按新主线修改的实验计划 |

从[原型复现入口](../../rdinp/experiments/permit-prototype/README.md)核对实测口径和运行步骤。冻结 ZIP 在 Git 快照之外，快照已跟踪构建所需的源码、证据、初稿与图表。仿真原始输出只收录 [Step 1 r02 五份封存输入](../../rdinp/experiments/structured-fast-slow/runs/step1-20261128-r02/COMPLETE.json)，后续临时运行仍遵循 Git 忽略规则。从仓库根可生成一份新的 ZIP，不启动实验。

~~~bash
python -B rdinp/experiments/permit-prototype/freeze_bundle.py --paper rdinp/experiments/permit-prototype/paper --out RDINP_GOAL1_REPRO_20261128.zip
python -B rdinp/experiments/permit-prototype/freeze_bundle.py --verify RDINP_GOAL1_REPRO_20261128.zip
~~~

已从干净的 Git 导出重建并校验 206 个文件，复算 Step 2 门禁与封存结果逐字节一致。部分历史文本在 Git 中统一了换行，因此原交付 ZIP 和重建 ZIP 的整体摘要可能不同。

Step 1 阶段的预算可从[四阶段控制预算](../../rdinp/experiments/structured-fast-slow/STEP1_CONTROL_BUDGET.md)追溯。

原 G1-A 单机取消诊断已封存。可查[判定报告](../../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md)、[冻结判定协议](../../rdinp/experiments/durable-worker/G1A_DECISION_PROTOCOL.md)、[公开回退点的条件论证](../../rdinp/experiments/durable-worker/PUBLIC_FALLBACK_INFORMATION_LEMMA.md)及[历史任务表](../../rdinp/experiments/durable-worker/evidence/g1a-20261128/README.md)。旧专家提示词可从 `b560fa20` 追溯。

开题评审版及[初稿](RDINP_硕士学位论文开题报告_初稿.md)保留供本轮审阅。实验状态与证据另见[当前推进](../current-research.md)和[关键证据索引](../evidence-index.md)。

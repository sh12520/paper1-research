# G1-A 配对判定证据

2026-11-28 固定配对。范围、结果解释和人工门禁见 [判定报告](../../G1A_DECISION_REPORT.md)。

| 核对项 | 文件 |
| --- | --- |
| 配对效应、区间和 B2-ideal 模型 | [机器判定](g1a-decision.json) |
| 逐阶段的逾期与有效 C2 授权 | [诊断](g1a-diagnostic.json) |
| 计划和全部计分任务 | [4 终端／1 槽](study-4x1/) · [8 终端／2 槽](study-8x2-retry-01/) |
| 源码摘要、依赖、运行恢复及逐对摘要 | [执行核验](g1a-execution-verification-v2.json) · [启动快照清单](launch-snapshot.sha256) · [分析快照清单](analysis-reviewed-v2.sha256) · [Python 依赖](dependencies-start.txt) |
| 复核完整事件链所需的原生证据 | [原始证据包 SHA-256](g1a-evidence-v1.tar.gz.sha256) |

每档 72 个配对。两份逐任务表分别有 2,592 条记录。表中绝对单调时间仅在所属运行时钟域内解释。两份计划及逐任务表按执行核验中的摘要保留。机器判定仅将运行目录缩为相对名称，原始 JSON 摘要记录在导出来源字段。

完整事件链、原生 C2 日志及失败校准记录位于本地和远端实验环境的 `g1a-evidence-v1.tar.gz`。本机在本实验目录的 `runs/g1a-decision-01/`，按上表 SHA-256 核对。逐任务表可核对分母与结果，端到端日志审计需使用该证据包。

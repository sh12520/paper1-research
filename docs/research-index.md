# 全局研究目录与时间线

更新于 2026 年 11 月 27 日。日常以 [当前推进](current-research.md) 为起点。下表用于定位资料和追溯旧结果。

| 位置 | 放什么 | 何时打开 |
| --- | --- | --- |
| [`AGENTS.md`](../AGENTS.md) | 面向协作 Agent 的入口与取证方法 | 新会话或交接 |
| [`docs/`](./) | 状态、[证据索引](evidence-index.md)、[历史经验](research-lessons.md)及[研究关系](research-map.md) | 确定工作范围和资料链 |
| [`rdinp/`](../rdinp/) | C2 协议、JSON Schema、可运行实现、worker 与代理复现实验 | 运行协议或执行层检查 |
| [`csods/`](../csods/) | 有限 DSL 合同搜索、方法说明、小型测试 | 审查搜索或复用正确性测试 |
| [`archive/genspace/`](../archive/genspace/) | CS-ODS、XR 基线、RDINP 近期研究与原始开发记录 | 查原论文、技术报告或逐例输出 |
| [`archive/rdinp-history/`](../archive/rdinp-history/) | RDINP 老版本交付和证据边界 | 比较协议版本、复核早期结论 |
| [`archive/v2x-development/`](../archive/v2x-development/) | OPV2V 回放、通信与计算测量、共享计算诊断 | 追溯车路协同数据和缺失证据 |
| [`archive/reorch/`](../archive/reorch/) | 运行期分组对照、脚本和结论 | 审查动态重分组为何未超过强静态基线 |
| [`archive/DIRECTORY_INDEX.tsv`](../archive/DIRECTORY_INDEX.tsv) | 可筛选的归档子目录、文件数、字节数 | 缩小到相关实验目录 |
| [`tools/`](../tools/research_archive_index.py) | 从原归档清单复核或重建目录索引 | 归档有增量时 |
| [`archive/MANIFEST.tsv`](../archive/MANIFEST.tsv) | 18,790 个原始归档路径及 SHA-256 | 核对具体文件或对象来源 |

四个归档方向合计约 668 MiB。PILOT、DG-PCE V1 和论文开发比较三批结果共 16,065 份。体量和历史引用限制见[归档说明](../archive/README.md)。

## 时间线

| 时间或阶段 | 决策与主要材料 |
| --- | --- |
| 2026-09-24 至 10-28 | RDINP 保留[双向丢包重试勘误](../archive/rdinp-history/august/rdinp-v04-bidirectional-retry-erratum-v1-20260924.md)、[10 月 23 日本地评估](../archive/rdinp-history/august/rdinp-d5-local-evaluation-20261023/2026-10-23--rdinp-d5--r01--evaluation-report.md)、[10 月 26 日导师交付](../archive/rdinp-history/october/rdinp-advisor-final-delivery-20261026-r01/deliverables/RDINP_提交老师_20261026/01_成果交付说明.md)和[10 月 28 日证据边界](../archive/rdinp-history/august/rdinp-claims-and-paper-feasibility-20261028-r01/DECISION-REPORT-ZH.md)。 |
| 2026-11-18 | [SMOKE-02](../archive/genspace/SMOKE_REPORT.md)完成 192 个工程检查实例，[PILOT-01](../archive/genspace/PILOT_REPORT.md)完成 1,920 个探索性实例。 |
| CS-ODS 方法开发与冻结准备 | [DG-PCE V1 未超过 FLAT](../archive/genspace/FLAT_BASELINE_AUDIT_REPORT.md)。无图语法搜索经历[原始扩展失败](../archive/genspace/ON_DEMAND_GRAMMAR_GATE_REPORT.md)和[规范化去重后通过开发门禁](../archive/genspace/GRAMMAR_FINAL_ROUTE_DECISION.md)。保留 [Depth 3 原判与短域解释](../archive/genspace/DEPTH3_GATE_INTERPRETATION.md)。[11 月 19 日审批文件](../archive/genspace/METHOD_FINAL_APPROVAL_PACKET.md)为 `APPROVAL_PENDING`。 |
| CS-ODS 第三轮审阅 | 形成[导师审阅稿](../archive/genspace/PAPER1_ROUND3/PAPER1_ROUND3_REVISED.docx)和[修订历史](../archive/genspace/PAPER1_ROUND3/ROUND3_REVISION_HISTORY.md)。 |
| 2026-11-23 | [XR 前传基线重审](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/PAPER1_PROBLEM_BASELINE_RESET.md)保留 `RESEARCH_DIRECTION_NOT_YET_JUSTIFIED`。 |
| 2026-11-24 至 11-27 | [协同感知问题审查](../archive/genspace/AGENT_COMMUNICATION_PROBLEM_REVIEW.md)保留 `PROBLEM_GAP_UNPROVEN`。OPV2V 资源敏感性有开发回放，共享计算诊断仍缺真实并发轨迹。 [OPV2V 档案](../archive/v2x-development/README.md) |
| 2026-11-27 | 形成[当前 RDINP 拟题](current-research.md)。本地开发验证推进到实际 Caddy 代理控制。 |

REORCH 是并行的历史路线。其归档报告保留 [`REORCH_GAP_WEAK`](../archive/reorch/GATE_REPORT.md)，此处按主题保留。

## 按需检出

新机器可先检出源码和导航。

```bash
git clone --filter=blob:none --sparse git@github.com:sh12520/paper1-research.git
cd paper1-research
git sparse-checkout set docs rdinp csods
```

从索引选中目录后，可用 `git sparse-checkout add archive/genspace/PAPER1_TOPIC_APPROVAL_20261127` 补取当前档案。只读一份文件时可运行 `git show HEAD:archive/genspace/PILOT_REPORT.md`。完整备份可使用普通克隆，或运行 `git sparse-checkout disable`。

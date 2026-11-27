# 论文 1 研究索引

更新于 2026 年 11 月 27 日。此页按使用优先级组织，并列出研究决策的时间线。归档文件保留原有路径，便于追溯实验 ID、正文引用和文件摘要。

## A｜当前推进与导师沟通

| 顺序 | 材料 | 用途与证据边界 |
| --- | --- | --- |
| 1 | [11 月 27 日选题与实验方案](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/论文1选题与实验方案_导师审阅.md) | 当前拟议选题。聚焦提交回执丢失后，边缘资源状态不明时的限时履约与本地回退。 |
| 2 | [首轮实验与复现记录](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/首轮实验与复现记录.md) · [RDINP 本地运行入口](../rdinp/README.md) | 核对逻辑提交和任务执行的关系。RDINP 目录提供可运行源码和小型测试。 |
| 3 | [实际代理执行对照与下一步证据](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/业务代理执行对照与下一步证据.md) | 近期诊断使用本机 Caddy 和真实 HTTP 后端。常规版本控制与时限守卫已覆盖部分故障，真实业务 SLA、故障轨迹与公平强对照仍待取得。 |

沟通当前选题时从第 1 项开始。复核方法与数据时从第 2、3 项进入相应记录。

## B｜关键证据与路线决策

| 方向 | 优先阅读 | 保存价值 |
| --- | --- | --- |
| RDINP 协议 | [C2 协议](../rdinp/protocol/c2/CONTRACT.md) · [复现命令](../rdinp/docs/REPRODUCE.md) · [适用边界](../rdinp/docs/SCOPE.md) | 规范、实现及本机复现。协议提交、执行资格、产出结果、及时采用分别核对。 |
| CS-ODS 论文 | [第三轮 Word](../archive/genspace/PAPER1_ROUND3/PAPER1_ROUND3_REVISED.docx) · [PDF](../archive/genspace/PAPER1_ROUND3/PAPER1_ROUND3_REVISED.pdf) · [审稿回应](../archive/genspace/PAPER1_ROUND3/REVIEW_RESPONSE_MATRIX.md) · [运行入口](../csods/README.md) | 旧路线的导师审阅版本和可运行导出。已完成开发比较，独立确认未执行。 |
| CS-ODS 结论依据 | [PILOT 报告](../archive/genspace/PILOT_REPORT.md) · [强基线与消融](../archive/genspace/PAPER_DEVELOPMENT_COMPARISON.md) · [Depth 3 独立复核](../archive/genspace/DEPTH3_INDEPENDENT_PROOF_AUDIT.md) | 分别核对开发数据、方法比较和正确性证据。 |
| XR 前传 | [问题与基线重审](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/PAPER1_PROBLEM_BASELINE_RESET.md) · [TFH 历史证据](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/TFH_ARCHIVED_EVIDENCE.md) | 保留基线表现及为何缺乏继续设计双边协商方法的证据。 |
| 车路协同感知 | [文献与问题审查](../archive/genspace/AGENT_COMMUNICATION_PROBLEM_REVIEW.md) · [OPV2V 资源敏感性](../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/result_summary.md) · [共享计算诊断](../archive/v2x-development/queue-diagnostic/QUEUE_DIAGNOSTIC_REPORT.md) | 区分已有设备计时、链路模型回放和缺失的并发任务证据。 |
| 运行期重新分组 | [REORCH 判定](../archive/reorch/GATE_REPORT.md) | `REORCH_GAP_WEAK`。动态分组未达到预设稳定优势，供后续排除重复方向。 |

### 研究时间线

按报告日期或已知阶段先后排列。仅给原件能支持的日期。

| 时间或阶段 | 研究进展与当时结论 |
| --- | --- |
| 2026-09-24 至 10-28 | 保留 [RDINP 双向丢包重试勘误](../archive/rdinp-history/august/rdinp-v04-bidirectional-retry-erratum-v1-20260924.md)、[10 月 23 日本地评估](../archive/rdinp-history/august/rdinp-d5-local-evaluation-20261023/2026-10-23--rdinp-d5--r01--evaluation-report.md) 和 [10 月 26 日导师交付说明](../archive/rdinp-history/october/rdinp-advisor-final-delivery-20261026-r01/deliverables/RDINP_提交老师_20261026/01_成果交付说明.md)，以及 [10 月 28 日证据边界与路线决定](../archive/rdinp-history/august/rdinp-claims-and-paper-feasibility-20261028-r01/DECISION-REPORT-ZH.md)。 |
| CS-ODS 开发阶段，至 2026-11-19 | [SMOKE-02 工程检查](../archive/genspace/SMOKE_REPORT.md)完成后，运行 1,920 个探索性 PILOT 实例。[DG-PCE V1 未超过 FLAT](../archive/genspace/FLAT_BASELINE_AUDIT_REPORT.md)，进一步定位了全扫描瓶颈。无图语法搜索经历[原始扩展失败](../archive/genspace/ON_DEMAND_GRAMMAR_GATE_REPORT.md)和[规范化去重后通过开发门禁](../archive/genspace/GRAMMAR_FINAL_ROUTE_DECISION.md)。Depth 3 保留[原始判定 `DEPTH3_PARTIAL` 及短域解释](../archive/genspace/DEPTH3_GATE_INTERPRETATION.md)。11 月 19 日的[批准文件](../archive/genspace/METHOD_FINAL_APPROVAL_PACKET.md)记为 `APPROVAL_PENDING`。 |
| CS-ODS 第三轮审阅 | [修订历史](../archive/genspace/PAPER1_ROUND3/ROUND3_REVISION_HISTORY.md)记录文献、证明成本、合同案例和主张调整。稿件保留独立确认未运行的边界。 |
| 2026-11-23 | XR 场景重审保留 `RESEARCH_DIRECTION_NOT_YET_JUSTIFIED`。 |
| 2026-11-24 至 11-27 | 协同感知文献审查结论为 `PROBLEM_GAP_UNPROVEN`。11 月 26 日归档的 OPV2V 开发回放显示时限对通信和计算均敏感。共享计算诊断缺少可核验的并发负载，保留 `BLOCKED_MISSING_CONCURRENT_WORKLOAD`。 |
| 2026-11-27 | 形成 RDINP 限时协商与服务履约拟题。开发验证依次覆盖单任务、顺序任务与重启、[旧写者与过期](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_03/执行点保护与场景证据_诊断报告.md)、实际软件代理控制。 |

## C｜完整备份与复核

实际上传了 **18,790 份**历史文件。18,782 是加入两份 OPV2V 资料前的中间盘点，两份资料增加了 8 个文件。下表按原归档清单统计。

| 档案 | 文件数 | 原始大小 |
| --- | ---: | ---: |
| [GENSPACE](../archive/genspace/) | 18,737 | 589.21 MiB |
| [REORCH](../archive/reorch/) | 23 | 71.62 MiB |
| [OPV2V 开发诊断](../archive/v2x-development/) | 8 | 6.19 MiB |
| [RDINP 历史](../archive/rdinp-history/) | 22 | 0.80 MiB |
| [归档合计](../archive/MANIFEST.tsv) | 18,790 | 667.83 MiB |

- 大部分条目是逐实例或逐运行记录。PILOT、DG-PCE V1 和论文开发比较三个结果目录共 **16,065 份，占 85.5%**。日常用汇总报告，核对数值时再追溯逐例数据。
- 归档含 **16,610 个不同的 SHA-256**。同内容副本保留各自的历史路径，便于追溯不同运行和稿件引用。Git 会让相同内容共享对象，本机初始导入的 Git pack 约 46 MiB。
- 最大单文件是 [REORCH 原始结果表](../archive/reorch/results/raw_results.csv)，约 71.53 MiB。快速审阅可从判定报告进入。
- 逐文件字节数和摘要见 [MANIFEST.tsv](../archive/MANIFEST.tsv)。旧文档仍可能引用原机或未随归档复制的中间文件。目录用途与未入库材料见 [归档说明](../archive/README.md)。

### 协作检出

只需当前代码与导航时，可用已配置访问权限的 GitHub SSH 身份在新机器执行。

```bash
git clone --filter=blob:none --sparse git@github.com:sh12520/paper1-research.git
cd paper1-research
git sparse-checkout set docs rdinp csods
```

需要当前 RDINP 研究档案时，可运行 `git sparse-checkout add archive/genspace/PAPER1_TOPIC_APPROVAL_20261127`。完整归档可用普通克隆，或在精简检出中运行 `git sparse-checkout disable`。

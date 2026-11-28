# 关键证据与原始记录

按结论找报告，按报告找表，再按任务或实例 ID 定位原始记录。下表定位仓库内可查证据和已移交本地的原始明细。历史材料中保留了当时的文件路径。

## RDINP 主线

Step 2 的会话许可实测、五类问题及门禁见 [原型实测报告](../rdinp/experiments/permit-prototype/evidence/step2-20261128-r01/RESULTS.md)。四组仿真对照、修正复算和快切归因见 [Step 1 复核报告](../rdinp/experiments/structured-fast-slow/STEP1_REVIEW.md)。下表供核对开题中的前期数据与已封存的原型和诊断。

| 要核查的结论 | 成立范围及状态 | 从报告到记录 |
| --- | --- | --- |
| **RDINP G1-A**，共享槽位假设证据不足 | 144 个同机配对。存在分向应用故障和回退，准入 BUSY 为零。原判定保留，支线已按作者决定封存。 | [判定报告](../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md) → [配对计划、任务表和机器判定](../rdinp/experiments/durable-worker/evidence/g1a-20261128/README.md) |
| **RDINP C2**，终端 `UNKNOWN` 可以对应不同的远端提交与配额状态 | 本地受控故障和逻辑账本。资源单位为逻辑配额。 | [首轮复现记录](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/首轮实验与复现记录.md) → [协议的承诺与知识状态](../rdinp/protocol/c2/CONTRACT.md) → [复现步骤](../rdinp/docs/REPRODUCE.md) |
| **RDINP DEV01–03**，本机 worker、持久恢复、过期和旧代际保护 | 受控 CPU、SQLite 和进程故障。余量参数来自试验条件。 | [单任务逐案表](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_01/run_20261127-125536/per_case.csv) · [顺序任务逐任务表](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_02/run_20261127-130601/per_task.csv) · [执行点报告](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_03/执行点保护与场景证据_诊断报告.md) → [逐案写入结果](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_03/effect_20261127-134638/summary.json) |
| **RDINP DEV04**，管理确认、新路由读回、在途旧请求各有可观察时间 | 真实 Caddy 和 HTTP 后端，使用本机受控故障。 | [代理对照报告](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/业务代理执行对照与下一步证据.md) → [原生条件更新](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/native_proxy_20261127-135819/summary.json) · [转发延迟](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/summary.json) · [在途请求](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/inflight_agent_01/summary.json) → [发送端检查个案](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/sender_check_only/result.json) · [执行点守卫个案](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/actuator_gate/result.json) |

## 可复用的工程证据

需要边缘业务候选或单边工程对照时，查 OPV2V 的处理流程、数据范围和缺失的并发证据。

| 要核查的结论 | 成立范围及状态 | 从报告到记录 |
| --- | --- | --- |
| **OPV2V R1–R2.6**，需求反馈与时限工程优化 | 需求反馈策略 C 在已测设置低于普通补包 B。预筛、流水线、去重可作为单边工程对照。GPU 服务计时与模型链路分别记账。 | [方向证据与原件](../research/opv2v-deadline/EVIDENCE.md) |
| **OPV2V**，通信与计算时限敏感性 | 80 个开发帧，结合历史 CUDA 计时和模型链路。 | [资源回放报告](../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/result_summary.md) → [逐条件汇总](../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity-summary.csv) → [逐帧表](../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity-frames.csv)，按 `frame_key` 和 `scenario` 对齐 |
| **OPV2V**，并发算力争用诊断受阻 | 缺可核验的独立任务释放与共享执行记录。SHARED、ISOLATED、EDF 对照未执行。 | [队列诊断](../archive/v2x-development/queue-diagnostic/QUEUE_DIAGNOSTIC_REPORT.md) → [历史与配对状态](../archive/v2x-development/queue-diagnostic/PAIRED_TASK_RESULTS.csv) · [时间线](../archive/v2x-development/queue-diagnostic/REPRESENTATIVE_TIMELINE.md) |

## 历史路线与负结果

涉及结构合同、前传或动态分组的先例时，按原判定与适用范围核对。

| 要核查的结论 | 成立范围及状态 | 从报告到记录 |
| --- | --- | --- |
| **GENSPACE PILOT**，结构合同空间的存在性差异 | 1,920 个探索性实例，用于分布和机制诊断。 | [PILOT 报告](../archive/genspace/PILOT_REPORT.md) → [按 family 汇总](../archive/genspace/results/pilot/family_summary.csv) → [本地逐实例方法输出](../archive/README.md#本地原始结果)，原路径为 `archive/genspace/results/pilot/raw_results.csv`，按 `instance_id` 和 `method` 对齐 |
| **CS-ODS**，与同域通用 best-first 的搜索比较 | 开发集。共同获证子集的时延只能作条件比较。 | [第三轮稿件](../archive/genspace/PAPER1_ROUND3/PAPER1_ROUND3_REVISED.md) · [方法开发比较](../archive/genspace/PAPER_DEVELOPMENT_COMPARISON.md) → [比较汇总](../archive/genspace/results/paper_method_dev/comparison_summary.csv) · [消融汇总](../archive/genspace/results/paper_method_dev/ablation_summary.csv) → [逐查询表](../archive/genspace/results/paper_method_dev/per_query.csv)，按 `instance_id`、`effective_depth`、`method` 和 `k` 对齐。稿件中的时延比另见 [共同获证配对表](../archive/genspace/PAPER1_ROUND3/Supplementary_Materials/S2_paired_k500_comparisons.csv) |
| **Depth 3**，精确前缀、短域穷尽和独立覆盖证明 | 原始 `DEPTH3_PARTIAL` 保留。后续独立裁判核对开发检查点。确认授权待定。 | [原门槛解释](../archive/genspace/DEPTH3_GATE_INTERPRETATION.md) · [证明审计](../archive/genspace/DEPTH3_INDEPENDENT_PROOF_AUDIT.md) → [逐查询证明与计时](../archive/genspace/results/depth3_proof/per_query.csv) · [三阶段成本配对汇总](../archive/genspace/PAPER1_ROUND3/Supplementary_Materials/S9_depth3_audited_stage_summary.json) · [批准状态](../archive/genspace/METHOD_FINAL_APPROVAL_PACKET.md) |
| **XR 前传**，双边协商必要性仍缺证据 | 已测 T1 强基线及已有业务要求。 | [问题与强基线重审](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/PAPER1_PROBLEM_BASELINE_RESET.md) → [TFH 证据与原入口](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/TFH_ARCHIVED_EVIDENCE.md) |
| **REORCH**，动态分组未稳定优于强静态比较 | 固定仿真条件和该诊断策略，保留 `REORCH_GAP_WEAK`。 | [判定报告](../archive/reorch/GATE_REPORT.md) → [配对统计表](../archive/reorch/results/paired_effects.csv) → [本地原始运行表](../archive/README.md#本地原始结果)，原路径为 `archive/reorch/results/raw_results.csv` |

## G1-A 逐任务核验

从[配对证据说明](../rdinp/experiments/durable-worker/evidence/g1a-20261128/README.md)选择同一拓扑下的计划及任务表。按配对和任务身份核对同输入、已释放任务的分母、回退与合格按期采用。完整的进程、协议与释槽事件仍按证据说明定位。

## 按实例核对的示例

先用 PILOT 的 family 汇总确定查哪个问题。原始逐例表已转入本地归档。已有实例 ID 且拥有该提交的 Git 历史时，可从历史版本直接提取对应行。

```bash
git grep -n -m 4 -F 'F1__medium__high__rich__d2__s0' 666a39fac685d0576849de7776a0c35d70d83e7f -- archive/genspace/results/pilot/raw_results.csv
```

写下引用的报告、表、筛选条件和对应 Git 提交。核对字节时，现行文件查[云端清单](../archive/MANIFEST.tsv)，已迁出的文件通过[本地明细入口](../archive/README.md#本地原始结果)按路径查 SHA-256。

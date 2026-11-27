# 历史经验与研究机会

以下条目来自已有记录。每项区分观察到的现象和待检验的问题。研究机会只在原判断缺口得到新证据后才成立。当前优先复核第 1、2 项，因为已有协议与执行端的配对记录。

## 1. 承诺回执、业务效果和采用时间要分开

- **已观察。** 同样的 `UNKNOWN` 可对应两种远端状态。代理试验还分开观察到管理确认、新路由实际可用、旧请求返回。常规执行租约已解决试验中的顺序复用，幂等、代际和执行点期限守卫也已覆盖一部分故障。 [顺序任务对照](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_02/顺序任务与失联恢复_实验报告.md) · [首轮记录](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/首轮实验与复现记录.md) · [代理证据](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/业务代理执行对照与下一步证据.md)
- **待检验。** 在有真实 SLA 和故障轨迹的服务中，状态查询、有限租约、条件更新和回退都启用后，是否仍出现可归因的迟交付、回退冲突或无效额度占用？若同观测、同动作的强对照可以消除损失，到此停止增强协议。

## 2. 截止检查之后还有执行尾段

- **已观察。** 本地 SQLite 对照中，最终检查时尚有余量，随后注入的暂停仍让提交越过期限。代理发送前检查也可能在后续转发中失效。试验余量亟需实际服务证据支持。 [执行点时序](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_03/执行点保护与场景证据_诊断报告.md) · [转发对照](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/summary.json)
- **待检验。** 从最终守卫到业务可见的尾段能否建立适用范围明确的时间上界，且预留该余量后的拒绝率仍满足业务要求？若执行点守卫和验证过的余量已足够，把它作为现有基线或工程规范。

## 3. 多车辆输入和同帧并行不能证明跨任务争用

- **已观察。** OPV2V 开发回放对链路与计算均敏感。已有 GPU 和队列数据缺少同一执行资源上、以共同时间基准记录的独立任务释放。 [开发回放](../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/result_summary.md) · [并发缺口](../archive/v2x-development/queue-diagnostic/QUEUE_DIAGNOSTIC_REPORT.md)
- **待检验。** 若取得真实释放轨迹，先配对检查同数据量下“隔离按期、共享迟到”能否重复出现，再对照因果 EDF 等简单调度。缺可归因争用时保留原受阻结论。简单调度足以解决时，记录基线结果并停止增加协商机制。

## 4. 搜索收益要同时算评分、验证和独立复核

- **已观察。** DG-PCE V1 在开发集未超过 FLAT。全扫描诊断说明，精确验证次数少时，特征计算和评分仍可能占用大量工作。Depth 3 的完整成本要把同一查询的在线、证明生成和独立裁判计时配对。短域精确穷尽与资源受限分别记账。 [FLAT 审计](../archive/genspace/FLAT_BASELINE_AUDIT_REPORT.md) · [完整成本与边界](../archive/genspace/PAPER1_ROUND3/PAPER1_ROUND3_REVISED.md) · [短域解释](../archive/genspace/DEPTH3_GATE_INTERPRETATION.md)
- **待检验。** 若真实业务的能力或动作空间频繁变化，无法及时复用预建索引，才值得复查按需生成的系统收益。对照需计入索引重建、在线检索、可审计证据成本和任务结果。确认实验仍待独立授权。

## 5. 先保留强单边对照与既有负结果

- **已观察。** XR 的 OptimizeRBs 在已测受保护流上已满足期限约束。REORCH 未得到稳定的动态分组优势。模型内资源差异和动态变化本身缺少足以支持新增协商的业务证据。 [XR 重审](../archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/PAPER1_PROBLEM_BASELINE_RESET.md) · [REORCH 判定](../archive/reorch/GATE_REPORT.md)
- **待检验。** 只有在有依据的服务要求、实际资源成本及可执行动作明确后，才检验是否存在同观测的强单边策略仍解决不了、且需要两个主体分别执行的决策。强单边策略已满足目标时保留原路线判定。

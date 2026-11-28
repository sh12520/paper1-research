# 当前推进

2026-11-28。唯一主线是 **RDINP 限时意图协商与边缘服务履约**。GOAL-1 处于 G1-A 人工门禁，状态为 blocked。研究目标、开题评审版和判定材料从[开题与研究目标审阅](proposals/README.md)进入。

## 问题与已验证边界

终端提交有截止期的边缘任务时，提交请求未到达与提交回执丢失都可能让终端观察到 `UNKNOWN`，而远端的权威提交与资源占用状态不同。需要确认，在真实任务与现有强基线下，这种差异是否导致可重复的按期交付或回退损失。 [选题与实验方案](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/论文1选题与实验方案_导师审阅.md)

| 进展 | 当前能说明什么 |
| --- | --- |
| C2 协议和首轮回归 | 控制面承诺与客户端所知可以分离。结果来自本地 HTTP、SQLite 和受控故障。 [首轮记录](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/首轮实验与复现记录.md) |
| CPU worker 与持久恢复 | 业务计算、槽位、租约和重启可在本机独立观察。 [RDINP 复现入口](../rdinp/README.md) |
| 执行点保护与真实软件代理 | 代际、条件写及期限守卫已覆盖部分受控故障。管理确认、首次新路由读回和旧请求排空可能发生在不同时刻。 [执行点诊断](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_03/执行点保护与场景证据_诊断报告.md) · [软件代理对照](../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/业务代理执行对照与下一步证据.md) |

## G1-A 判定与门禁

远端 Ubuntu 已完成 144 个配对和 5,184 条任务×方法记录。中高负载下 B2-info 相对强基线 B1 的合格按期采用率差为 −0.174 个百分点，95% CI [−0.434, 0.000]。两种边缘方法均未观测到 APP_BUSY，本轮未检验到旧任务占槽造成的后继准入争用。机器判定为 INCONCLUSIVE_REQUIRES_MANUAL_REVIEW。 [定量结果与逐任务表](../rdinp/experiments/durable-worker/evidence/g1a-20261128/README.md)

待人工决定补足 G1-A 的实际争用暴露，或按既有计划选择 Pivot。两个候选方向为旧执行者副作用与新任务截止期冲突，以及真实业务多档质量降级下的强因果对照。支持下一阶段的证据应能从任务身份追溯到授权、执行、采用和释放，并说明实际业务的质量、采用期限及旧请求排空语义。

先例和强基线的文献入口见[共享书目](../literature/README.md)。

## 并行路线

CS-ODS 提供已开发的方法和证明资产，独立确认未运行。XR 前传缺乏双边动作必要性的证据。[OPV2V](../research/opv2v-deadline/README.md) 保留为独立开发方向。已有结果可复用为候选业务的单边强对照，仍缺把它接入 RDINP 或验证跨任务争用的实际轨迹。各原始判定和追溯入口见[关键证据索引](evidence-index.md)。

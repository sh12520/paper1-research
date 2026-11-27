# 论文 1 独立确认实验 · 人工审批模板

## 当前状态

**`APPROVAL_PENDING`**。适用范围为 `GENSPACE-METHOD-HOLDOUT-V1`。当前执行授权文件中 `METHOD_HOLDOUT=false`、`CONFIRM=false`，readiness 和独立发布摘要均为空。此文件供人工审阅和填写。已核验的候选配置及历史结论同时归档。 [当前授权状态](METHOD_AUTHORIZATION_STATE.json) · [最终准备审查](METHOD_HOLDOUT_FINAL_READINESS_REPORT.md)

| 状态 | 需要具备的证据 |
|---|---|
| `APPROVAL_PENDING` | 最终候选按 SHA-256 送审。独立发布方、资源与计量条件、签署人及各项批准证据均待人工核定。 |
| `FROZEN_AUTHORIZED` | 对同一份冻结候选有明确的人工批准，且就绪证明、独立发布、保管和备份及计量条件均经验证并已获正式启用许可。执行授权限于本方法持出命名空间。旧 `CONFIRM` 保持关闭。 |

## 哈希与人工签署

从文件原始字节重新计算 SHA-256。审批包和冻结清单的摘要与签名保存在独立审批记录中。候选文件发生变化时重新提交对应版本、摘要与批准记录。

| 审批绑定 | SHA-256 |
|---|---|
| `METHOD_FINAL_APPROVAL_PACKET.md` | 由签署人填写 |
| `METHOD_FINAL_FREEZE_MANIFEST.json` | 由签署人填写 |
| 基础执行快照 | `b11c320219c6de92d890040d3b97345271423a34de9ec0430240fde0cde7fe1a` |
| 基础及 Depth 3 派生身份计划 | `a17fed60a43dac73bb864d2237c1d364d02db630b7b6e932c695d1808fa7605a` |
| Depth 3 证明执行附录 | `281bec8773cadbd761adb44b5895c0cb33c9c0b63dd3fdccfd122a6bde4a2701` |
| 当前关闭状态文件 | `bc79872fbed17a017397e20e68c35b6f78668636dedf690bd4319f514d2101d4` |

[冻结清单](METHOD_FINAL_FREEZE_MANIFEST.json) · [执行快照](METHOD_EXECUTION_SNAPSHOT_DRAFT.json) · [身份计划](METHOD_HOLDOUT_IDENTITY_PLAN_DRAFT.json) · [证明附录](results/depth3_proof/METHOD_DEPTH3_PROOF_EXECUTION_ADDENDUM_DRAFT.json)

| 签署字段 | 待人工填写 |
|---|---|
| 审批人、职责、签名及审批记录编号 | ＿＿＿＿ |
| 审批的文件字节版本、日期及时间 | ＿＿＿＿ |
| 明确批准的范围和生效条件 | ＿＿＿＿ |
| 独立发布责任人、采样实现及版本摘要、随机映射和保管记录的引用 | ＿＿＿＿ |
| 主机、资源隔离和查询间状态重置方案，日块及中断处置，跨块开发哨兵以及事前漂移诊断和通过规则的批准记录 | ＿＿＿＿ |
| 工作空间检查与独立备份的实际落点、保管人、可用容量和恢复校验记录 | ＿＿＿＿ |
| 事务签名密钥保管人和工作区外保管位置的引用 | ＿＿＿＿ |
| 最终 readiness、release 原始字节 SHA-256 与授权复核签名 | ＿＿＿＿ |

## 审批顺序与执行绑定

1. 人工审阅冻结清单、两项主终点及全部阈值、既定多重比较和缺失规则，批准同一个候选版本。执行计划的资源和测量条件、独立备份落点及恢复办法也需有审核记录。固定查询对独立性或计量完整性无从核实时，主区间和通过判据记为无法解释。
2. 明确批准独立发布方、采样实现版本和随机映射保管之后，由发布方在批准范围内形成基础序列化样本。准备态入口只消费外部送审的序列化数据，基础身份计划中的序号是标签。冻结的 `src/instances.py::derive_seed` 仅接收其现有命名空间，持出发布方的采样和隔离依据需另行审核。
3. 发布清单 `results/method_holdout_release/release_manifest.json` 采用 `GENSPACE-METHOD-SEALED-RELEASE-V1`，绑定专用命名空间、计划摘要及 2,880 个基础身份。每条记录含序列化字节摘要、实例摘要、公开和私有部分摘要。480 个派生查询引用这些已发布的基础记录。发布方与开发人员的接触隔离和成对方法共享同份序列化字节纳入发布复核。
4. 拟采用的 `METHOD_HOLDOUT_READINESS_ATTESTATION.json` 由经授权的责任人单独交付。受控入口核对状态 `READY_TO_FREEZE` 和字段 `snapshot_sha256`、`plan_sha256`、`depth3_proof_addendum_sha256`。审批记录同时绑定最终冻结包和清单摘要。正式启用许可确认后，授权状态的两项审批摘要分别绑定实际发布清单和 readiness 回执的原始字节，`required_snapshot_sha256` 绑定基础执行快照。
5. 经人工批准采用与证明附录绑定的入口，沿用冻结调度、Windows 监督、原子事务和独立证明复核。事务签名密钥须在工作区外保管，至少 32 字节，通过 `METHOD_HOLDOUT_TRANSACTION_KEY_FILE` 授予执行端。审批记录只留保管引用。备份与从备份恢复均以摘要、签名和快照再验证为准。

[最终审批包](METHOD_FINAL_APPROVAL_PACKET.md) · [预注册](METHOD_FINAL_PREREGISTRATION.md) · [执行计划](METHOD_FINAL_EXECUTION_PLAN.md) · [统计方案](METHOD_CONFIRMATION_STATISTICS.md) · [独立准入审计](METHOD_HOLDOUT_ROUTE_AUDIT.md) · [证明入口](results/depth3_proof/prepare_holdout_proof_entry.py)

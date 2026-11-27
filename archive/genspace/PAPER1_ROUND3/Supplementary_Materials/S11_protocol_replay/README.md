# S11 固定开发协议回放分母

`replay_checkpoint_counts.csv` 含可交付预算检查点的计数。观察单位为 `instance_id × depth × method × budget`。`verification_calls` 是实际验证调用，含 B2。`public_pool_count` 是通过 V2–V4 的累计候选次。`proposal_rounds` 计提案消息，一轮包括一条提案及其响应。`agreement` 为该可观察回放是否达成协议。`attempt_provenance.csv` 列出全部 1,248 条方法—查询尝试，包括没有任何预算输出的条目，并给出原封存 JSON 的路径、摘要、最高可用预算及状态。`replay_summary.json` 给出论文中各预算的汇总。

使用方法—查询记录作分母可解释工程覆盖。同一实例可在多个方法中重现，预算之间也可能重用结果。各预算的可回放集合不同，这些描述性计数不用于样本推断、方法间协议收益检验或确认判定。`COMPLETE` 表示全四档均有归档结果，存在早停或已证穷尽时可远早于最大验证预算。无回放结果的记录保留在总分母，未插补为协议失败。

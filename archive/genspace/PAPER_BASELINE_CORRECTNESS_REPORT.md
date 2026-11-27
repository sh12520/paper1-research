# 开发集基线正确性

封存的 96 个原深度查询和 24 个 depth3 查询是共同参照。已检查 1248/1248 个方法×查询，共 4590/4800 个检查点取得完整或短域证书。1248 个方法×查询的同输入前缀协议重放逐字段一致，含独立复核双方效用和 Nash。协议需超出已知前缀时保留不完整状态。

| 方法 | 深度 | 计划检查点 | 全长 | 短域 | 限额 | 不健全 | 未运行 | 协议完整 | 协议有限前缀 | 协议前缀不足 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CURRENT_ON_DEMAND_GRAMMAR_SEARCH | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 3 | 72 | 62 | 10 | 0 | 0 | 0 | 16 | 8 | 0 |
| GENERIC_ABSTRACT_BEST_FIRST | ≤2 | 384 | 349 | 30 | 5 | 0 | 0 | 62 | 34 | 0 |
| GENERIC_ABSTRACT_BEST_FIRST | 3 | 72 | 6 | 10 | 56 | 0 | 0 | 8 | 0 | 16 |
| FULL_FLAT | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| GENERIC_INDEX | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| CONTRACT_AWARE_INDEX | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |

通用基线在 15 个独立缩减域通过全域签名、顺序、binary64 分数、原始与规范代表以及穷尽检查。额外下界证据记录在 [generic_bound_checks.json](results/paper_method_dev/generic_bound_checks.json)。该证据状态为 PASS。

Depth 3 的一般规模核对以封存的精确前缀和当前前沿证书为参照。完整 FLAT 和两类索引的 Depth 3 结果为 N/A。

首轮预检在 JSON 预算键类型上产生 11 条假差异。它们的前缀摘要已匹配。统一运输键后，同一前缀重放的 11 条协议记录也逐字段相等。该预检不进入计时统计。 [传输核对](results/paper_method_dev/transport_checker_preflight/corrected_transport_check.json)

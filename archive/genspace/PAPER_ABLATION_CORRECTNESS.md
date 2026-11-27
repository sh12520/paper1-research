# 六项消融正确性

全部消融保持冻结 DSL、能力定义、公开分数、规范键、并列顺序与原双边接受规则。

完整有限缩减域通过数如下。完整规模检查按认证、限额和不健全分别记账。

| 消融 | 缩减域精确一致 |
| --- | --- |
| NO_EARLY_SEMANTIC_DEDUP | 15 |
| GENERIC_BOUND_ONLY | 15 |
| DEFER_CAPABILITY_PRUNING | 15 |
| WEAK_STATE_TIME_RESOURCE_ENVELOPE | 15 |
| NO_LAZY_STOP | 15 |
| NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 15 |

| 方法 | 深度 | 计划检查点 | 全长 | 短域 | 限额 | 不健全 | 未运行 | 协议完整 | 协议有限前缀 | 协议前缀不足 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NO_EARLY_SEMANTIC_DEDUP | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| NO_EARLY_SEMANTIC_DEDUP | 3 | 72 | 54 | 10 | 8 | 0 | 0 | 16 | 7 | 1 |
| GENERIC_BOUND_ONLY | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| GENERIC_BOUND_ONLY | 3 | 72 | 37 | 10 | 25 | 0 | 0 | 13 | 6 | 5 |
| DEFER_CAPABILITY_PRUNING | ≤2 | 384 | 350 | 14 | 20 | 0 | 0 | 59 | 35 | 2 |
| DEFER_CAPABILITY_PRUNING | 3 | 72 | 59 | 0 | 13 | 0 | 0 | 14 | 7 | 3 |
| WEAK_STATE_TIME_RESOURCE_ENVELOPE | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| WEAK_STATE_TIME_RESOURCE_ENVELOPE | 3 | 72 | 38 | 10 | 24 | 0 | 0 | 13 | 6 | 5 |
| NO_LAZY_STOP | ≤2 | 384 | 354 | 30 | 0 | 0 | 0 | 62 | 34 | 0 |
| NO_LAZY_STOP | 3 | 72 | 62 | 10 | 0 | 0 | 0 | 16 | 8 | 0 |
| NO_SEARCH_TIME_DOMAIN_NORMALIZATION | ≤2 | 384 | 349 | 30 | 5 | 0 | 0 | 62 | 34 | 0 |
| NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 3 | 72 | 8 | 10 | 54 | 0 | 0 | 9 | 1 | 14 |

A5 的 K 证书在首次可得时保存，取消停止后的交付状态单独记录。A6 推迟规范化会改变早期可识别的等价关系，测得的是在该表示下的边际影响。

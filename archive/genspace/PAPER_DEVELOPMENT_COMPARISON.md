# PAPER-BASELINE-ABLATION-01 · 开发集比较

**METHOD_READY_FOR_FREEZE_REVIEW**。同域配对显示在线优势，且单因素测试支持至少一项领域抽象减少展开。

封存的 96 个原深度查询和 24 个 depth3 查询是共同参照。已检查 1248/1248 个方法×查询，共 4590/4800 个检查点取得完整或短域证书。1248 个方法×查询的同输入前缀协议重放逐字段一致，含独立复核双方效用和 Nash。协议需超出已知前缀时保留不完整状态。

同一批既有查询按固定顺序交错深度和轮换方法，每一时刻只执行一个查询。高成本集合在结果读取前按原深度冻结公开合格候选数 ≥100,000 定义。下面的秒数包括限额前已做的工作。限额中的行不能代表完成耗时。

| 集合 | 方法 | 交付 | 耗时 s median/p95/max | 展开 median/p95/max | 完整赋值 median/p95/max | 采样峰值 MiB median/p95/max |
| --- | --- | --- | --- | --- | --- | --- |
| all_development | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 120/120 | 0.227 / 1.801 / 28.95 | 334.5 / 1.332e+04 / 1.959e+05 | 504 / 702 / 819 | 272.5 / 284.4 / 288.7 |
| all_development | GENERIC_ABSTRACT_BEST_FIRST | 97/120 | 0.7137 / 20.57 / 25.39 | 382 / 9.816e+04 / 1.326e+05 | 504 / 2.031e+04 / 8.119e+04 | 273.1 / 287.7 / 289.7 |
| all_development | NO_EARLY_SEMANTIC_DEDUP | 116/120 | 0.2408 / 3.705 / 35.47 | 337 / 6.706e+04 / 2.403e+05 | 522 / 1.627e+04 / 2.079e+05 | 272.8 / 287.6 / 359.7 |
| all_development | GENERIC_BOUND_ONLY | 111/120 | 0.2228 / 45 / 45.01 | 343 / 3.28e+05 / 3.968e+05 | 504 / 588 / 711 | 272.8 / 291.4 / 320.2 |
| all_development | DEFER_CAPABILITY_PRUNING | 105/120 | 0.282 / 26.57 / 45 | 714 / 3.705e+05 / 7.044e+05 | 591 / 5.117e+05 / 8.846e+05 | 273.2 / 288.5 / 304.7 |
| all_development | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 111/120 | 0.3271 / 15.71 / 44.38 | 632 / 1.799e+05 / 3.652e+05 | 1,170 / 2.135e+05 / 2.249e+05 | 273.1 / 290.9 / 302.2 |
| all_development | NO_LAZY_STOP | 71/120 | 0.5989 / 45 / 45.03 | 800 / 2.35e+05 / 2.884e+05 | 1,512 / 6.893e+04 / 2.186e+05 | 274.2 / 287 / 294.3 |
| all_development | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 97/120 | 0.306 / 35.55 / 45.07 | 346 / 1.438e+05 / 2.171e+05 | 522 / 6.589e+04 / 8.122e+04 | 273.3 / 288.5 / 380.7 |
| all_development | FULL_FLAT | 96/96 | 0.1891 / 2.009 / 2.678 | — / — / — | — / — / — | 520.2 / 543.9 / 567 |
| all_development | GENERIC_INDEX | 96/96 | 0.265 / 0.8274 / 1.811 | — / — / — | — / — / — | 517.9 / 543.2 / 548.5 |
| all_development | CONTRACT_AWARE_INDEX | 96/96 | 0.1157 / 0.5915 / 1.117 | — / — / — | — / — / — | 518 / 543.2 / 549 |
| depth_le_2 | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 96/96 | 0.2163 / 0.5331 / 1.312 | 325 / 846.5 / 1,044 | 504 / 555 / 588 | 272.1 / 284.1 / 288.7 |
| depth_le_2 | GENERIC_ABSTRACT_BEST_FIRST | 92/96 | 0.5956 / 11.69 / 12 | 351.5 / 5.029e+04 / 7.36e+04 | 513 / 6.402e+04 / 8.119e+04 | 272.3 / 286 / 289.7 |
| depth_le_2 | NO_EARLY_SEMANTIC_DEDUP | 96/96 | 0.2223 / 0.5868 / 1.292 | 327 / 2,183 / 3,535 | 513 / 2,636 / 6,012 | 271.7 / 283.6 / 288.7 |
| depth_le_2 | GENERIC_BOUND_ONLY | 96/96 | 0.2081 / 0.6673 / 1.18 | 333.5 / 3,785 / 1.344e+04 | 504 / 555 / 588 | 271.7 / 283.6 / 288.7 |
| depth_le_2 | DEFER_CAPABILITY_PRUNING | 87/96 | 0.2271 / 6.834 / 7.819 | 535.5 / 3e+05 / 3e+05 | 544.5 / 4.936e+05 / 5.165e+05 | 271.5 / 283.6 / 288.7 |
| depth_le_2 | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 96/96 | 0.3058 / 1.335 / 2.124 | 504 / 1.669e+04 / 2.579e+04 | 882 / 2.689e+04 / 4.752e+04 | 272 / 284.5 / 288.7 |
| depth_le_2 | NO_LAZY_STOP | 66/96 | 0.5437 / 12 / 12.01 | 800 / 2.405e+04 / 3.623e+04 | 1,512 / 3.847e+04 / 6.734e+04 | 272.9 / 285.7 / 291.3 |
| depth_le_2 | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 92/96 | 0.2754 / 11.52 / 12.16 | 325 / 4.594e+04 / 6.397e+04 | 531 / 6.4e+04 / 8.122e+04 | 272.2 / 284.7 / 289.5 |
| depth_le_2 | FULL_FLAT | 96/96 | 0.1891 / 2.009 / 2.678 | — / — / — | — / — / — | 520.2 / 543.9 / 567 |
| depth_le_2 | GENERIC_INDEX | 96/96 | 0.265 / 0.8274 / 1.811 | — / — / — | — / — / — | 517.9 / 543.2 / 548.5 |
| depth_le_2 | CONTRACT_AWARE_INDEX | 96/96 | 0.1157 / 0.5915 / 1.117 | — / — / — | — / — / — | 518 / 543.2 / 549 |
| high_cost | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 30/30 | 0.2354 / 0.5366 / 0.5959 | 522.5 / 986.8 / 1,044 | 504 / 586.6 / 588 | 272.9 / 284.8 / 288.4 |
| high_cost | GENERIC_ABSTRACT_BEST_FIRST | 28/30 | 1.279 / 11.83 / 12 | 4,182 / 6.02e+04 / 7.36e+04 | 3,393 / 6.569e+04 / 8.119e+04 | 273.4 / 288.3 / 289.7 |
| high_cost | NO_EARLY_SEMANTIC_DEDUP | 30/30 | 0.2503 / 0.5951 / 0.7252 | 791 / 3,266 / 3,491 | 1,062 / 2,978 / 3,144 | 272.9 / 285.7 / 288.6 |
| high_cost | GENERIC_BOUND_ONLY | 30/30 | 0.3232 / 0.7958 / 0.876 | 1,776 / 7,149 / 1.344e+04 | 504 / 586.6 / 588 | 272.9 / 285.7 / 288.6 |
| high_cost | DEFER_CAPABILITY_PRUNING | 30/30 | 0.2336 / 0.5011 / 0.609 | 552 / 1,665 / 2,884 | 507 / 1,799 / 3,789 | 272.9 / 285.7 / 288.6 |
| high_cost | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 30/30 | 0.8431 / 1.897 / 2.124 | 8,350 / 2.442e+04 / 2.579e+04 | 1.246e+04 / 4.149e+04 / 4.752e+04 | 273.6 / 286.7 / 288.1 |
| high_cost | NO_LAZY_STOP | 0/30 | 12 / 12 / 12.01 | 1.901e+04 / 2.415e+04 / 2.528e+04 | 2.35e+04 / 3.785e+04 / 3.989e+04 | 276.3 / 288.8 / 291.3 |
| high_cost | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 28/30 | 0.8286 / 11.95 / 12 | 2,564 / 4.971e+04 / 6.397e+04 | 3,429 / 6.558e+04 / 8.122e+04 | 273.2 / 287.5 / 289.5 |
| high_cost | FULL_FLAT | 30/30 | 1.745 / 2.2 / 2.678 | — / — / — | — / — / — | 537.6 / 553.4 / 567 |
| high_cost | GENERIC_INDEX | 30/30 | 0.2381 / 1.217 / 1.623 | — / — / — | — / — / — | 518.5 / 536.8 / 548.5 |
| high_cost | CONTRACT_AWARE_INDEX | 30/30 | 0.183 / 0.8741 / 1.117 | — / — / — | — / — / — | 518.4 / 536.8 / 549 |
| rich_depth2 | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 24/24 | 0.2354 / 0.5401 / 0.5959 | 491.5 / 1,017 / 1,044 | 504 / 587.5 / 588 | 272.3 / 283.3 / 286 |
| rich_depth2 | GENERIC_ABSTRACT_BEST_FIRST | 22/24 | 1.199 / 10.99 / 12 | 2,917 / 5.583e+04 / 6.025e+04 | 1,746 / 5.853e+04 / 6.569e+04 | 272.4 / 283.4 / 288.8 |
| rich_depth2 | NO_EARLY_SEMANTIC_DEDUP | 24/24 | 0.2503 / 0.6449 / 0.7252 | 787.5 / 3,295 / 3,491 | 1,059 / 2,935 / 3,144 | 272.4 / 283.2 / 287.5 |
| rich_depth2 | GENERIC_BOUND_ONLY | 24/24 | 0.3264 / 0.7616 / 0.876 | 1,280 / 6,673 / 7,149 | 504 / 587.5 / 588 | 272.4 / 283.3 / 287.5 |
| rich_depth2 | DEFER_CAPABILITY_PRUNING | 24/24 | 0.2414 / 0.5592 / 0.609 | 491.5 / 1,017 / 1,044 | 504 / 587.5 / 588 | 272.3 / 283.3 / 287.5 |
| rich_depth2 | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 24/24 | 0.7313 / 1.926 / 2.124 | 6,970 / 2.131e+04 / 2.301e+04 | 9,387 / 3.669e+04 / 4.107e+04 | 272.3 / 283.6 / 288.1 |
| rich_depth2 | NO_LAZY_STOP | 0/24 | 12 / 12 / 12.01 | 1.943e+04 / 2.418e+04 / 2.528e+04 | 2.496e+04 / 3.794e+04 / 3.989e+04 | 274.6 / 286.7 / 291.3 |
| rich_depth2 | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 22/24 | 0.6241 / 10.97 / 12 | 1,602 / 4.504e+04 / 5.057e+04 | 1,782 / 5.829e+04 / 6.573e+04 | 272.6 / 283.4 / 288.7 |
| rich_depth2 | FULL_FLAT | 24/24 | 1.753 / 2.274 / 2.678 | — / — / — | — / — / — | 537.6 / 559.1 / 567 |
| rich_depth2 | GENERIC_INDEX | 24/24 | 0.2256 / 1.308 / 1.623 | — / — / — | — / — / — | 518.5 / 543.9 / 548.5 |
| rich_depth2 | CONTRACT_AWARE_INDEX | 24/24 | 0.1748 / 1.009 / 1.117 | — / — / — | — / — / — | 518.4 / 543.9 / 549 |
| sparse | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 60/60 | 0.1744 / 1.856 / 28.95 | 290 / 5,238 / 1.914e+05 | 504 / 576.9 / 711 | 271.5 / 284.5 / 288.4 |
| sparse | GENERIC_ABSTRACT_BEST_FIRST | 51/60 | 0.5964 / 21 / 23.17 | 309 / 1.002e+05 / 1.326e+05 | 502.5 / 6.374e+04 / 8.119e+04 | 272.7 / 287 / 289.7 |
| sparse | NO_EARLY_SEMANTIC_DEDUP | 58/60 | 0.233 / 4.058 / 27.26 | 290 / 7.879e+04 / 2.256e+05 | 504 / 1.723e+04 / 2.079e+05 | 271.5 / 285.9 / 356.4 |
| sparse | GENERIC_BOUND_ONLY | 57/60 | 0.2007 / 8.413 / 45 | 290 / 5.163e+04 / 3.968e+05 | 504 / 541.3 / 711 | 271.5 / 288.8 / 316.6 |
| sparse | DEFER_CAPABILITY_PRUNING | 45/60 | 0.3249 / 37.63 / 45 | 1,322 / 6.31e+05 / 7.044e+05 | 1,512 / 5.517e+05 / 8.846e+05 | 273.9 / 288.6 / 304.7 |
| sparse | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 58/60 | 0.2821 / 8.284 / 25.71 | 366 / 1.067e+05 / 2.494e+05 | 684 / 1.251e+05 / 2.249e+05 | 272.1 / 287.5 / 302.2 |
| sparse | NO_LAZY_STOP | 47/60 | 0.4371 / 45 / 45.03 | 402 / 1.235e+05 / 2.884e+05 | 756 / 6.737e+04 / 2.186e+05 | 272.7 / 285.4 / 290.5 |
| sparse | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 51/60 | 0.2869 / 31.19 / 38.38 | 299 / 1.383e+05 / 2.14e+05 | 504 / 6.381e+04 / 8.122e+04 | 272.7 / 286.2 / 367.5 |
| sparse | FULL_FLAT | 48/48 | 0.1467 / 1.573 / 1.926 | — / — / — | — / — / — | 518.6 / 542.1 / 548.1 |
| sparse | GENERIC_INDEX | 48/48 | 0.2283 / 0.8245 / 1.811 | — / — / — | — / — / — | 517.7 / 541.4 / 548.1 |
| sparse | CONTRACT_AWARE_INDEX | 48/48 | 0.1054 / 0.5929 / 1.091 | — / — / — | — / — / — | 517.9 / 541.5 / 547.1 |
| depth3 | CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 24/24 | 0.7486 / 28.25 / 28.95 | 3,266 / 1.913e+05 / 1.959e+05 | 580.5 / 709.6 / 819 | 277 / 284.3 / 285.4 |
| depth3 | GENERIC_ABSTRACT_BEST_FIRST | 5/24 | 19.45 / 23.06 / 25.39 | 8.492e+04 / 1.243e+05 / 1.326e+05 | 225 / 378 / 450 | 278.5 / 288.9 / 289 |
| depth3 | NO_EARLY_SEMANTIC_DEDUP | 20/24 | 2.141 / 33.07 / 35.47 | 2.823e+04 / 2.256e+05 / 2.403e+05 | 1.315e+04 / 1.373e+05 / 2.079e+05 | 274.9 / 355.5 / 359.7 |
| depth3 | GENERIC_BOUND_ONLY | 15/24 | 5.828 / 45 / 45.01 | 4.082e+04 / 3.396e+05 / 3.968e+05 | 85.5 / 700.6 / 711 | 285.1 / 314.4 / 320.2 |
| depth3 | DEFER_CAPABILITY_PRUNING | 18/24 | 2.112 / 45 / 45 | 1.447e+04 / 6.451e+05 / 7.044e+05 | 702 / 8.492e+05 / 8.846e+05 | 277.5 / 299.1 / 304.7 |
| depth3 | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 15/24 | 11.09 / 26.23 / 44.38 | 1.171e+05 / 2.438e+05 / 3.652e+05 | 1.133e+05 / 2.249e+05 / 2.249e+05 | 284.3 / 298 / 302.2 |
| depth3 | NO_LAZY_STOP | 5/24 | 45 / 45.01 / 45.03 | 7.922e+04 / 2.581e+05 / 2.884e+05 | 4.462e+04 / 1.844e+05 / 2.186e+05 | 280.6 / 293.1 / 294.3 |
| depth3 | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 5/24 | 30.27 / 45 / 45.07 | 1.388e+05 / 2.095e+05 / 2.171e+05 | 262.5 / 7.949e+04 / 8.025e+04 | 280.8 / 355.8 / 380.7 |

以下消融差值为消融减当前方法。共同认证配对与全队列处罚后配对分开解释。处罚秒数为预设墙钟上限。墙钟截尾行的实做时间可作完成时长下界。A5 的 post-proof 工作量包含限额前的额外搜索，未穷尽时仅为下界。

| 集合 | 消融 | 共同精确交付 n | 配对耗时 Δ 秒 | 配对展开 Δ | 限额处罚后配对 Δ 秒 | 墙钟截尾配对 n | 时差下界中位 秒 | 该机制工作量中位 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| depth_le_2 | NO_EARLY_SEMANTIC_DEDUP | 96 | -0.0003551 | 2.5 | -0.0003551 | 0 | — | terminal_duplicates = 4.5 |
| depth_le_2 | GENERIC_BOUND_ONLY | 96 | 0.002283 | 9 | 0.002283 | 0 | — | bound_evaluations = 433 |
| depth_le_2 | DEFER_CAPABILITY_PRUNING | 87 | 0.008237 | 0 | 0.01307 | 0 | — | deferred_capability_rejects = 0 |
| depth_le_2 | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 96 | 0.02293 | 197 | 0.02293 | 0 | — | coarsened_envelopes = 571 |
| depth_le_2 | NO_LAZY_STOP | 66 | 0.263 | 463 | 0.3166 | 30 | 11.76 | post_proof_partial_expanded = 490 |
| depth_le_2 | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 92 | 0.02516 | 11 | 0.02915 | 4 | 11.34 | raw_asts_materialized = 531 |
| high_cost | NO_EARLY_SEMANTIC_DEDUP | 30 | 0.02326 | 351 | 0.02326 | 0 | — | terminal_duplicates = 558 |
| high_cost | GENERIC_BOUND_ONLY | 30 | 0.07192 | 1,246 | 0.07192 | 0 | — | bound_evaluations = 3,794 |
| high_cost | DEFER_CAPABILITY_PRUNING | 30 | 0.01423 | 0 | 0.01423 | 0 | — | deferred_capability_rejects = 0 |
| high_cost | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 30 | 0.6287 | 7,790 | 0.6287 | 0 | — | coarsened_envelopes = 1.097e+04 |
| high_cost | NO_LAZY_STOP | 0 | — | — | 11.76 | 30 | 11.76 | post_proof_partial_expanded = 1.847e+04 |
| high_cost | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 28 | 0.5069 | 1,647 | 0.5896 | 2 | 11.43 | raw_asts_materialized = 3,429 |
| sparse | NO_EARLY_SEMANTIC_DEDUP | 58 | 0.008947 | 32.5 | 0.009962 | 0 | — | terminal_duplicates = 51 |
| sparse | GENERIC_BOUND_ONLY | 57 | 0.0007635 | 0 | 0.002428 | 3 | 43.03 | bound_evaluations = 315.5 |
| sparse | DEFER_CAPABILITY_PRUNING | 45 | 0.0203 | 298 | 0.05706 | 3 | 44.94 | deferred_capability_rejects = 1,431 |
| sparse | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 58 | 0.01149 | 77.5 | 0.01303 | 0 | — | coarsened_envelopes = 371 |
| sparse | NO_LAZY_STOP | 47 | 0.04933 | 112 | 0.1417 | 13 | 16.05 | post_proof_partial_expanded = 116.5 |
| sparse | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 51 | 0.01464 | 13 | 0.02721 | 2 | 11.06 | raw_asts_materialized = 504 |
| depth3 | NO_EARLY_SEMANTIC_DEDUP | 20 | 0.7432 | 1.726e+04 | 0.947 | 0 | — | terminal_duplicates = 1.25e+04 |
| depth3 | GENERIC_BOUND_ONLY | 15 | 0.4623 | 6,520 | 3.714 | 9 | 43.34 | bound_evaluations = 1.613e+04 |
| depth3 | DEFER_CAPABILITY_PRUNING | 18 | 0.1083 | 0 | 0.2492 | 3 | 44.94 | deferred_capability_rejects = 0 |
| depth3 | WEAK_STATE_TIME_RESOURCE_ENVELOPE | 15 | 1.594 | 2.706e+04 | 9.963 | 0 | — | coarsened_envelopes = 1.152e+05 |
| depth3 | NO_LAZY_STOP | 5 | 0.005705 | 0 | 43.23 | 19 | 43.39 | post_proof_partial_expanded = 5.994e+04 |
| depth3 | NO_SEARCH_TIME_DOMAIN_NORMALIZATION | 5 | 0.02156 | 143 | 43.23 | 3 | 44.58 | raw_asts_materialized = 262.5 |

逐条结果含分数调用、下界调用、前沿峰值、认证状态和双边结果。候选赋值、语义状态、原始 witness AST 和索引记录访问是不同事件。固定开发面板仅作描述性解读，不将重用查询的统计量外推为独立确认。

[逐查询 CSV](results/paper_method_dev/per_query.csv) · [全部汇总](results/paper_method_dev/comparison_summary.csv) · [消融汇总](results/paper_method_dev/ablation_summary.csv)

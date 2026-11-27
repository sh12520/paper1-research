# Generic and contract-aware index comparison

The generic tree partitions the same public feature vectors by axes. The contract-aware tree also partitions by legal capability and depth.

Both trees use deterministic range-based axis selection, median splitting, the same leaf limit and the same admissible FLAT score bound. The contract forest also groups equal depth-specific availability, active/offload masks and mechanism bits. Both variants apply the exact public eligibility check when needed.

| Variant | K=500 cohort | Paired with FLAT | TouchRatio median / p95 | Public search median / p95 s | p95 reduction vs FLAT |
| --- | --- | --- | --- | --- | --- |
| generic | target | 842/842 | 49.1402% / 100.0000% | 0.144821 / 0.560690 | 68.95% |
| generic | large | 340/340 | 0.6589% / 6.7401% | 0.121279 / 0.859865 | 55.48% |
| generic | rich_depth2 | 298/298 | 0.6574% / 4.7952% | 0.121279 / 0.827345 | 57.14% |
| contract | target | 842/842 | 55.4894% / 100.0000% | 0.010324 / 0.308825 | 82.90% |
| contract | large | 340/340 | 0.4668% / 3.1028% | 0.044335 / 0.484170 | 74.93% |
| contract | rich_depth2 | 298/298 | 0.4668% / 2.7012% | 0.044228 / 0.467000 | 75.81% |

Correctness coverage for each variant and each K is reported in `INDEX_CORRECTNESS_REPORT.md`. Timing summaries use the paired FLAT IDs for each row. Unequal cohort coverage precludes a direct variant speed comparison between those rows.

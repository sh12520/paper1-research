# Depth≤2 regression against the frozen FLAT comparator

**PASS** on 96 sealed queries.

The regression compares compact signature order, binary64 score bits and canonical witnesses with the previous graph-free deduplication replay. That archived replay passed the independent FLAT comparisons on all 96 fixed existing cases. Both seals and the prior reference CSV hashes were checked before use.

| Check | K or budget | Compared fixtures | Exact | Mismatch | Incomplete |
| --- | --- | --- | --- | --- | --- |
| topk | 10 | 96 | 96 | 0 | 0 |
| topk | 50 | 96 | 96 | 0 | 0 |
| topk | 100 | 96 | 96 | 0 | 0 |
| topk | 500 | 96 | 96 | 0 | 0 |

The independent original FLAT graph comparator was also rerun offline after both online workers exited. It recorded 384/384 exact comparisons.

Online regression uses existing serialized development queries and the original structural ranking domain. Its goal is the depth-two score and order check. The archive already contains separate exact agreement checks. Median and p95 search seconds are reported descriptively on the same fixed IDs.

| Lane | n | Median s | p95 s |
| --- | --- | --- | --- |
| Archived deduplication | 96 | 0.31138270000519697 | 0.7218498500005808 |
| Current depth≤2 regression | 96 | 0.26407400000607595 | 0.8248922499915352 |

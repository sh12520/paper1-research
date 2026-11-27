# Grammar deduplication correctness

G1 **PASS**. G2 **PASS**.

The fixed set consists of the original 96 seed-index-0 serialized development queries. An independent reference loaded the existing graph only after the graph-free online worker finished and its seal verified. It reproduced original FLAT candidate order and compared binary64 score bits. It also compared original agreements, representatives, utilities, Nash values, verification counts and exact proposal histories.

| Check | K or budget | Exact / 96 | Mismatch | Incomplete |
| --- | --- | --- | --- | --- |
| topk | 10 | 96 | 0 | 0 |
| topk | 50 | 96 | 0 | 0 |
| topk | 100 | 96 | 0 | 0 |
| topk | 500 | 96 | 0 | 0 |
| protocol | 100 | 96 | 0 | 0 |
| protocol | 500 | 96 | 0 | 0 |
| protocol | 5000 | 96 | 0 | 0 |

The correctness record binds the online source fingerprint, sealed input IDs and reference CSVs. Formal performance clearance requires all comparisons at each K and budget.

Performance clearance = **True**.

The final two limits from the preceding grammar gate were both included in the original fixed 96. Times below are correctness-phase end-to-end protocol run times. They do not enter G4.

| Formerly limited query | Prior elapsed s (censored) | New elapsed s | New terminal status | B=5000 verification calls |
| --- | --- | --- | --- | --- |
| F2__medium__high__sparse__d2__s0 | 60.0487 | 12.1738 | COMPLETE | 5000 |
| F4__medium__medium__sparse__d2__s0 | 60.0537 | 11.8702 | COMPLETE | 5000 |

The same-128 diagnostic had 128 exact nonempty shared prefixes, 0 mismatches and 0 empty intersections.

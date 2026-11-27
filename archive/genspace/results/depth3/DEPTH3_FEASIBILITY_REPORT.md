# DEPTH3-FEASIBILITY-01

**DEPTH3_PARTIAL**

Depth≤2 regression seal: **PASS** across 96 existing fixed queries. The depth-three online seal covers 24 existing public fixtures, with clean guard counters and 0 unsound certificate checkpoints.

| K | Exact certified | Full length | Exhausted short | Requested | Exact rate |
| --- | --- | --- | --- | --- | --- |
| 10 | 24 | 24 | 0 | 24 | 100.00% |
| 100 | 24 | 19 | 5 | 24 | 100.00% |
| 500 | 24 | 19 | 5 | 24 | 100.00% |

Every requested checkpoint was certified as an exact finite-domain prefix. The run recorded zero resource-limited checkpoints.

The following K500 queries exhausted their entire domains. Their exact prefixes are shorter than the requested K because that many distinct eligible contracts exist for those public capabilities.

| Instance | Exact domain size |
| --- | --- |
| F1__low__high__sparse__d2__s0 | 81 |
| F2__high__high__sparse__d2__s0 | 27 |
| F3__high__high__sparse__d2__s0 | 81 |
| F4__medium__high__sparse__d2__s0 | 81 |
| F4__high__high__sparse__d2__s0 | 81 |

| Family | Richness | Certified K500 pressure levels | Covered / 3 |
| --- | --- | --- | --- |
| F1 | rich | high, low, medium | 3 |
| F1 | sparse | high, medium | 2 |
| F2 | rich | high, low, medium | 3 |
| F2 | sparse | low, medium | 2 |
| F3 | rich | high, low, medium | 3 |
| F3 | sparse | low, medium | 2 |
| F4 | rich | high, low, medium | 3 |
| F4 | sparse | low | 1 |

FEASIBLE requires at least 20 of 24 full-length K500 certificates, at least two pressure levels per family and richness pair, a passing depth-two regression and zero unsound checkpoints. PARTIAL requires one or more certified K10 results with a passing regression and no unsound checkpoints. Other outcomes are INFEASIBLE.

Depth-three uses the fixed public six-cell DSL with up to four structural groups. The sealed trials are an engineering feasibility gate on existing fixtures. Exact prefixes are not a full depth-three enumeration.

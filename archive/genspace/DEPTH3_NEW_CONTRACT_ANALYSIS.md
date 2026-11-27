# Depth-3 novelty and agreement analysis

The comparator opened the frozen **depth≤2** semantic graph only after the 24 graph-free development queries were sealed. It searched sorted depth-two signatures and used the exact capability-conditioned depth≤2 availability mask, without building a depth-three graph. The mask uses all exact O1 structures; the narrower historical FLAT one/two-group ranking does not define novelty. Each emitted witness and protocol winner was independently normalized, encoded and checked by the original V1–V5 state machine at effective depth 3.

Online seal SHA256 `8e63d43a823525a59f59d81d680423a931557cfa13fa7318965888e698561517`.

The table counts candidate occurrences across queries, so a signature seen in different queries can count more than once. Novelty includes signatures missing globally and those present globally but absent under the query’s frozen capability availability. Only certified emissions are counted. An incomplete prefix cannot establish the full Top-K result. A proven exhausted domain is reported separately when shorter than K.

| K | Full-length certified queries | Short exhausted certificates | Emitted prefix candidates | Globally absent | Absent after capability conditioning only | Independently verified novel |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 24/24 | 0/24 | 240 | 16 | 0 | 1 |
| 100 | 19/24 | 5/24 | 2251 | 1029 | 0 | 197 |
| 500 | 19/24 | 5/24 | 9851 | 7041 | 0 | 642 |

The emitted prefixes contain 642 independently verified depth3-only candidate occurrences across 8 queries. Among cases where old O1 had no agreement, they contain 0 such candidates across 0 queries. This is evidence of existence on the tested query only. The table below requires a selected agreement from the actual bilateral protocol.

A capped case remains **UNKNOWN** for agreement existence. This includes a verification-budget stop with no agreement and no proof of domain exhaustion. “New agreement over O1” requires a verified selected depth3-only witness on an instance where the original exact depth≤2 O1 reported no agreement. A novel winner on a case already solved by O1 shows a different available contract. The signed Nash difference is computed only for two verified agreements.

| Exact verification budget | Agreements | Exhausted with no agreement | Unknown | Depth3-only winners | New over O1 |
|---:|---:|---:|---:|---:|---:|
| 100 | 14 | 1 | 9 | 1 | 0 |
| 500 | 14 | 2 | 8 | 1 | 0 |
| 1000 | 14 | 2 | 8 | 1 | 0 |
| 5000 | 14 | 2 | 8 | 1 | 0 |

| Instance | B=5000 outcome | Original B2 / O1 | Winner depth≤2 membership | Signed Nash difference vs old O1 |
|---|---|---|---|---:|
| `F1__low__high__sparse__d2__s0` | AGREEMENT | True / True | IN_CONDITIONED_DEPTH2 | -0.041222490 |
| `F1__low__high__rich__d2__s0` | AGREEMENT | True / True | IN_CONDITIONED_DEPTH2 | -0.083971048 |
| `F1__medium__high__sparse__d2__s0` | UNKNOWN | False / False | — | — |
| `F1__medium__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | -0.015263922 |
| `F1__high__high__sparse__d2__s0` | UNKNOWN | False / False | — | — |
| `F1__high__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | +0.000000000 |
| `F2__low__high__sparse__d2__s0` | UNKNOWN | False / False | — | — |
| `F2__low__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | -0.022067432 |
| `F2__medium__high__sparse__d2__s0` | UNKNOWN | False / False | — | — |
| `F2__medium__high__rich__d2__s0` | UNKNOWN | False / False | — | — |
| `F2__high__high__sparse__d2__s0` | EXHAUSTED_NO_AGREEMENT | False / False | — | — |
| `F2__high__high__rich__d2__s0` | UNKNOWN | False / False | — | — |
| `F3__low__high__sparse__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | +0.000000000 |
| `F3__low__high__rich__d2__s0` | AGREEMENT | True / True | IN_CONDITIONED_DEPTH2 | -0.013744092 |
| `F3__medium__high__sparse__d2__s0` | AGREEMENT | False / True | DEPTH3_ONLY_GLOBAL | -0.024020191 |
| `F3__medium__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | -0.016132376 |
| `F3__high__high__sparse__d2__s0` | EXHAUSTED_NO_AGREEMENT | False / False | — | — |
| `F3__high__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | -0.062403004 |
| `F4__low__high__sparse__d2__s0` | AGREEMENT | True / True | IN_CONDITIONED_DEPTH2 | -0.021692379 |
| `F4__low__high__rich__d2__s0` | UNKNOWN | False / False | — | — |
| `F4__medium__high__sparse__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | +0.000000000 |
| `F4__medium__high__rich__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | -0.015768882 |
| `F4__high__high__sparse__d2__s0` | AGREEMENT | False / True | IN_CONDITIONED_DEPTH2 | +0.000000000 |
| `F4__high__high__rich__d2__s0` | UNKNOWN | False / False | — | — |

Machine-readable candidate and agreement details are saved in `results/depth3/new_contract_candidates.csv` and `results/depth3/new_contract_agreements.csv`. This is a fixed development fixture study. The certified prefix and bounded protocol results do not enumerate all depth-three agreements.

## Public footprint of novel verified contracts

The emitted depth3-only occurrences comprise 3,716 distinct compact signatures across the grid. Of these, 483 were independently verified on at least one queried instance.

C denotes If, D denotes Delay, P denotes Sequence or ValidFor, and O denotes Offload. The counts use the normalized whole-contract capability footprint. They do not attribute acceptance causally to an individual constructor. Independently verified candidates in the captured prefix and selected bilateral agreements use separate columns.

| Group footprint | Verified novel emitted candidates | Verified novel emitted candidates where old O1 failed | Selected novel agreements at B=5000 |
|---|---:|---:|---:|
| C+O | 21 | 0 | 1 |
| C+P+O | 81 | 0 | 0 |
| P | 60 | 0 | 0 |
| P+O | 480 | 0 | 0 |

| Instance | Depth | Group footprint | Constructors | Verification calls | Proposal rounds | Old O1 agreement | Signed Nash difference |
|---|---:|---|---|---:|---:|---|---:|
| `F3__medium__high__sparse__d2__s0` | 3 | C+O | If+Offload | 43 | 10 | True | -0.024020191 |

### Verified depth3-only agreement on `F3__medium__high__sparse__d2__s0`

Normalized witness `["If","moving",["If","moving",["Offload","edge",["Static",0.8,1.0,0.5]],["Static",0.4,1.0,0.5]],["If","moving",["Static",0.4,1.0,0.5],["Offload","edge",["Static",0.8,1.0,0.5]]]]`.

Required capabilities were `apply_conditional_policy`, `enable_edge_offload`, `observe_motion_state`, `reserve_edge_compute`, `reserve_fh_resource`, `reserve_ran_resource`, `select_latency_profile`, `set_quality`, `set_rate`.

At B=5000 the selected witness had uA 0.800673035, uN 0.614346462, and Nash 0.491890646. Its acceptance followed 10 proposal rounds and 43 exact verifier calls.

The agreement CSV gives the checkpoint proposal rounds, total rounds observed in the sealed case, and mechanism groups, constructors, and required capabilities for each verified winner. Missing checkpoint results have no completed round counter. The case-level observed counter is still retained.

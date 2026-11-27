# PILOT-01 canonical cases

**4/4 deterministic canonical cases passed.** These cases were executed separately from the 1,920 random PILOT instances and are excluded from all PILOT agreement rates, averages, comparisons, and future confirmation data. No random seed was read or generated in this check.

| Family | Expected structure and observed action | Structural target | First failing layer of low/high static profiles | Application / network utility |
|---|---|---|---|
| F1 | `If(moving, low, high)`: quality 0.4 when moving and 0.9 when still | Verified | V5 / V4 | 0.65 / 0.80 |
| F2 | `Delay(1, high)`: no service at time 0, quality 0.9 at times 1–2 | Verified | V4 / V4 | 0.60 / 0.80 |
| F3 | `Sequence(1, low, high)`: quality 0.4 at time 0 and 0.9 at time 1 | Verified | V5 / V4 | 0.65 / 0.80 |
| F4 | `Offload(edge, high)`: RAN and EDGE demands both 0.45 at each time | Verified | V5 / V4 | 0.90 / 0.80 |

All target actions were checked against RAN/FH/EDGE capacities. Removing each structural capability required by a target caused a V2 failure. The existing `test_four_structural_mechanisms_resolve_fixed_deadlock` and `test_missing_capability_rejects_each_structure` unit tests both passed. Detailed action, demand, capacity and failure-layer evidence is in `results/pilot_canonical_audit.json`.

These are the pre-existing `src/canonical_cases.py` fixtures: hand-constructed, simplified validator and grammar checks with permissive fixture precondition functions and fixture-specific utility/resource inputs. They do not prove that the full stochastic PILOT model or real network execution works. `verified` here denotes passage under that abstract fixture's validator only.

The repository search did not identify a separate existing four-family, seed-free canonical set using the full operational instance and acceptance model. The existing full-model mechanism-review tests use generated ENGINEERING fixtures and check public mechanism behavior; they were not run for this canonical check and are not evidence of full bilateral acceptance.

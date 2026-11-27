# SMOKE-01 diagnostic report

Status: SMOKE_FAIL.
Completed instances: 35/192.
Primary worker count: 1. No bootstrap, research gates or research-success conclusion were computed.
Peak observed worker RSS: 766025728 bytes; peak sampled aggregate workers: 726982656 bytes; peak sampled system physical used: 16335958016 bytes.
Memory samples are periodic and may miss transient spikes. Percentiles use linear interpolation at (n−1)×p.
Failed invariants: C01_192_complete, C02_zero_crash, C03_zero_silent_skip, C05_space_containment, C06_negative_control_exact, C07_invalid_never_verified, C08_zero_nan_inf, C09_utility_unit_interval, C10_schema_complete, C11_rerun_8_equal, C12_1v2_16_equal.
Negative-control exact equality (all instances): FAIL/UNCHECKABLE.
Snapshot, source, graph, indices, plan and preregistration unchanged: PASS.
SMOKE-01 is an engineering/exploratory pipeline check and is not confirmation evidence for the research hypothesis.
Public eligible count is conditioned candidate count minus V1/V2/V3 failures; it is not the number passing capacity or private acceptance.
Finite/unit-interval checks apply to defined output and V5-reached utilities; utilities for non-eligible or infeasible classes are undefined and are not treated as zero.
The results characterize implementation diagnostics only. PILOT/CONFIRM were not run.

| Family | Method | Instances | Agreements | Deadlocks | All zero | All one |
|---|---|---:|---:|---:|---|---|
| F1 | B0 | 35 | 0 | 35 | True | False |
| F1 | B1 | 35 | 4 | 31 | False | False |
| F1 | B2 | 35 | 13 | 22 | False | False |
| F1 | O1 | 35 | 30 | 5 | False | False |
| F2 | B0 | 0 | 0 | 0 | False | False |
| F2 | B1 | 0 | 0 | 0 | False | False |
| F2 | B2 | 0 | 0 | 0 | False | False |
| F2 | O1 | 0 | 0 | 0 | False | False |
| F3 | B0 | 0 | 0 | 0 | False | False |
| F3 | B1 | 0 | 0 | 0 | False | False |
| F3 | B2 | 0 | 0 | 0 | False | False |
| F3 | O1 | 0 | 0 | 0 | False | False |
| F4 | B0 | 0 | 0 | 0 | False | False |
| F4 | B1 | 0 | 0 | 0 | False | False |
| F4 | B2 | 0 | 0 | 0 | False | False |
| F4 | O1 | 0 | 0 | 0 | False | False |

O1_s: median=0.7808482000255026, p95=4.784310570015805, max=5.237985900021158 seconds (n=35).

complete_run_paired_s: median=0.8513139000278898, p95=4.817110319976928, max=5.261494799982756 seconds (n=35).

## Post-run failure clarification

The main worker was terminated by the preregistered low-memory protection when sampled available physical memory fell below 768 MiB; this was not an evaluator exception. The 35 completed main instances had no failed per-instance checks. C01-C03 failed because the main run was interrupted. C05-C12 cannot be established for the full plan and are conservatively recorded as false; their false values do not by themselves show semantic violations. C04 holds for the 35 observed instances only. C13 passed the available snapshot checks; the interrupted instance has no post-instance record. Only one of the four preselected candidate-level artifacts exists. The remaining artifacts and full-grid family diagnostics are incomplete. No pilot or confirmation execution is authorized by this failure.

# SMOKE-02 report

Status: SMOKE_PASS for the 13 specified engineering invariants; 192/192 complete.
SMOKE-02 is an engineering and exploratory distribution check. It is not confirmation evidence for the research hypothesis.
No Gate A–E, bootstrap or significance test was performed.

| Family | Method | Agreement | Deadlock |
|---|---|---:|---:|
| F1 | B0 | 0 | 48 |
| F1 | B1 | 4 | 44 |
| F1 | B2 | 13 | 35 |
| F1 | O1 | 37 | 11 |
| F2 | B0 | 0 | 48 |
| F2 | B1 | 0 | 48 |
| F2 | B2 | 0 | 48 |
| F2 | O1 | 16 | 32 |
| F3 | B0 | 0 | 48 |
| F3 | B1 | 6 | 42 |
| F3 | B2 | 10 | 38 |
| F3 | O1 | 37 | 11 |
| F4 | B0 | 0 | 48 |
| F4 | B1 | 3 | 45 |
| F4 | B2 | 11 | 37 |
| F4 | O1 | 34 | 14 |

| Family | B1 deadlocks | Fraction | Resolution denominator nonzero |
|---|---:|---:|---|
| F1 | 44/48 | 0.916667 | True |
| F2 | 48/48 | 1.000000 | True |
| F3 | 42/48 | 0.875000 | True |
| F4 | 45/48 | 0.937500 | True |

Distribution review: DISTRIBUTION_REVIEW_REQUIRED.
O1 selected representative with structural novelty, instance count by family: {"F1": 32, "F2": 16, "F3": 36, "F4": 30}.
O1 any verified structural contract exists, instance count by family: {"F1": 37, "F2": 16, "F3": 37, "F4": 33}. These are instance counts, not candidate-contract counts.
O1 runtime median/p95/max seconds: 0.415853/1.80047/3.14589.
Paired runtime median/p95/max seconds: 0.744615/2.58317/3.22482.
These O1/paired timings are inside the evaluator call and exclude external guard and full orchestration. Guard wall time (guard_started to completed): 947.282 s.
Planned-stop segments: 0; actual memory-pause segments: 0; external prelaunch-wait records: 0 (records are not necessarily distinct pauses).
Peak observed Job child root-process OS peak working set: 762011648 bytes; orchestrator process peak was not measured.
Minimum sampled system available: 2227712000 bytes; estimated peak system physical used (physical total minus minimum sampled available): 14681354240 bytes.
Jobs: 76, all final Job ActiveProcesses=0: True. Memory/event sampling can miss transients.
Snapshot SHA256 c45633c085d0b0cac05564255db4f18552eb20c4cec06f4d0fcd846a3a4f9a9d; final verifier and per-instance checks passed. Guard completed without fatal/integrity termination; initial snapshot, authorization, formal-plan and preregistration hashes match. Planned pause segments and statuses: [('COMPLETE', None, 0, 192)].

## Preregistration protocol deviation

The frozen orchestrator did not record worker and orchestrator memory at each specified FAST stage. Its normal phase callback handled fault injection only; periodic system/worker sampling cannot reconstruct the missing stage-specific events. This execution did not satisfy that preregistered instrumentation requirement. The deviation does not change the C01–C13 results; the SMOKE_PASS label here applies to those 13 invariants only. Since the 13 invariants passed, the work may enter the PILOT-01 human review stage. The preregistered phase-memory recording deviation and any DISTRIBUTION_REVIEW_REQUIRED finding must be reviewed before a decision to proceed; this report does not authorize or establish readiness for direct PILOT execution.
C08 checks finite defined outputs and utilities reaching V5; internal undefined sentinel arrays are not claimed to contain no NaN.
PILOT and CONFIRM were not executed.

The same deviation also covers the required per-instance start/end and child-exit observations: complete worker and orchestrator RSS plus system-used/available samples were not recorded at those boundaries. The measured worker peak and system samples are periodic and cannot reconstruct these missing events.

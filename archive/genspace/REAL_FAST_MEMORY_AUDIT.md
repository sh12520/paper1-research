# Real FAST 32-instance memory audit

Status: PASS
Completed 32/32; exact reference matches 32/32.
Phase events complete: True; minimum event-sampled available physical bytes: 3228770304; wall time: 63.206 s.
Parent assigns each CREATE_SUSPENDED child to the Job before resuming it. Event-level sampling does not measure between-event instantaneous peaks.

| Phase | Count | Median worker RSS bytes | Max worker RSS bytes |
|---|---:|---:|---:|
| CHILD_PRE_EXIT | 8 | 409016320.0 | 410828800 |
| FAST_EVALUATION_COMPLETE | 32 | 449345536.0 | 452759552 |
| INSTANCE_COMPLETE | 32 | 408164352.0 | 410828800 |
| INSTANCE_START | 32 | 407646208.0 | 410918912 |
| LIBRARY_READY | 8 | 344082432.0 | 344424448 |
| PERSISTENCE_END | 32 | 408164352.0 | 410828800 |
| PERSISTENCE_START | 32 | 407504896.0 | 410918912 |
| PUBLIC_FILTER_END | 32 | 413233152.0 | 416505856 |
| PUBLIC_FILTER_START | 32 | 407646208.0 | 410918912 |
| REPRESENTATIVE_SELECTED | 32 | 450674688.0 | 565563392 |
| SERIALIZATION_END | 32 | 449345536.0 | 452759552 |
| SERIALIZATION_START | 32 | 449345536.0 | 452759552 |
| V4_END | 32 | 414216192.0 | 529313792 |
| V4_START | 32 | 413233152.0 | 416505856 |
| V5_END | 32 | 449073152.0 | 564170752 |
| V5_START | 32 | 414216192.0 | 529313792 |

| First index | Peak event RSS | Min event available | Available before exit | Available after exit |
|---:|---:|---:|---:|---:|
| 0 | 452759552 | 3359821824 | 3382390784 | 3777511424 |
| 4 | 527474688 | 3345088512 | 3488641024 | 3881111552 |
| 8 | 565563392 | 3367124992 | 3527602176 | 3916464128 |
| 12 | 452964352 | 3367133184 | 3555983360 | 3935739904 |
| 16 | 498008064 | 3327217664 | 3401920512 | 3973808128 |
| 20 | 501223424 | 3374534656 | 3846127616 | 3871272960 |
| 24 | 452337664 | 3466383360 | 3652173824 | 3966078976 |
| 28 | 489459712 | 3340689408 | 3411173376 | 3796045824 |

Complete lifecycle, Job Object and memory records: `results/windows_lifecycle_finalize_01/report.json`.

# Artifact-inclusive conditioned FAST engineering benchmark

This report supersedes summary-only `FAST_SCALING_03.md` for paired timing and planning. It is an ENGINEERING-only performance and determinism check, not a study result. The benchmark ran only after depth-1/depth-2 numeric differential and ULP-boundary checks, full-domain provider/private noninterference, and independent capability-conditioned all-class lexical witness checks were verified against the current execution snapshot. The machine-readable data are in `results/engineering/fast_scaling_04/report.json`.

## Setup

Twenty-four distinct pre-specified fixtures from `ENGINEERING_FIXTURE_PLAN_02.md` cover 4 families × 2 capability richness × 3 resource pressure; each cell uses one fixed conflict level and one ENGINEERING seed. All methods receive the same serialized instance; identical fixture files were reused for every worker count. This is not the complete 96-configuration research distribution.

Every fixture was executed via `run_paired(..., fast_library=..., candidate_layers_path=...)`: the O1 evaluator scans the 1,394,064-class rich graph as a superset, uses the exact public capability-conditioned mask and selected lexical witness, and writes the full per-class first-failure NPZ artifact, including B0/B1/B2 layer records. No heuristic top-K, random candidate truncation, or utility-guided candidate generation is used. The complete paired time includes this NPZ write and selected-contract JSON serialization; it excludes persistent writing of the later consolidated per-instance JSON/results CSV. Thus any real final output pipeline may incur additional I/O.

The prior same-session host and power inspection found Intel i5-11300H (4 physical/8 logical cores), 16,909,066,240 B RAM, Windows 11 Pro 64-bit build 10.0.26100, Balanced power plan `381b4222-f694-41f0-9685-ff5bb260df2e`. The evaluated runtime was CPython 3.12.14 and NumPy 2.3.5. OS/BLAS thread environment was limited to one per worker. No continuous whole-system load trace was collected; ordinary background load remained.

A fresh one-worker process loaded the graph in **0.5347 s** and preloaded all 17 conditioned indices in **0.8388 s**, with total `from_graph` wall time **1.4375 s**; first public feature binding added **2.1420 s**. The OS disk/page cache was not flushed, so this is not a cold-disk measurement. These one-time costs are outside warm per-instance timing. Prior graph construction took 198.097 s and 17-index construction 943.910 s, roughly **1,142.007 s sequential**, with any separate validation/serialization overhead to be accounted for separately.

## Warm single-worker phases

Seconds over 24 fixtures; p90/p95 use linear interpolation. Each phase's median is independent and must not be added.

| Phase | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|
| Instance deserialize/init | 0.0036 | 0.0063 | 0.0065 | 0.0075 |
| Public filter | 0.2973 | 0.3244 | 0.3287 | 0.3943 |
| Capacity and hard constraints | 0.3182 | 1.6816 | 2.2299 | 2.3418 |
| Private utility | 0.0114 | 0.0771 | 0.1539 | 0.2123 |
| Representative selection | 0.0021 | 0.0045 | 0.0056 | 0.0068 |
| Selected witness revalidation | 0.0020 | 0.0051 | 0.0053 | 0.0055 |
| B0 | 0.00052 | 0.00107 | 0.00117 | 0.00126 |
| B1 | 0.00432 | 0.00737 | 0.00788 | 0.00829 |
| B2 | 0.01554 | 0.02106 | 0.02477 | 0.02767 |
| O1, excluding class-artifact write | **0.6719** | **2.1030** | **2.7470** | **2.8812** |
| Class-layer NPZ construction/write | 0.0437 | 0.0637 | 0.0661 | 0.0707 |
| Result JSON serialization | 0.000267 | 0.000836 | 0.000891 | 0.001594 |
| Complete paired call including NPZ | **0.7582** | **2.1835** | **2.8244** | **2.9508** |

The warm O1 median is below the provisional 2-second threshold on this fixed engineering sample; p95 and max exceed 2 seconds. This is not a claim about the final study's outcome or a blanket readiness determination.

## Scaling, determinism and memory

| Workers | 24-fixture batch wall | Throughput | Worker CPU total | Peak individual worker RSS | Peak sampled aggregate worker RSS | Equality |
|---|---:|---:|---:|---:|---:|---|
| 1 | 30.0311 s | 0.7992 fixture/s | 28.3438 s | 759,005,184 B | 668,725,248 B | Repeat exact |
| 2 | 23.0506 s | 1.0412 fixture/s | 40.1406 s | 758,755,328 B | 1,337,372,672 B | 24 outputs and each worker repeat exact |
| 4 | Not run | — | — | — | — | Memory budget guard |
| 8 | Not run | — | — | — | — | Memory budget guard |

The equality test ignores only the four top-level per-method `runtime_seconds` timing fields, which were separately observed to be the sole repeat differences and remain available in stage timing. Every other canonical row field, including candidate counts, utilities, compiled actions, witness and labels, was compared byte-for-byte. Every generated class-layer NPZ was decoded and its full uint8 layer array and metadata string compared exactly; ZIP container timestamps were not used as equality criteria. SHA-256 values of canonical decoded content were recorded as reproducibility evidence in addition to direct equality. The earlier `fast_scaling_03` batch that compared timing fields was stopped as a mismatch and retained; `fast_scaling_03b` excluded artifact writing and is superseded here.

Individual peak RSS is a Windows process peak counter. Aggregate worker RSS and system physical use are sampled once per second and may miss brief peaks; sampled peak system physical use for two workers was **14,458,822,656 B**. Before 4/8 workers, available RAM was about **3.806 GB**; conservative estimates with a 1 GiB OS reserve were **5.323 GB / 9.572 GB**, so those batches were not started. There is no 4/8-worker throughput or equivalence claim.

## Compute projection — engineering planning only

| Workers | 192 SMOKE-equivalent tasks | 1,920 PILOT-equivalent tasks | 9,600 CONFIRM-equivalent tasks |
|---|---:|---:|---:|
| 1, projected wall | 4.00 min | 40.04 min | 200.21 min |
| 2, projected wall | 3.07 min | 30.73 min | 153.67 min |
| 4/8 | Not measured | Not measured | Not measured |

Projected aggregate worker CPU seconds are **226.8 / 2,267.5 / 11,337.5** for one worker and **321.1 / 3,211.3 / 16,056.3** for two. The linear projection uses batch wall time, including fresh-process loads/bind and a repeat per worker, over only the fixed 24-fixture mixture. It does not prove the runtime of the full 96-configuration grid and omits persistent consolidated CSV writing; no projection is an authorization to run the study. Measured RSS values above are not guaranteed future upper bounds.

No SMOKE, PILOT or CONFIRM seed was read/generated; no `FROZEN_CONFIG.yaml` was created. Snapshot/model/index/graph compatibility and final blockers are reported separately in `EXECUTION_SNAPSHOT_FINGERPRINT.json` and `PRE_PILOT_CHECKLIST.md`.

# FAST engineering scaling — ORACLE-RUNTIME-CLOSE-02

This is an ENGINEERING-only timing and determinism check, not a smoke, pilot, confirmation, or result about the research hypothesis. The report and per-worker engineering outputs are under `results/engineering/fast_scaling_02/`. The measured path uses the actual `run_paired(..., fast_library=...)` dispatch and scans all 1,394,064 semantic records for each depth-2 fixture. The complete depth-1, depth-2 and ULP-boundary differential reports passed before this measurement and are bound to the same execution snapshot and graph through `results/engineering/fast_differential_provenance.json`.

## Setup and coverage

Twenty-four distinct serialized fixtures followed `ENGINEERING_FIXTURE_PLAN_02.md`: 4 families × 2 richness levels × 3 pressure levels, one predetermined preference-conflict value and one ENGINEERING seed label per cell. Exactly the same serialized fixture files were reused for each worker count. This broadens family/richness coverage relative to the legacy baseline but is not the full 96-configuration research distribution; projections below are rough engineering planning estimates, not study outcomes.

Post-run system inspection reported Intel i5-11300H, 4 physical/8 logical cores, 16,909,066,240 bytes physical RAM, Windows 11 Pro 64-bit build 10.0.26100, CPython 3.12.14, NumPy 2.3.5 and Balanced power plan `381b4222-f694-41f0-9685-ff5bb260df2e`. These host/power details were sampled after the run; they are not a continuous in-run telemetry record. The snapshot records the exact dependency versions. Other normal OS activity remained. Worker library loads are fresh-process reads with the OS page/disk cache uncontrolled; the graph is not memory-mapped and each worker has its own in-memory copy. BLAS/OpenMP environment thread limits were set to one.

## Warm single-worker timings

A single worker completed all 24 fixtures with warm library reuse; below are seconds and linear-interpolation percentiles. The graph read once in the fresh worker took 0.7182 s; subsequent one-time public feature binding took 5.7373 s. Both are **outside** the warm per-instance values. Prior graph construction took 198.097 s and is not repeated per instance.

| Phase | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|
| Instance deserialize/init | 0.0051 | 0.0067 | 0.0070 | 0.0086 |
| Public filtering | 0.3264 | 0.4071 | 0.4181 | 0.4265 |
| Capacity/hard constraints | 0.3765 | 1.8243 | 2.3093 | 2.4510 |
| Private utility | 0.0135 | 0.1057 | 0.1245 | 0.1316 |
| Representative selection | 0.0016 | 0.0038 | 0.0041 | 0.0200 |
| B0 | 0.0008 | 0.0011 | 0.0012 | 0.0013 |
| B1 | 0.0058 | 0.0088 | 0.0102 | 0.0109 |
| B2 | 0.0182 | 0.0255 | 0.0259 | 0.0272 |
| O1 | **0.7543** | **2.3577** | **2.7637** | **2.8867** |
| Result serialization | 0.000058 | 0.000126 | 0.000133 | 0.000161 |
| Complete paired run | **0.7983** | **2.4044** | **2.8079** | **2.9240** |

Phase medians are calculated separately and must not be added. For this fixed 24-fixture engineering set, the measured warm O1 **median** meets the tentative <2 s threshold; its p95 and max exceed 2 s. This does not establish the remaining validation, compatibility, or pre-smoke gates.

## Worker scaling and repeatability

| Workers | Batch wall seconds | Fixtures/s | Aggregate worker CPU seconds | Peak individual worker RSS | Peak sampled sum of worker RSS | Exact outputs |
|---|---:|---:|---:|---:|---:|---|
| 1 | 33.038 | 0.7264 | 31.797 | 631,525,376 B | 514,076,672 B | Same-worker repeat identical |
| 2 | 24.039 | 0.9984 | 42.938 | 631,160,832 B | 972,357,632 B | All 24 outputs byte-identical to 1 worker; each worker repeat identical |
| 4 | Not run | — | — | — | — | Insufficient available-memory budget |
| 8 | Not run | — | — | — | — | Insufficient available-memory budget |

The peak individual value comes from the Windows process peak counter, whereas the aggregate sum is sampled once per second and can miss short spikes; they are different measurements. The sampled peak system physical-memory use was 14,703,136,768 bytes in the 2-worker batch. Before the 4/8-worker batches, available physical memory was approximately 3.16 GB; conservative budgets including a 1 GiB OS reserve were approximately 4.61 GB and 8.14 GB respectively. They were skipped rather than simulated. Batch wall times and throughput include fresh worker startup, library loading/binding and one repeated fixture per worker, so they are conservative measurements for a long-lived worker and do not predict steady-state scaling precisely.

## Compute projection, not a research outcome

| Workers | 192 SMOKE-equivalent tasks | 1,920 PILOT-equivalent tasks | 9,600 CONFIRM-equivalent tasks |
|---|---:|---:|---:|
| 1: projected wall | 4.41 min | 44.05 min | 220.25 min |
| 2: projected wall | 3.21 min | 32.05 min | 160.26 min |
| 4 / 8 | Not measured | Not measured | Not measured |

The corresponding projected aggregate worker CPU times for 1 worker are 254.4 s, 2,543.8 s and 12,718.8 s; for 2 workers they are 343.5 s, 3,435.0 s and 17,175.0 s. These linear projections scale observed batch throughput, not per-instance median. They include repeated startup/binding and repeat checks in the observed 24-fixture batches and assume the engineering mix and available resources remain representative; neither assumption is established for the actual 96-configuration grid. There is no 4/8-worker projection. The sampled aggregate RSS values above are observations, not guaranteed upper memory bounds.

No SMOKE, PILOT or CONFIRM seeds were accessed; no `FROZEN_CONFIG.yaml` was created. The exact scope and any remaining blockers are in `PRE_PILOT_CHECKLIST.md`, and the complete timing, fixture hashes, exact output comparison, differential report hashes and execution fingerprint are in the machine-readable report.

## Historical status after conditioned witness correction

This summary-only, rich-global-witness performance run predates the capability-conditioned lexical witness correction and omitted per-class first-failure artifact writes. It is historical engineering evidence, not the final conditioned execution or paired runtime. The authoritative later 24-fixture artifact-inclusive benchmark is `FAST_SCALING_04.md`; it includes full stage median/p90/p95/max, separate graph/17-index cold loading and warm reuse, 1/2-worker scaling and memory-guarded 4/8 skips, and planning-only projections. No study seed namespace was used by that run.

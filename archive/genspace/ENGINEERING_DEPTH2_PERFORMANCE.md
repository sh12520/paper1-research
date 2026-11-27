# Depth-two engineering runtime audit

Status: **20 engineering fixtures measured under concurrent load.** This is an engineering timing check, not a smoke, pilot, confirmation or research outcome. The packed evaluator is experimental and its reduced-domain differential test is not proof of full-graph correctness. Independent full depth-two reference validation remains a separate gate.

One rich-capability fixture in namespace `GENSPACE-FAIL-01-ENGINEERING` was scanned over all 1,394,064 records of `results/engineering/semantic_library.graph.gz`, SHA-256 `11e84c86d15e58f64d8dcfc892e22a813cf1250c835a9d48fa96f22ea112f6fd`. Timing data and the engineering instance hash are in `results/engineering/depth2_single_full.json`. No pilot or confirmation seeds were generated for this measurement.

| Measured component | Seconds |
|---|---:|
| Graph loading, once | 2.256 |
| O1 public filtering | 7.196 |
| O1 V3–V4 checks | 36.850 |
| O1 V5 and selection | 39.457 |
| O1 complete record scan, wall time | 84.866 |
| B0/B1/B2 baseline, total | 0.028 |
| Paired scan plus baselines | 84.893 |

The O1 scan timer excludes graph loading and per-instance evaluator initialization, so it understates end-to-end time. Per-stage timers are accumulated for each record and add timing overhead. The single-fixture scan above was concurrent with the independent reference workers.

## Twenty-fixture audit

Twenty distinct engineering fixtures were measured by two parallel worker processes while the independent reference audit and other processes were active. Both completed normally; indices were unique and peak observed worker RSS was 329,015,296 bytes. Each process loaded the graph once (2.283 and 2.434 seconds respectively). The helper and graph SHA-256 fingerprints matched before and after the run. Full per-fixture records and fingerprints are in `results/engineering/depth2_performance_20.json` and `results/engineering/depth2_runtime_environment.json`.

| Stage | Median seconds | Range seconds |
|---|---:|---:|
| Per-instance initialization | 0.0010 | 0.0006–0.0098 |
| Public filtering | 4.853 | 0.805–9.223 |
| V3–V4 | 6.702 | 0.0004–45.538 |
| V5 and representative selection | 0.306 | 0–57.668 |
| O1 record scan, total | **13.284** | 1.099–110.306 |
| B0/B1/B2, total | 0.019 | 0.013–0.030 |
| Paired methods including initialization | 13.303 | 1.114–110.331 |

The stage medians are computed independently and should not be summed. The observed O1 median exceeds the tentative 2-second threshold, but these are concurrent-load measurements and are not a controlled idle-machine benchmark. Regardless, the pre-smoke gate is not established. No optimization or result-dependent model change is implied.

Including per-instance evaluator initialization, the complete O1 median is **13.2849 s** (range **1.0998–110.3071 s**); graph loading is separately amortized across each worker. The packed implementation remains subject to the complete independent reference audit and deeper differential verification.

## ORACLE-RUNTIME-CLOSE-02: quiet FAST paired-path follow-up

The later 24-fixture ENGINEERING-only benchmark measured the actual `run_paired(..., fast_library=...)` path after full depth-1/depth-2 F1–F4 differential and ULP-boundary checks passed on the same execution snapshot. The 1-worker warm O1 median was **0.7543 s**, p90 **2.3577 s**, p95 **2.7637 s** and max **2.8867 s**. Complete paired-run median was **0.7983 s**, p95 **2.8079 s**. The warm O1 median meets the tentative <2 s threshold on this engineering set; that fact alone does not close other pre-smoke gates. A fresh-process graph read took **0.7182 s**, with first public-feature binding **5.7373 s** separately; OS file cache was not flushed. The earlier legacy quiet baseline is documented in `QUIET_BASELINE_02.md`.

For the 24 fixed cross-family/richness/pressure fixtures, measured batches were **33.038 s / 0.7264 fixtures/s** with one worker and **24.039 s / 0.9984 fixtures/s** with two. Full serialized outputs were byte-identical across worker counts and same-worker repeats. Peak individual worker RSS was 631,525,376 B and 631,160,832 B respectively; sampled peak aggregate worker RSS was 514,076,672 B and 972,357,632 B. The 4- and 8-worker batches were not started because the available-memory budget, including a 1 GiB OS reserve, was insufficient. Do not infer their throughput or determinism.

Scaling measured batch throughput linearly gives planning-only wall estimates for SMOKE-equivalent 192, PILOT-equivalent 1,920 and CONFIRM-equivalent 9,600 tasks: **4.41/44.05/220.25 min** at one worker and **3.21/32.05/160.26 min** at two. Aggregate CPU estimates respectively are **254.4/2,543.8/12,718.8 s** and **343.5/3,435.0/17,175.0 s**. These include fixed batch setup/repeat overhead, and the 24-fixture set is not the full 96-configuration distribution. They are not research outcomes or approved runs.

For the full per-stage median/p90/p95/max table, CPU and RAM methodology, fingerprint and fixture-coverage limits, see `FAST_SCALING_02.md` and `results/engineering/fast_scaling_02/report.json`. No SMOKE, PILOT or CONFIRM seed was accessed by the scaling run.

## Artifact-inclusive conditioned FAST follow-up

The later `FAST_SCALING_04.md` benchmark supersedes the 03/03b summary-only timing above. It writes the complete per-class first-failure NPZ per engineering fixture and compares decoded class arrays and metadata exactly. Its 1-worker warm O1 median/p95/max were **0.6719/2.7470/2.8812 s**; complete paired-call median/p95 including NPZ were **0.7582/2.8244 s**. One/two worker wall times for 24 fixtures were **30.031/23.051 s**; four/eight workers were not started due to memory budget. See the full report for cold graph/17-index/binding costs, all stage percentiles, fingerprints, exact-output checks, sampling limits, and planning projections. No study namespace was used.

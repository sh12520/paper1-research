# Conditioned FAST scaling — ORACLE-RUNTIME-CLOSE-02

This engineering-only report supersedes the previous rich-witness FAST timing in `FAST_SCALING_02.md`. Before execution, the harness checked the current snapshot, the complete depth-1/depth-2 numerical differential, ULP-boundary regression, full-domain provider/private noninterference checks, and independent capability-conditioned full syntax/witness references for all four engineering families plus the static-only negative control. These checks are scoped to the documented finite benchmark. No SMOKE, PILOT or CONFIRM seed was accessed, and no study outcome was calculated.

## Fixture, environment and timing boundaries

The 24 ENGINEERING fixtures use the pre-specified `ENGINEERING_FIXTURE_PLAN_02.md` cross of 4 families × 2 richness × 3 pressure levels, with one conflict level and one seed per cell. The same serialized fixture files were used in each worker batch. The host was Intel i5-11300H (4 physical/8 logical cores), 16,909,066,240 bytes RAM, Windows 11 Pro 64-bit build 10.0.26100, CPython 3.12.14, NumPy 2.3.5, with Balanced power plan sampled in the earlier same-session environment inspection. Worker threads for OpenMP/BLAS were limited to one. OS/disk page cache was not flushed; source/config/dependency, graph, index manifest and helper hashes were verified unchanged during this benchmark.

The first loading in the 1-worker process took **1.5261 s** total: internally graph load was **0.6844 s**, all 17 conditioned-index loads **0.8074 s**, with small remaining overhead. One-time public feature binding then took **2.3157 s**. These are fresh-process times, not controlled cold-disk times. The graph and all indices were reused for all warm per-instance timings. Prior independent graph and 17-index construction took 198.097 s and 943.910 s respectively (approximately 1,142.007 s sequential), excluding separately recorded validation/serialization work; this one-time construction is not included in the per-instance warm values.

## Single-worker warm timing

The table reports seconds over the 24 fixed fixtures, using linear interpolation for p90/p95. Individual stage medians are not additive. O1 evaluates the rich graph as a scan superset and uses the exact conditioned availability mask; it does not truncate, top-K rank or generate based on private utility. It reconstructs and revalidates one selected witness. The measured complete paired call includes baseline methods, final selected action schedule and result JSON serialization. **It does not write the optional full per-class first-failure NPZ artifact**, so it is not a measurement of that additional output path.

| Phase | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|
| Instance deserialize/init | 0.0041 | 0.0060 | 0.0062 | 0.0075 |
| Public filtering | 0.3148 | 0.3452 | 0.3478 | 0.4223 |
| Capacity/hard constraints | 0.3492 | 1.7393 | 2.2586 | 2.7570 |
| Private utility | 0.0116 | 0.0841 | 0.1241 | 0.1513 |
| Representative selection | 0.0018 | 0.0042 | 0.0050 | 0.0222 |
| Selected witness validation | 0.0016 | 0.0041 | 0.0042 | 0.0042 |
| B0 | 0.00055 | 0.00091 | 0.00096 | 0.00123 |
| B1 | 0.00432 | 0.00754 | 0.00836 | 0.01149 |
| B2 | 0.01326 | 0.02229 | 0.02596 | 0.03261 |
| O1 | **0.6663** | **2.2177** | **2.7295** | **3.2268** |
| Result JSON serialization | 0.000289 | 0.000973 | 0.001463 | 0.001658 |
| Complete paired call, no NPZ output | **0.6986** | **2.2615** | **2.7621** | **3.2654** |

The tentative <2 s warm O1 **median** is met on this fixed 24-fixture engineering sample; p95 and maximum exceed 2 s. These numbers do not on their own establish complete pre-pilot readiness or end-to-end cost with every requested artifact.

## Worker scaling and deterministic research fields

| Workers | 24-fixture wall | Throughput | Worker CPU total | Peak single-worker RSS | Peak sampled aggregate RSS | Result |
|---|---:|---:|---:|---:|---:|---|
| 1 | 30.0350 s | 0.7991 fixture/s | 28.7031 s | 757,964,800 B | 656,187,392 B | Same-worker repeat equal |
| 2 | 22.0337 s | 1.0892 fixture/s | 38.2813 s | 757,186,560 B | 1,306,558,464 B | All 24 outputs match 1 worker; both same-worker repeats equal |
| 4 | Not run | — | — | — | — | Memory budget guard |
| 8 | Not run | — | — | — | — | Memory budget guard |

Per-method `runtime_seconds` naturally changes between repetitions and was excluded from the equality comparison after the failed first batch and a field-level diagnostic found those four fields were the only differences. Every other row field, including instance/public/private hashes, candidate counts, utilities, compiled actions, selected witness and labels, was serialized canonically and compared byte for byte. Timing values remain separately recorded. The first `fast_scaling_03` batch, which treated those timings as deterministic, was stopped as a mismatch and remains intact; the corrected, separately fingerprinted run is `fast_scaling_03b`.

The individual worker figure is the process peak counter; aggregate worker RSS and system physical use were sampled once per second and may miss spikes. Peak sampled system physical use in the two-worker batch was **14,486,999,040 B**. For 4/8 workers, available physical memory was approximately **3.717 GB**, while the conservative estimates including a 1 GiB OS reserve were **5.314 GB** and **9.554 GB**; neither was launched. No output equivalence or throughput is claimed for those unrun worker counts.

## Compute projection — planning only

The following scales observed 24-fixture batch throughput, which includes fresh process startup, library/index loading and binding, plus one repeated fixture per worker. It excludes optional per-class artifact I/O. It is not an estimate validated against all 96 configurations, and does not authorize a research run.

| Workers | SMOKE 192 tasks | PILOT 1,920 tasks | CONFIRM 9,600 tasks |
|---|---:|---:|---:|
| 1: projected wall | 4.00 min | 40.05 min | 200.23 min |
| 2: projected wall | 2.94 min | 29.38 min | 146.89 min |
| 4 / 8 | Not measured | Not measured | Not measured |

Projected aggregate worker CPU times are 229.6 / 2,296.3 / 11,481.3 seconds for one worker and 306.3 / 3,062.5 / 15,312.5 seconds for two. Memory observations are from the table above and are not guaranteed future upper bounds. These estimates are subject to engineering fixture mix, OS load, output requirements and hardware state.

The machine-readable report is `results/engineering/fast_scaling_03b/report.json`. The source snapshot remains a compatibility record, not `FROZEN_CONFIG.yaml`; any later source, dependency, configuration, graph or index change requires renewed verification. Remaining gate decisions are in `PRE_PILOT_CHECKLIST.md`.

The artifact-inclusive conditioned benchmark in `FAST_SCALING_04.md` supersedes the summary-only timing in this document. In particular, the prior paired-call and projections did not include per-class layer NPZ output.

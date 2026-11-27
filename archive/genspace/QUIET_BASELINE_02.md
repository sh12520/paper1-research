# QUIET-BASELINE-02 — legacy packed evaluator

This is an engineering-only baseline, not a study result and not evidence that the packed evaluator is exact. Twenty distinct `GENSPACE-FAIL-01-ENGINEERING` instances each scanned the full **1,394,064** graph records with one worker. No SMOKE, PILOT or CONFIRM seed was generated or read. Timing data and complete before/after fingerprints are in `results/engineering/quiet_baseline_02.json`.

No competing Python performance or enumeration process was running at the start or at the interim process check. Normal OS/background activity remained: Win32 CPU load samples were 26% at start and 33% at end; no continuous system-load trace was captured. This is a quiet engineering run, not a fully isolated or controlled idle machine. Host: Intel Core i5-11300H, 4 physical/8 logical cores, 16,909,066,240 bytes physical RAM, Windows 11 Pro 64-bit build 10.0.26100, CPython 3.14.4, Python standard-library runtime dependencies, Balanced power profile GUID `381b4222-f694-41f0-9685-ff5bb260df2e`, one worker. The machine-readable JSON's OS Caption/architecture localized text suffered an output-encoding error; the caption and architecture above were independently read from PowerShell at baseline start. CPU name, build, numeric RAM and power GUID were not affected.

The first graph read in a fresh process took **2.0641 s**; the operating-system file cache was not flushed, so this is a process-cold load, not a controlled cold-disk measurement. All per-instance rows below use the same in-memory library; warm load is zero by reuse, not a timed repeated filesystem read. The graph was built once in the earlier engineering audit in **198.097 s**, separately from this baseline. The measured peak process working set was **329,531,392 bytes**; peak system RAM use was not continuously measured.

| Warm phase, seconds | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|
| Instance deserialization + evaluator initialization | 0.0012 | 0.0022 | 0.0026 | 0.0032 |
| Public filtering | 5.6371 | 6.3782 | 6.5508 | 6.6181 |
| Capacity and hard constraints | 7.1443 | 31.0111 | 33.1463 | 33.8173 |
| Private utility and acceptance | 0.3157 | 33.8464 | 39.1862 | 39.9605 |
| Representative selection | 0.0067 | 1.1661 | 1.2007 | 1.8576 |
| B0 | 0.0005 | 0.0011 | 0.0012 | 0.0012 |
| B1 | 0.0036 | 0.0081 | 0.0083 | 0.0084 |
| B2 | 0.0114 | 0.0225 | 0.0258 | 0.0311 |
| O1 loop wall time | **14.2851** | **76.8040** | **78.4146** | **79.9666** |
| Result serialization proxy | 0.0006 | 0.0009 | 0.0010 | 0.0016 |
| Complete paired-loop proxy | **14.3018** | **76.8217** | **78.4328** | **79.9828** |

The complete paired-loop proxy includes deserialization, evaluator initialization, the full O1 loop, B0/B1/B2 and timing-metadata JSON serialization. It does **not** persist a full research result record or include a production runner's output overhead, and cold graph load is excluded. The result serialization measurement is a metadata proxy, not full production-result serialization. Individual phase timings call the clock per candidate and incur instrumentation overhead; phase medians are independently computed and should not be added. Percentiles use linear interpolation at `(n-1)*p`. This baseline does not establish the faster evaluator's performance or exact equivalence.

## Fixture and provenance limits

The legacy `make_fixtures` set couples family to richness: F1/F3 are rich and F2/F4 sparse. It does not cover the full family×richness design or all 96 configurations, and the measured median is not a validated projection of their run time. The separately specified `ENGINEERING_FIXTURE_PLAN_02.md` fixes a 24-instance cross-family/richness/pressure follow-up set before optimized timings are observed; it also states its own coverage limits.

The complete source-tree fingerprint changed during measurement because other agents added optimization modules/tests and changed `src/runner.py` and `tests/test_runner_semantic.py`; the JSON correctly records different before/after hashes. Those changes were not imported by this legacy baseline. The baseline's actual imported application paths (`src/engineering_depth2.py`, `src/compact_semantics.py`, `src/instances.py`, `src/models.py`, `src/registry.py`, `src/state_machine.py`, `src/engine.py`, `src/enumeration.py`, `src/fingerprints.py`) had matching individual SHA-256 hashes before and after. Config hash, Python/dependency fingerprint, graph SHA-256, and this baseline helper SHA-256 also matched. This supports the scoped baseline provenance but is not a full-tree fingerprint match and does not establish compatibility of the subsequent FAST implementation.

The later FAST benchmark and worker-scaling results are reported separately in `FAST_SCALING_02.md`. The legacy baseline above remains useful as a historical reference; its fixture coverage and per-record timing instrumentation differ from the FAST follow-up and should not be treated as an identical-sample paired speedup estimate.

The final conditioned FAST benchmark is `FAST_SCALING_04.md`. Unlike this historical legacy baseline and the intermediate summary-only FAST measurements, it includes writing the full per-class first-failure NPZ artifact for each of 24 ENGINEERING fixtures; it reports cold graph plus 17-index loading, warm per-stage median/p90/p95/max, 1/2-worker timings and memory-guarded 4/8-worker skips. Its study-size compute projections are engineering planning only. This historical baseline remains unchanged and must not be used as the final conditioned runtime.

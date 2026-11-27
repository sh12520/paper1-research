# Search cost accounting — FLAT-BASELINE-AUDIT-01

This is a development-data diagnostic, not confirmatory evidence. No benchmark instances, research seeds, or new method outputs were generated for this accounting. The source records and method are unchanged. `results/flat_audit/scaling_record_audit.py` extracts the reported per-instance quantities from the 1,920 existing `results/method_dev_v1/run_protocol_fixed/*/record.json` files without importing benchmark modules. The 1,920-row `results/flat_audit/scaling_record_extract.csv` is the machine-readable cross-check. Sorted-input fingerprint: `6fbeac202a2124e34ff1b35d7a421873e350458fe1f3314d5ad18cc98c811464`; extract SHA-256: `daa115fa381bb987e0f9b9987492c269c8a1d0708e80d2d46e1a1fd9b86386e8`.

## Counts with distinct meanings

The following are observed **B=5,000 checkpoint** values from original records; percentiles use linear interpolation. The 842-instance target is B2 no agreement / full O1 agreement. Calls include 27 static B2 exact checks and are checked in blocks of up to 16; they are not the rank of the first acceptable class.

| Population | N | FLAT public structural candidates scored, median / p95 | FLAT exact calls, median / p95 | GLOBAL scored, median / p95 | GLOBAL exact calls, median / p95 |
|---|---:|---:|---:|---:|---:|
| Target | 842 | 1,512 / 1,252,611 | 43 / 43 | 1,512 / 1,252,611 | 43 / 171 |
| All | 1,920 | 1,512 / 1,252,611 | 43 / 5,000 | 1,512 / 1,252,611 | 43 / 5,000 |

`public_ranked_count` counts the capability/depth-conditioned structural candidates with one or two mechanism groups passed through `_proxy` and sorted, not all typed ASTs, not a count of validated contracts, and not the number of exact verification calls. The separate static-proxy computation covers 27 profiles when a plan is made. The scored structural count divided by the recorded capability/depth-conditioned O1 candidate count has target median/p95 94.0609% / 98.2456%; all-instance values are 89.8532% / 99.9351%. The denominator includes the 27 static semantics, so this is not the fraction of a purely structural set. Among all 1,920, 330 B2 agreements stop before structural scoring, giving zero structural scored; none of the 842 targets does so.

Zero structural scores do **not** mean zero library work. `results/method_dev_v1/runtime.py` calls `group_bits(library)` over all 1,394,064 graph rows to find the B2 static classes before B2 can succeed. If B2 fails, `results/method_dev_v1/public_search.py:make_plan` calls it again, constructs capability/depth masks, scores every surviving one/two-group structural ID, and performs `np.lexsort` on that set. Thus each method invocation reads full-graph role metadata at least once; expansions do so at least twice. These are graph metadata scans, not 1,394,064 public proxy scores or exact calls. The graph can be resident and its construction amortized; this does not eliminate per-invocation vector passes. FLAT and GLOBAL both use the same public proxy/sort universe; GLOBAL subsequently reorders by fixed O/P/C/D groups and applies stage quotas in the common protocol. DG also performs public mechanism probes, separately counted from structural scoring. Reports that count only exact calls omit substantial public work.

## GLOBAL versus FLAT on recoverable target

Agreement-set cross-tabulation in the existing records, each row summing to 842:

| Budget | Both | FLAT only | GLOBAL only | Neither | GLOBAL selected class has O bit / GLOBAL successes |
|---:|---:|---:|---:|---:|---:|
| 100 | 781 | 42 | 12 | 7 | 783 / 793 |
| 500 | 830 | 11 | 0 | 1 | 812 / 830 |
| 5,000 | 841 | 1 | 0 | 0 | 823 / 841 |

The O bit records the selected contract's capability footprint. A post-hoc replay reconstructs GLOBAL's quota-truncated structural verification sequence. The first mutually acceptable ordinal is conditional on success at the listed budget and excludes the 27 B2 checks. In all 841 successful target runs at B=5,000, the first mutually acceptable candidate actually checked was also the selected candidate. Each successful earlier checkpoint selected that same class, and its verification budget covered the observed ordinal. The grouped rank below is the position of that candidate in the full public order, including candidates skipped by quotas. Acceptance of the skipped candidates remains unknown. The grouped order matched the original `make_plan` candidate order on eight family/depth fixtures. The replay checked original stage sizes and public-feasible counts on all 842 targets.

| Budget | Successful n | First mutual actual ordinal median / p95 / p99 / max | Selected full grouped rank median / p95 | O footprint among successes |
|---:|---:|---:|---:|---:|
| 100 | 793 | 1 / 7 / 10 / 46 | 1 / 7 | 783/793 (98.74%) |
| 500 | 830 | 1 / 10 / 338 / 419 | 1 / 10 | 812/830 (97.83%) |
| 5,000 | 841 | 1 / 129 / 1,938 / 3,538 | 1 / 811 | 823/841 (97.86%) |

Per-budget joins and the exact quantile code are in `results/flat_audit/global_budget_diagnostics.csv` and `global_budget_diagnostics.py`. FLAT and GLOBAL each perform at least two full role-metadata scans on all 842 targets and score the same complete conditioned structural universe, independently of the exact-verification budget; neither quantity is the first-success ordinal.

## Offline versus online and scaling

`SEMANTIC_ENUMERATION_AUDIT.md` and `EXTERNAL_REFERENCE_AUDIT.md` report exact rich fixed-domain counts: depth≤1 1,566 syntax / 1,539 semantics; depth≤2 4,909,437 syntax / 1,394,064 semantics, with the depth2 unique sets compared byte-for-byte. `ENUMERATION_AUDIT.md` gives depth≤3 syntax **48,205,158,042,276**, not a semantic count. Syntax ratio depth2/depth1 ≈3,135 and depth3/depth2 ≈9,818,877; depth2/depth1 exact semantic ratio ≈905.8. These grammar counts include legal syntax without claiming acceptance.

The offline depth≤2 compact semantic graph was built in 198.097 s and serialized in another 12.211 s; gzip graph size 7,464,460 bytes and observed process peak RSS 358,879,232 bytes at precompute end. That RSS does not cover the subsequent serialization peak. Before compression, 1,394,064 × (49-byte key + 7-byte witness) = 78,067,584 bytes, excluding header and runtime indices. `FAST_SCALING_04.md` also reports 17-index construction 943.910 s; a fresh prior-engineering worker's graph/index loading 1.4375 s plus 2.1420 s first public binding, and peak worker RSS 759,005,184 bytes for an artifact-inclusive O1 paired path. That memory measurement is **not** an isolated FLAT-only working-set measurement; report-specific runtime and fixture conditions apply.

For the online scan, a single-process measurement ran the unmodified FLAT public plan on the existing rich depth2 target `F1__medium__medium__rich__d2__s0`. It scored and sorted 1,252,611 candidates, matching the original B=5,000 record. After graph load and binding the current working set was 405,827,584 bytes (387.0 MiB). The Windows process peak working set increased from 527,060,992 to 559,337,472 bytes (533.4 MiB) during the public plan. The maximum of 73 in-plan samples agreed with that endpoint high-water mark. It includes the resident interpreter, library and indices and is a single-fixture process measurement. The separate instrumented 96-configuration FLAT/DG replay reached 634,060,800 bytes (604.7 MiB) in its shared process. The isolated record and script are `results/flat_audit/flat_scan_working_set.json` and `measure_flat_scan_working_set.py`.

For a hypothetical full score scan of S semantic classes, the fixed six-cell benchmark requires S candidate score evaluations and Θ(S) scan work. Materialized comparison sorting has an approximate Θ(S log S) work model and the resident ranking arrays scale as Θ(S). Full depth1 and depth2 would therefore require 1,539 and 1,394,064 candidate score evaluations respectively, about a 906× increase. At a fixed 56 bytes per packed record, uncompressed graph payload increases from 86,184 to 78,067,584 bytes. The S log₂S model gives a sort-work ratio of about 1,746×. The current implementation also passes over all 1,394,064 graph rows for role metadata on each shallow fixture.

At depth3, write S₃ for the unknown unique semantic count. A full semantic scan would require S₃ scores and Θ(S₃) scan work. If a depth3 format could retain the same packed record width, its payload would be 56S₃ bytes before indices and runtime arrays. As an illustrative uncollapsed syntax scenario, scoring all 48,205,158,042,276 trees would require that many scores and about 2.70 PB at an assumed 56 bytes per record. This arithmetic describes the cost of the stated scenario. The diagnostic provides neither an exact depth3 semantic count nor a measured depth3 runtime or storage footprint.

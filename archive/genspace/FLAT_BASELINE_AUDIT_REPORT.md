# FLAT baseline audit — development-data diagnostics

This analysis uses the 1,920 preserved PILOT instances and their original V1 development records. The primary cohort is the 842 existing B2-deadlock / full-O1 agreement instances. No new benchmark instance or research seed is generated, and all private acceptance checks in the rank audit are post-hoc diagnostics, never ranking inputs. These are not confirmatory results.

The previous V1 development result remains `METHOD_WEAK_V1`: at B=5,000, FLAT recovered all 842 target instances and DG-PCE recovered 841. The audit distinguishes the availability-conditioned candidate universe, actual online graph metadata passes, public feature/score/sort work, and exact verification; a graph metadata touch is not counted as a proxy score or a verifier invocation.

## Observed cost and ranks

| Cohort | N | Public conditioned candidates median / p95 | Actual scored median / p95 | Exact calls median / p95 |
|---|---:|---:|---:|---:|
| B2 deadlock / O1 agreement | 842 | 1,512 / 1,252,611 | 1,512 / 1,252,611 | 43 / 43 |
| All | 1920 | 1,512 / 1,252,611 | 1,512 / 1,252,611 | 43 / 5,000 |

FLAT and GLOBAL both read the metadata of all 1,394,064 rich depth≤2 semantic classes once before B2; B2 failure triggers a second full metadata pass. Among all 1,920 instances, 330 stop at B2 and score no structural classes. The conditional universe column is the public availability/depth domain even for such early stops; it is not a claim these classes were scored online. Each full proxy count excludes 27 separate static-profile proxy evaluations when the structural plan is built. Exact counts include the 27 B2 checks and batched structural checks.

For the 842 targets at budget 5,000, median/p95 exact FLAT verification calls are 43/43, while median/p95 structural candidates scored are 1,512/1,252,611. See [SEARCH_COST_ACCOUNTING.md](SEARCH_COST_ACCOUNTING.md) and the machine-readable per-instance accounting. Rank is one-based within the conditioned structural FLAT order, and remains an offline private-acceptance diagnostic. See [FLAT_SUCCESS_RANK_ANALYSIS.md](FLAT_SUCCESS_RANK_ANALYSIS.md) and [FLAT_TOPK_COMPOSITION.md](FLAT_TOPK_COMPOSITION.md).

## GLOBAL-FREQUENCY comparison

| B | Both succeed | FLAT only | GLOBAL only | Neither |
|---:|---:|---:|---:|---:|
| 100 | 781 | 42 | 12 | 7 |
| 500 | 830 | 11 | 0 | 1 |
| 5,000 | 841 | 1 | 0 | 0 |

GLOBAL also evaluates and sorts all conditionally eligible structural candidates, before group rearrangement and group-stage quotas. OFFLOAD-bearing selections are 783/793, 812/830 and 823/841 successes, respectively. Role footprint is not a causal attribution.

## Interpretation and boundary

**Diagnostic classification: `FULL_SCAN_BOTTLENECK`.** The present FLAT implementation scans all rich-graph role metadata before B2 and again when B2 fails, and scores and sorts the complete eligible public domain during expansion. In the target cohort, the eligible domain and scored counts have median/p95 1,512 / 1,252,611. Scored structural records amount to approximately 0.1085% / 89.8532% of the full 1,394,064-record graph at those quantiles; the complete graph's role metadata is nevertheless scanned at least once per invocation. In the 37 target instances in the independent 96-configuration timing sample, FLAT feature calculation, conditioning, score calculation and sorting account for 76.22%, 14.53%, 1.97% and 5.57% of aggregate timed work, respectively. The 37-instance target sample is not the entire 842-instance cohort, and these aggregate time shares are weighted by duration rather than describing the median instance. The median case is relatively cheap, whereas rich depth-2 cases produce a substantial tail. Thus this classification concerns the **observed implementation and workload**, not a proof that a full scan is intrinsically necessary to obtain the same agreements.

Exact rich semantic counts at depth≤1 and depth≤2 are 1,539 and 1,394,064. Syntactic counts at depth≤1, depth≤2 and depth≤3 are 1,566, 4,909,437 and 48,205,158,042,276. The depth3 semantic count and runtime remain unknown. Offline depth≤2 graph build took 198.097 seconds and produced a 7,464,460-byte compressed graph. In a separate test of the original FLAT public plan on one existing rich depth2 fixture, process working set reached 533.4 MiB from 387.0 MiB after graph load and binding. It scored 1,252,611 structural candidates. The peak includes the warmed graph and interpreter. The search cost report gives the engineering measurement boundaries and the depth3 extrapolation assumptions.

Recommended follow-up: test indexed/on-demand retrieval that preserves the existing public score order as a reference, reporting total candidate touches, scores, verifier calls, construction and memory costs. Treat negotiation-feedback ranking as a separate secondary experiment, subject to the privacy and protocol boundaries. No claim of improved method performance is made here.

Reproduction artifacts: `results/flat_audit/per_instance.csv`, `family_summary.csv`, `rank_topk_records.jsonl`, `assemble_audit.py`, `rank_topk_audit.py`, and the timing audit under the same directory. [METHOD_RUNTIME_DECOMPOSITION.md](METHOD_RUNTIME_DECOMPOSITION.md) states the sampling and timing scope.

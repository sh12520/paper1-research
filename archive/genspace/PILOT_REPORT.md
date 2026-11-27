# PILOT-01 exploratory report

PILOT is exploratory model/distribution and effect-structure evaluation, not confirmation evidence. No A–E confirmation gate, bootstrap or significance test is determined here.

Integrity: 1920/1920 COMPLETE; integrity PASS; C01–C13 all passed; snapshot SHA-256 `18c3ef2eda454dd91a607eaecdd7501f5f82624f907d09bd6939cc77dd6bec0f`.
Main telemetry event records 27360, recorded telemetry errors 0; emergency breaches 0.
Paired method runtime per instance median 0.5495s, p95 2.6057s, max 6.1059s (FAST paired stage, excludes full child/Job orchestration).
The single execution segment took 116.42 minutes, including batches, repeated checks and aggregation; it does not include initial instance serialization before the segment began.
Maximum event worker peak working set 729.5 MiB; minimum sampled system available 1756.5 MiB. These are reported sample measurements.
All 508 Job launches passed the three-sample 2,048 MiB prelaunch check (lowest prelaunch sample 2,623.3 MiB). The lower 1,756.5 MiB sample was during execution, above the 768 MiB emergency threshold.

## Family agreement/deadlock and paired differences

| family | B0 A/D | B1 A/D | B2 A/D | O1 A/D | B1 deadlocks resolved | resolution | O1−B1 | O1−B2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 0/480 | 45/435 | 130/350 | 364/116 | 319/435 | 0.7333 | 0.6646 | 0.4875 |
| F2 | 0/480 | 0/480 | 0/480 | 122/358 | 122/480 | 0.2542 | 0.2542 | 0.2542 |
| F3 | 0/480 | 40/440 | 82/398 | 339/141 | 299/440 | 0.6795 | 0.6229 | 0.5354 |
| F4 | 0/480 | 40/440 | 118/362 | 347/133 | 307/440 | 0.6977 | 0.6396 | 0.4771 |

Selected O1 novelty outside B2 for B1+B2 deadlocks resolved by O1: 842/842 = 1.0000. For B1 deadlocks resolved: 977/1047 = 0.9331. Under candidate-space containment and the same-instance acceptance rules, a verified O1 representative that resolves a B2 deadlock must be outside B2; the 842/842 result is a consistency implication, not independent empirical evidence.
Mechanism counts among B1+B2 deadlocks resolved by O1 (labels may overlap): STATIC 0/842, STATE_CONDITIONAL 22/842, DELAYED_START 1/842, TEMPORAL_PHASED 38/842, OFFLOAD 823/842, HYBRID 42/842.
Detailed family, per-configuration, mechanism and F2 results are in PILOT_EFFECT_SUMMARY.md, PILOT_DISTRIBUTION_DIAGNOSTICS.md, PILOT_MECHANISM_ANALYSIS.md and PILOT_F2_ANALYSIS.md. Nash welfare and per-agent utility means in the CSV summaries include only agreements for that method; failures are excluded, not treated as zero.

## Interpretation boundaries

`PILOT_DISTRIBUTION_REVIEW_REQUIRED`: 96 configurations have at least one all-zero/all-one method; 40 have O1 all-zero/all-one or a zero B1-deadlock denominator. B0 all-zero and F2 structural necessity were already accepted by the user as benchmark properties and do not automatically constitute a model error. Exploratory review rationale: O1 在九个配置全0、31个配置全1且机制集中；不是因为已接受的 B0 全0或 F2 的 B1/B2 全0.
`MIXED_SIGNAL` is a subjective exploratory synthesis, not a research gate or confirmation finding. Reason: 四个 family 的 O1−B2 差值均为正，多个相邻区域也有正差，但 842 个双死锁解决代表中 823 带 OFFLOAD；F2 的 122 个代表全部带 OFFLOAD，仅 1 个带 DELAYED_START；40/96 配置的 O1 为全0或全1，限制了机制广泛性和分布区分度. No confidence or significance claim follows; this label must be reviewed by a human.
Depth/richness comparisons are between different random instances, since complete configuration enters seed derivation. A strict same-instance count of depth-2-only resolutions is not identifiable. Adjacent-cell descriptions are not evidence of statistical stability.
The F2 DELAYED_START count concerns only the selected representative. The per-instance summaries do not establish whether another verified delayed-start candidate existed, so the one selected representative cannot be used as an existence count for all verified candidates.
Recommend human distribution/benchmark review before deciding whether to enter CONFIRM freeze review.

The four canonical cases are separate from the 1,920 pilot instances; see PILOT_CANONICAL_CASES_REPORT.md. They are existing hand-constructed simplified fixtures with permissive fixture preconditions and fixture-specific utility/resource inputs, not full stochastic-model bilateral acceptance tests. Benchmark verification concerns only the frozen abstract benchmark semantics, not real-network execution proof.

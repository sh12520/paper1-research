# Engineering fixture plan — ORACLE-RUNTIME-CLOSE-02

This plan is written before the optimized post-baseline timing is observed. It defines **24** deterministic engineering fixtures, covers all 4 families × 2 capability-richness levels × 3 resource-pressure levels, and does not change any family, sampling distribution, utility, reservation or research seed design. Each fixture uses composition depth 2 and the existing `generate_instance` function with namespace `GENSPACE-FAIL-01-ENGINEERING`.

For zero-based indices `f`, `r`, `p` in the following lists:

- families: `[F1, F2, F3, F4]`;
- richness: `[sparse, rich]`;
- resource pressure: `[low, medium, high]`;

create one configuration for each Cartesian tuple. Set `preference_conflict` to `medium` if `(f+r+p) % 2 == 0`, otherwise `high`. Use the seed label `runtimeclose02-cross-{f}-{r}-{p}`; it is interpreted in the ENGINEERING namespace only. Generate each serialized instance once, reuse it for every evaluator and worker count, and record its complete, public and private hashes. Compare exact per-instance outputs between implementations and worker counts. Persist timing data without reporting agreement-rate research conclusions.

Report one-worker cold-process load separately from warm in-process reuse and separately estimate median/p90/p95/max, process/system memory, and phase timing. Fix software snapshot and library fingerprint before the run; record the power profile, host load, worker count and any contention. A warm run does not imply OS disk cache was flushed. If tests show a mismatch, halt and investigate rather than drop or approximate a candidate.

The earlier 20-fixture legacy baseline uses `make_fixtures`, in which `F1/F3` coincide with rich and `F2/F4` with sparse; it does not cover this full cross-product. Both datasets are engineering diagnostics. These 24 fixtures cover all family/richness/pressure combinations but select only one preference-conflict level for each such cell and only one engineering seed; they do not form the full 96-configuration design and do not support a representative research-outcome estimate. Any compute projection based on them must disclose this coverage and the limits of extrapolation.

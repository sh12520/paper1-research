# Grammar search work and public search time

Work summaries below describe measured online Top-K attempts, including limited queries. A scored-complete ratio divides exact public scores by the original 1,394,064 graph classes. The recorded `partial_generated` counter measures enqueues into the bound frontier, including structurally complete leaves awaiting transfer. `partial_expanded` counts unresolved hole expansions. `complete_syntax` counts complete leaf transfers and `scores` counts exact scores of unique eligible signatures. Quantiles use linear interpolation. Memory is the sampled or reported process working set. The bound permanently prunes zero subtrees. Unexpanded frontier nodes remain available to extend a certified prefix. The raw metric payload is retained in `per_query.csv`. Production and protocol consumption have separate columns. A stopped protocol run can lack the counters returned at its terminal budget.

| Cohort | Attempted | Exact K500 | Expected | Frontier enqueues median/p95 | Partial expanded median/p95 | Frontier median/p95 | Syntax leaves median/p95 | Exact scores median/p95 | Duplicates median/p95 | Score ratio median/p95 | Elapsed s median/p95 | Peak memory B median/p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fixed grid | 96 | 93 | 96 | 953 / 1.361e+05 | 351.5 / 5.03e+04 | 141 / 3.888e+04 | 513 / 6.916e+04 | 504 / 555 | 13.5 / 6.87e+04 | 0.0362% / 0.0398% | 0.3085 / 9.248 | 8.92e+07 / 9.944e+07 |
| 842 targets | 69 | 61 | 842 | 7,164 / 2.144e+05 | 1,888 / 8.205e+04 | 4,295 / 5.848e+04 | 1,062 / 7.396e+04 | 504 / 588 | 558 / 7.361e+04 | 0.0362% / 0.0422% | 0.5659 / 12 | 9.089e+07 / 9.953e+07 |
| Rich depth2 | 34 | 31 | 298 | 3.188e+04 / 2.116e+05 | 1.149e+04 / 8.069e+04 | 1.632e+04 / 5.731e+04 | 5,206 / 7.363e+04 | 504 / 596.4 | 4,698 / 7.329e+04 | 0.0362% / 0.0428% | 1.907 / 12 | 8.935e+07 / 9.931e+07 |
| >=100k | 46 | 38 | 340 | 5.075e+04 / 2.175e+05 | 1.942e+04 / 8.346e+04 | 2.324e+04 / 6.12e+04 | 1.085e+04 / 7.471e+04 | 504 / 588 | 1.027e+04 / 7.433e+04 | 0.0362% / 0.0422% | 2.587 / 12 | 9.076e+07 / 9.938e+07 |

The ≥100k comparison uses saved public-search timings from `INDEX-GATE-01`, including the original full FLAT score and sort. All three reference lanes depend on the pre-enumerated graph. The grammar lane consumes the typed DSL, public model and registry. It excludes independent reference work. Attempted-but-limited timings describe work until interruption, so G4 requires separately certified K=500 comparisons.

| Coverage | Lane | Measured instances | Public search seconds median/p95 |
| --- | --- | --- | --- |
| Full historical cohort | flat | 340 | 1.587 / 1.931 |
| Full historical cohort | generic | 340 | 0.1213 / 0.8599 |
| Full historical cohort | contract | 340 | 0.04434 / 0.4842 |
| Same attempted IDs | grammar | 46 | 2.587 / 12 |
| Same attempted IDs | flat | 46 | 1.619 / 1.849 |
| Same attempted IDs | generic | 46 | 0.2874 / 1.156 |
| Same attempted IDs | contract | 46 | 0.06625 / 0.5199 |
| Same certified IDs | grammar | 38 | 1.153 / 5.606 |
| Same certified IDs | flat | 38 | 1.597 / 1.827 |
| Same certified IDs | generic | 38 | 0.1992 / 0.6787 |
| Same certified IDs | contract | 38 | 0.04419 / 0.3279 |

G3 uses p95 score ratio ≤ 5% on all 298 rich-depth2 targets. G4 requires full K=500 coverage of the same 340 large instances and p95 no greater than 2× the contract-aware index and 70% of FLAT. The FLAT percentage is the previous 30% engineering margin applied descriptively. It has no inferential claim.

For a failed or censored comparison, elapsed time and score counts at the observed cutoff are lower bounds on completion for the same cursor. Filling missing entries with the nonnegative lower bound zero gives a mathematical lower bound on full-cohort p95, even when no full descriptive p95 can be reported. This calculation cannot establish a pass with incomplete coverage.

| Gate | Observations | Expected | Observed above threshold | Lower bound on full p95 | Threshold |
| --- | --- | --- | --- | --- | --- |
| G3 | 34 | 298 | 0 | 0.000362178 | 0.05 |
| G4 | 46 | 340 | 28 | 3.34923 | 0.968341 |

Among 11 limited K=500 attempts with a leaf count, 99.46%–99.87% of transferred syntax leaves duplicated an already seen semantic signature. Semantic duplication is the primary observed work bottleneck. `F4__low__medium__sparse__d2__s0` transferred 77,580 complete syntax leaves, of which 77,481 were duplicates, and certified 99 outputs. The measurements quantify duplicated work and frontier growth. They do not separately attribute wall time to each cause.

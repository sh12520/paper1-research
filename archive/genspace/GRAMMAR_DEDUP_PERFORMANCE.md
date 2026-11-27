# Grammar deduplication performance

G3 **PASS**. G4 **PASS**. Formal performance queried 340 of the original target IDs. Only the formal performance lane contributes measurements.

G3 uses the original 298 rich depth-two targets and score ratios relative to 1,394,064 classes. G4 uses the original 340 targets with at least 100,000 conditioned candidates and the frozen 0.96834057-second K=500 p95 threshold. Complete-cohort coverage is required for a pass. Limited attempts still supply measured lower bounds on work and time; unmeasured IDs use the nonnegative lower bound zero only in the mathematical full-cohort lower-bound calculation.

| Gate | Observed | Original n | Observed over threshold | Full p95 lower bound | Threshold |
| --- | --- | --- | --- | --- | --- |
| G3 | 298 | 298 | 0 | 0.000419636401 | 0.05 |
| G4 | 340 | 340 | 0 | 0.43484073 | 0.96834057 |

Archived timings for the prior grammar include their recorded limits. Matching-ID panels distinguish attempted and certified comparisons. Historical cohort timing is shown for its measured coverage.

| Scope | Lane | n | Public search seconds median / p95 |
| --- | --- | --- | --- |
| full cohort | flat | 340 | 1.58741 / 1.93141 |
| full cohort | generic | 340 | 0.121279 / 0.859865 |
| full cohort | contract | 340 | 0.0443353 / 0.48417 |
| full cohort | prior_grammar | 46 | 2.5873 / 12 |
| full cohort | deduplicated_grammar | 340 | 0.228828 / 0.434841 |
| same attempted IDs | flat | 340 | 1.58741 / 1.93141 |
| same attempted IDs | generic | 340 | 0.121279 / 0.859865 |
| same attempted IDs | contract | 340 | 0.0443353 / 0.48417 |
| same attempted IDs | prior_grammar | 46 | 2.5873 / 12 |
| same attempted IDs | deduplicated_grammar | 340 | 0.228828 / 0.434841 |
| same certified IDs | flat | 340 | 1.58741 / 1.93141 |
| same certified IDs | generic | 340 | 0.121279 / 0.859865 |
| same certified IDs | contract | 340 | 0.0443353 / 0.48417 |
| same certified IDs | prior_grammar | 46 | 2.5873 / 12 |
| same certified IDs | deduplicated_grammar | 340 | 0.228828 / 0.434841 |

| Observed new performance metric | n | median / p95 |
| --- | --- | --- |
| public_search_s | 340 | 0.228828 / 0.434841 |
| unique_scores | 340 | 504 / 585 |
| partial_expanded | 340 | 333 / 792 |
| frontier_peak | 340 | 272 / 1,106 |
| complete_assignments | 340 | 504 / 585 |
| duplicate_syntax_transfers | 340 | 0 / 0 |
| witness_asts_materialized | 340 | 500 / 500 |
| witness_recipe_evaluations | 340 | 1,094 / 3,392 |
| symbolic_shapes | 340 | 91 / 91 |
| symbolic_cases | 340 | 369 / 369 |
| template_count | 340 | 116 / 116 |
| template_recipes | 340 | 316 / 316 |
| template_build_s | 340 | 0.0212438 / 0.0293164 |
| template_payload_bytes | 340 | 123,188 / 123,188 |
| exact_state_keys | 340 | 1,097 / 2,378 |
| complete_key_memo_size | 340 | 1,089 / 1,196 |
| cell_memo_size | 340 | 238 / 297 |
| peak_worker_bytes | 340 | 5.33688e+07 / 5.37111e+07 |

Symbolic template construction time is included in public search time. A complete assignment instantiates a packed semantic key. Witness AST materializations and candidate recipe evaluations are measured separately. Template payload bytes cover documented Python objects and payloads. Peak worker bytes are observed process working set and include the resident runtime.

Rich depth-two certified score ratio median / p95 = 0.0362% / 0.0420%.

## Same 128 prior diagnostic fixtures

Certified K=500 completion was 117/128 before quotienting and 128/128 after it. This panel uses separate diagnostic queries and is excluded from the G3 and G4 decisions.

| Diagnostic metric | n | median / p95 |
| --- | --- | --- |
| prior_wall_s | 128 | 0.343702 / 12 |
| new_wall_s | 128 | 0.178914 / 0.514726 |
| prior_complete_syntax | 128 | 606 / 73,170 |
| prior_duplicate_transfers | 128 | 105 / 72,837 |
| new_complete_assignments | 128 | 504 / 588 |
| new_duplicate_transfers | 128 | 0 / 0 |
| new_witness_asts | 128 | 500 / 500 |
| new_witness_recipe_evaluations | 128 | 605 / 3,392 |

The completed-pair speedup is old elapsed time divided by new elapsed time on the same ID. For the prior capped queries, old elapsed time is a lower bound on time to an eventual exact K=500 result, so the ratio also gives a lower bound. Per-ID ratios are summarized directly.

| Paired scope | n | Prior s median / p95 | New s median / p95 | Speedup median / p95 |
| --- | --- | --- | --- | --- |
| Both completed | 117 | 0.326637 / 5.60788 | 0.171273 / 0.367774 | 1.7188 / 28.4675 |
| Prior capped, lower bounds | 11 | 12 / 12.0565 | 0.49835 / 0.703588 | 24.0796 / 36.6332 |

| Censored query | Prior observed s | New certified s | Speedup ≥ |
| --- | --- | --- | --- |
| F1__low__medium__rich__d2__s0 | 12 | 0.551878 | 21.744 |
| F1__low__high__sparse__d2__s1 | 12.1129 | 0.541514 | 22.3686 |
| F1__low__high__sparse__d2__s3 | 12.0001 | 0.324805 | 36.9454 |
| F1__low__high__sparse__d2__s5 | 12.0001 | 0.33353 | 35.9791 |
| F1__low__high__sparse__d2__s6 | 12 | 0.330387 | 36.321 |
| F1__low__high__sparse__d2__s10 | 12 | 0.478617 | 25.0723 |
| F1__low__high__rich__d2__s0 | 12.0001 | 0.49835 | 24.0796 |
| F1__low__high__rich__d2__s1 | 12 | 0.571758 | 20.9879 |
| F1__low__high__rich__d2__s2 | 12 | 0.523544 | 22.9208 |
| F1__low__high__rich__d2__s4 | 12 | 0.4849 | 24.7474 |
| F4__low__medium__sparse__d2__s0 | 12.0001 | 0.835417 | 14.3643 |

See `paired_old_128_diagnostics.csv` for the exact matched-ID rows.

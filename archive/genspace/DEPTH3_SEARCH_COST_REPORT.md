# Depth-three search work and measured cost

All attempts include capped cases. Time at a cap is elapsed work and can only lower-bound time to a future certification. The certified-only lane excludes capped cases. Missing telemetry remains NA. Peak working set measures the whole process and is sampled. All rows are the fixed existing public fixtures. The cursor clock can include verifier and protocol work interleaved after cursor creation. A certified checkpoint uses the cursor clock, while an incomplete checkpoint records the whole query clock at its cutoff. Final-query rows below all use the same end-to-end clock.

| K | Scope | Metric | n | Median | p95 | Max |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | all_attempts | elapsed_s | 24 | 0.297803 | 25.2755 | 26.8042 |
| 10 | all_attempts | cursor_elapsed_s | 24 | 0.297803 | 25.2755 | 26.8042 |
| 10 | all_attempts | partial_generated | 24 | 1,661.5 | 5,289.4 | 6,000 |
| 10 | all_attempts | partial_expanded | 24 | 1,512 | 185,282 | 189,572 |
| 10 | all_attempts | frontier_peak | 24 | 1,033 | 3,204.9 | 3,237 |
| 10 | all_attempts | unique_semantics | 24 | 54 | 63 | 63 |
| 10 | all_attempts | scores | 24 | 54 | 63 | 63 |
| 10 | all_attempts | duplicates | 24 | 0 | 0 | 0 |
| 10 | all_attempts | witness_asts_materialized | 24 | 10 | 10 | 10 |
| 10 | all_attempts | witness_recipe_evaluations | 24 | 307 | 6,476.95 | 71,440 |
| 10 | all_attempts | template_count | 24 | 47 | 1,233.45 | 1,338 |
| 10 | all_attempts | peak_working_set_bytes | 24 | 1.33097e+08 | 1.489e+08 | 1.49684e+08 |
| 10 | all_attempts | shape_nodes_generated | 24 | 1,287.5 | 4,367 | 4,473 |
| 10 | all_attempts | shape_nodes_expanded | 24 | 516 | 2,675.75 | 2,906 |
| 10 | all_attempts | assignment_nodes_expanded | 24 | 109 | 143 | 143 |
| 10 | all_attempts | symbolic_shapes_compiled | 24 | 107 | 805.05 | 898 |
| 10 | all_attempts | partition_probes | 24 | 847 | 182,529 | 186,603 |
| 10 | all_attempts | merged_template_states | 24 | 800 | 181,270 | 185,240 |
| 10 | all_attempts | duplicate_states_eliminated | 24 | 800 | 181,270 | 185,240 |
| 10 | all_attempts | max_observed_profile_slots | 24 | 5 | 8 | 8 |
| 10 | all_attempts | lower_bound_evaluations | 24 | 1,603 | 5,257 | 5,982 |
| 10 | all_attempts | buffered_complete | 24 | 44 | 53 | 53 |
| 10 | all_attempts | template_recipes | 24 | 847 | 182,504 | 186,578 |
| 10 | all_attempts | exact_state_keys | 24 | 356 | 1,444.8 | 1,548 |
| 10 | certified | elapsed_s | 24 | 0.297803 | 25.2755 | 26.8042 |
| 10 | certified | cursor_elapsed_s | 24 | 0.297803 | 25.2755 | 26.8042 |
| 10 | certified | partial_generated | 24 | 1,661.5 | 5,289.4 | 6,000 |
| 10 | certified | partial_expanded | 24 | 1,512 | 185,282 | 189,572 |
| 10 | certified | frontier_peak | 24 | 1,033 | 3,204.9 | 3,237 |
| 10 | certified | unique_semantics | 24 | 54 | 63 | 63 |
| 10 | certified | scores | 24 | 54 | 63 | 63 |
| 10 | certified | duplicates | 24 | 0 | 0 | 0 |
| 10 | certified | witness_asts_materialized | 24 | 10 | 10 | 10 |
| 10 | certified | witness_recipe_evaluations | 24 | 307 | 6,476.95 | 71,440 |
| 10 | certified | template_count | 24 | 47 | 1,233.45 | 1,338 |
| 10 | certified | peak_working_set_bytes | 24 | 1.33097e+08 | 1.489e+08 | 1.49684e+08 |
| 10 | certified | shape_nodes_generated | 24 | 1,287.5 | 4,367 | 4,473 |
| 10 | certified | shape_nodes_expanded | 24 | 516 | 2,675.75 | 2,906 |
| 10 | certified | assignment_nodes_expanded | 24 | 109 | 143 | 143 |
| 10 | certified | symbolic_shapes_compiled | 24 | 107 | 805.05 | 898 |
| 10 | certified | partition_probes | 24 | 847 | 182,529 | 186,603 |
| 10 | certified | merged_template_states | 24 | 800 | 181,270 | 185,240 |
| 10 | certified | duplicate_states_eliminated | 24 | 800 | 181,270 | 185,240 |
| 10 | certified | max_observed_profile_slots | 24 | 5 | 8 | 8 |
| 10 | certified | lower_bound_evaluations | 24 | 1,603 | 5,257 | 5,982 |
| 10 | certified | buffered_complete | 24 | 44 | 53 | 53 |
| 10 | certified | template_recipes | 24 | 847 | 182,504 | 186,578 |
| 10 | certified | exact_state_keys | 24 | 356 | 1,444.8 | 1,548 |
| 100 | all_attempts | elapsed_s | 24 | 0.628167 | 26.8996 | 28.7571 |
| 100 | all_attempts | cursor_elapsed_s | 24 | 0.628167 | 26.8996 | 28.7571 |
| 100 | all_attempts | partial_generated | 24 | 2,576 | 7,934.25 | 9,985 |
| 100 | all_attempts | partial_expanded | 24 | 2,745 | 189,722 | 193,197 |
| 100 | all_attempts | frontier_peak | 24 | 1,459.5 | 4,903.15 | 5,439 |
| 100 | all_attempts | unique_semantics | 24 | 117 | 151.65 | 261 |
| 100 | all_attempts | scores | 24 | 117 | 151.65 | 261 |
| 100 | all_attempts | duplicates | 24 | 0 | 0 | 0 |
| 100 | all_attempts | witness_asts_materialized | 24 | 100 | 100 | 100 |
| 100 | all_attempts | witness_recipe_evaluations | 24 | 2,280 | 504,308 | 596,760 |
| 100 | all_attempts | template_count | 24 | 64 | 1,306.5 | 1,340 |
| 100 | all_attempts | peak_working_set_bytes | 24 | 1.33157e+08 | 1.48921e+08 | 1.49684e+08 |
| 100 | all_attempts | shape_nodes_generated | 24 | 1,595.5 | 4,467 | 5,566 |
| 100 | all_attempts | shape_nodes_expanded | 24 | 696.5 | 2,798.5 | 3,236 |
| 100 | all_attempts | assignment_nodes_expanded | 24 | 257 | 1,464.1 | 1,799 |
| 100 | all_attempts | symbolic_shapes_compiled | 24 | 176 | 842.85 | 940 |
| 100 | all_attempts | partition_probes | 24 | 1,692 | 185,523 | 189,608 |
| 100 | all_attempts | merged_template_states | 24 | 1,628 | 184,191 | 188,243 |
| 100 | all_attempts | duplicate_states_eliminated | 24 | 1,628 | 184,191 | 188,243 |
| 100 | all_attempts | max_observed_profile_slots | 24 | 6 | 8 | 8 |
| 100 | all_attempts | lower_bound_evaluations | 24 | 2,369 | 7,826.25 | 9,850 |
| 100 | all_attempts | buffered_complete | 24 | 17 | 51.65 | 161 |
| 100 | all_attempts | template_recipes | 24 | 1,692 | 185,498 | 189,583 |
| 100 | all_attempts | exact_state_keys | 24 | 756 | 4,955.35 | 6,012 |
| 100 | certified | elapsed_s | 24 | 0.628167 | 26.8996 | 28.7571 |
| 100 | certified | cursor_elapsed_s | 24 | 0.628167 | 26.8996 | 28.7571 |
| 100 | certified | partial_generated | 24 | 2,576 | 7,934.25 | 9,985 |
| 100 | certified | partial_expanded | 24 | 2,745 | 189,722 | 193,197 |
| 100 | certified | frontier_peak | 24 | 1,459.5 | 4,903.15 | 5,439 |
| 100 | certified | unique_semantics | 24 | 117 | 151.65 | 261 |
| 100 | certified | scores | 24 | 117 | 151.65 | 261 |
| 100 | certified | duplicates | 24 | 0 | 0 | 0 |
| 100 | certified | witness_asts_materialized | 24 | 100 | 100 | 100 |
| 100 | certified | witness_recipe_evaluations | 24 | 2,280 | 504,308 | 596,760 |
| 100 | certified | template_count | 24 | 64 | 1,306.5 | 1,340 |
| 100 | certified | peak_working_set_bytes | 24 | 1.33157e+08 | 1.48921e+08 | 1.49684e+08 |
| 100 | certified | shape_nodes_generated | 24 | 1,595.5 | 4,467 | 5,566 |
| 100 | certified | shape_nodes_expanded | 24 | 696.5 | 2,798.5 | 3,236 |
| 100 | certified | assignment_nodes_expanded | 24 | 257 | 1,464.1 | 1,799 |
| 100 | certified | symbolic_shapes_compiled | 24 | 176 | 842.85 | 940 |
| 100 | certified | partition_probes | 24 | 1,692 | 185,523 | 189,608 |
| 100 | certified | merged_template_states | 24 | 1,628 | 184,191 | 188,243 |
| 100 | certified | duplicate_states_eliminated | 24 | 1,628 | 184,191 | 188,243 |
| 100 | certified | max_observed_profile_slots | 24 | 6 | 8 | 8 |
| 100 | certified | lower_bound_evaluations | 24 | 2,369 | 7,826.25 | 9,850 |
| 100 | certified | buffered_complete | 24 | 17 | 51.65 | 161 |
| 100 | certified | template_recipes | 24 | 1,692 | 185,498 | 189,583 |
| 100 | certified | exact_state_keys | 24 | 756 | 4,955.35 | 6,012 |
| 500 | all_attempts | elapsed_s | 24 | 0.845573 | 27.3855 | 29.4557 |
| 500 | all_attempts | cursor_elapsed_s | 24 | 0.845573 | 27.3855 | 29.4557 |
| 500 | all_attempts | partial_generated | 24 | 3,841.5 | 10,289.2 | 11,185 |
| 500 | all_attempts | partial_expanded | 24 | 3,265.5 | 191,260 | 195,861 |
| 500 | all_attempts | frontier_peak | 24 | 2,007 | 5,412.55 | 5,745 |
| 500 | all_attempts | unique_semantics | 24 | 580.5 | 709.65 | 819 |
| 500 | all_attempts | scores | 24 | 580.5 | 709.65 | 819 |
| 500 | all_attempts | duplicates | 24 | 0 | 0 | 0 |
| 500 | all_attempts | witness_asts_materialized | 24 | 500 | 500 | 500 |
| 500 | all_attempts | witness_recipe_evaluations | 24 | 14,133 | 632,783 | 710,433 |
| 500 | all_attempts | template_count | 24 | 64 | 1,337.55 | 1,401 |
| 500 | all_attempts | peak_working_set_bytes | 24 | 1.33288e+08 | 1.49159e+08 | 1.49684e+08 |
| 500 | all_attempts | shape_nodes_generated | 24 | 1,605 | 4,515 | 5,982 |
| 500 | all_attempts | shape_nodes_expanded | 24 | 698.5 | 2,898.3 | 3,603 |
| 500 | all_attempts | assignment_nodes_expanded | 24 | 846 | 1,962.55 | 2,237 |
| 500 | all_attempts | symbolic_shapes_compiled | 24 | 176 | 894.25 | 1,091 |
| 500 | all_attempts | partition_probes | 24 | 1,692 | 186,582 | 191,158 |
| 500 | all_attempts | merged_template_states | 24 | 1,628 | 185,219 | 189,732 |
| 500 | all_attempts | duplicate_states_eliminated | 24 | 1,628 | 185,219 | 189,732 |
| 500 | all_attempts | max_observed_profile_slots | 24 | 6 | 8 | 8 |
| 500 | all_attempts | lower_bound_evaluations | 24 | 3,146 | 9,781.2 | 10,528 |
| 500 | all_attempts | buffered_complete | 24 | 80.5 | 209.65 | 319 |
| 500 | all_attempts | template_recipes | 24 | 1,692 | 186,557 | 191,133 |
| 500 | all_attempts | exact_state_keys | 24 | 2,389 | 6,270.4 | 7,212 |
| 500 | certified | elapsed_s | 24 | 0.845573 | 27.3855 | 29.4557 |
| 500 | certified | cursor_elapsed_s | 24 | 0.845573 | 27.3855 | 29.4557 |
| 500 | certified | partial_generated | 24 | 3,841.5 | 10,289.2 | 11,185 |
| 500 | certified | partial_expanded | 24 | 3,265.5 | 191,260 | 195,861 |
| 500 | certified | frontier_peak | 24 | 2,007 | 5,412.55 | 5,745 |
| 500 | certified | unique_semantics | 24 | 580.5 | 709.65 | 819 |
| 500 | certified | scores | 24 | 580.5 | 709.65 | 819 |
| 500 | certified | duplicates | 24 | 0 | 0 | 0 |
| 500 | certified | witness_asts_materialized | 24 | 500 | 500 | 500 |
| 500 | certified | witness_recipe_evaluations | 24 | 14,133 | 632,783 | 710,433 |
| 500 | certified | template_count | 24 | 64 | 1,337.55 | 1,401 |
| 500 | certified | peak_working_set_bytes | 24 | 1.33288e+08 | 1.49159e+08 | 1.49684e+08 |
| 500 | certified | shape_nodes_generated | 24 | 1,605 | 4,515 | 5,982 |
| 500 | certified | shape_nodes_expanded | 24 | 698.5 | 2,898.3 | 3,603 |
| 500 | certified | assignment_nodes_expanded | 24 | 846 | 1,962.55 | 2,237 |
| 500 | certified | symbolic_shapes_compiled | 24 | 176 | 894.25 | 1,091 |
| 500 | certified | partition_probes | 24 | 1,692 | 186,582 | 191,158 |
| 500 | certified | merged_template_states | 24 | 1,628 | 185,219 | 189,732 |
| 500 | certified | duplicate_states_eliminated | 24 | 1,628 | 185,219 | 189,732 |
| 500 | certified | max_observed_profile_slots | 24 | 6 | 8 | 8 |
| 500 | certified | lower_bound_evaluations | 24 | 3,146 | 9,781.2 | 10,528 |
| 500 | certified | buffered_complete | 24 | 80.5 | 209.65 | 319 |
| 500 | certified | template_recipes | 24 | 1,692 | 186,557 | 191,133 |
| 500 | certified | exact_state_keys | 24 | 2,389 | 6,270.4 | 7,212 |

Shape expansions, profile-assignment expansions and symbolic equality partition probes are counted distinctly. The aggregate partial expansion counter includes all three. A merged symbolic template does not produce another complete semantic score. Frontier peak includes buffered complete candidates, pending lower-bound states and any in-flight expansion represented by its predecessor bound.

| K | Cutoff reason | Count |
| --- | --- | --- |

Each final-query measurement covers the full combined negotiation and prefix-search attempt.

| Metric | n | Median | p95 | Max |
| --- | --- | --- | --- | --- |
| final_query_elapsed_s | 24 | 2.18353 | 31.2522 | 32.3486 |
| final_query_peak_working_set_bytes | 24 | 1.36659e+08 | 1.53931e+08 | 1.61456e+08 |
| final_verifier_calls | 24 | 43 | 5,000 | 5,000 |
| final_proposal_rounds | 24 | 10 | 2,324 | 4,982 |

Sealed engineering limits: `{"emergency_available_mib": 768, "frontier_size": 260000, "partial_expanded": 2000000, "prelaunch_available_mib": 1280, "wall_seconds": 120.0, "worker_rss_mib": 2048}`.

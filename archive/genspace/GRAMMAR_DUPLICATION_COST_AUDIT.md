# GRAMMAR-DUPLICATION-KILL-01 · Original traversal cost audit

This is a diagnostic replay of the original graph-free Cursor using fixed, existing serialized development queries. The audited implementation was wrapped in memory. No original source or results were edited. The graph guard remained active during retrieval and post-hoc AST-pair inspection. The native archived prefixes were opened after the guard exited, only to check instrumented behavior.

K=500 and the prior limits of 12 s, 300,000 expansions, 180,000 frontier nodes and a 768 MiB worker working-set ceiling apply. Timing instrumentation itself adds overhead and can shorten a wall-limited prefix. The original sealed runtime and the instrumented phase timings are separately listed. The timed interval includes timer/wrapper overhead. No component duration is inferred from duplicate counts.

`partial_children_created` counts the initial root and successors returned for attempted insertion, including complete successors. It excludes recursive temporary objects internal to hole replacement. Child-creation time includes the existing hole walk and constructors. Recursive wrapper counts need not equal the number of popped holes. Native `partial_generated` is the number admitted to the bound frontier. The abstract transformer, envelope/cache work, bound, queue, exact score and witness operations use exclusive timings. Queue counts include open and complete heaps. Emitted-witness normalization is the explicit normalization at emission. Internal Static packing is timed in semantic/signature work.

| Instance | Original wall s / status | Instrumented wall s / status | Created | Expanded | Complete | Unique scored | Duplicate | Frontier peak | Certified outputs | Prefix check |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `F1__medium__medium__rich__d2__s0` | 1.2217 / COMPLETE | 1.8711 / COMPLETE | 15907 | 4552 | 3393 | 504 | 2889 | 7565 | 500 | PASS (500) |
| `F4__low__medium__sparse__d2__s0` | 12.0001 / LIMIT | 12.0003 / wall_time_limit | 91439 | 35220 | 21180 | 33 | 21147 | 35002 | 27 | PASS (27) |
| `F1__low__medium__rich__d2__s0` | 12.0000 / LIMIT | 12.0002 / wall_time_limit | 66864 | 24908 | 18408 | 36 | 18372 | 29931 | 18 | PASS (18) |
| `F1__low__medium__sparse__d1__s0` | 0.1502 / COMPLETE | 0.3065 / COMPLETE | 828 | 295 | 504 | 504 | 0 | 84 | 500 | PASS (500) |

## Attribution interpretation

The diagnostic pairs each late-rejected AST with the **incumbent raw witness at the time of duplicate detection**. Identical compact signatures establish equal normalized public execution and role footprint. Redundant IF is diagnosed by equal child signatures. The nested Delay/ValidFor, nested Sequence and repeated Offload labels describe patterns present in either AST. They do not prove independently that that pattern caused the collision. For pairs with identical constructor-and-parameter shapes, an additional projection walk labels changed Static profiles only if every changed slot is never visited by any of the six public cells. These labels record fixed-state IF shadowing or time cropping. They preserve the distinction between an unobservable profile value and an operator that still contributes to the whole-contract footprint. Per-pair tags can overlap. The exclusive descriptive count puts equal IF collapse first, projected profile variation second, wrapper shape tags third, and equal raw syntax or other equal-signature pairs last. This avoids double-counting while keeping the residual category explicit.

Signature-cache counters are captured before post-hoc pair inspection. Analysis of the pairs is outside the phase clock. A reported `0` in an exclusive bucket means the trace did not expose that tagged collision.

## `F1__medium__medium__rich__d2__s0`

| Phase | Calls | Exclusive s | Share |
|---|---:|---:|---:|
| abstract_transformer | 17674 | 0.277721 | 14.84% |
| other | 0 | 0.249423 | 13.33% |
| emitted_witness_normalization | 500 | 0.226226 | 12.09% |
| envelope_lookup | 50260 | 0.188704 | 10.09% |
| abstract_envelope_construction | 17707 | 0.153663 | 8.21% |
| lower_bound | 15249 | 0.141963 | 7.59% |
| partial_child_creation | 12429 | 0.134000 | 7.16% |
| signature_transfer_cache_miss | 4077 | 0.124303 | 6.64% |
| observer | 29980 | 0.095492 | 5.10% |
| cursor_setup | 1 | 0.065966 | 3.53% |
| complete_leaf_bookkeeping | 3393 | 0.054985 | 2.94% |
| witness_serialization | 3893 | 0.049345 | 2.64% |
| signature_lookup | 11579 | 0.047161 | 2.52% |
| priority_queue_push | 15753 | 0.023712 | 1.27% |
| priority_queue_pop | 8445 | 0.021696 | 1.16% |
| emitted_witness_parse | 500 | 0.011866 | 0.63% |
| exact_public_score | 504 | 0.004838 | 0.26% |

| Incoming root | Successors created | Admitted | Expanded | Complete transfers | First-seen scores | Duplicates |
|---|---:|---:|---:|---:|---:|---:|
| ClauseHole | 1 | 1 | 1 | 0 | 0 | 0 |
| Static | 1 | 0 | 0 | 0 | 0 | 0 |
| If | 8289 | 7965 | 2609 | 2520 | 315 | 2205 |
| Sequence | 6698 | 6365 | 1608 | 423 | 171 | 252 |
| Delay | 7 | 7 | 1 | 0 | 0 | 0 |
| ValidFor | 7 | 7 | 1 | 0 | 0 | 0 |
| Offload | 904 | 904 | 332 | 450 | 18 | 432 |

Duplicate root pairs (incoming → incumbent): `{"Offload → Offload": 18, "If → Offload": 18, "Offload → If": 252, "Offload → Sequence": 162, "If → If": 2187, "Sequence → Sequence": 252}`

Exclusive pattern counts: `{"repeated Offload": 18, "redundant IF": 369, "different syntax same signature (unassigned)": 477, "state-shadowed IF profile variation": 2025}`

Overlapping pattern tags: `{"repeated Offload": 36, "redundant IF": 369, "different syntax same signature (unassigned)": 477, "state-shadowed IF profile variation": 2106, "nested Sequence": 243}`

Representative equal-signature pairs (incoming, incumbent): `{"repeated Offload": ["[\"Offload\",\"edge\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]", "[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]"], "redundant IF": ["[\"If\",\"moving\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]],[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]", "[\"Offload\",\"edge\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]"], "different syntax same signature (unassigned)": ["[\"Offload\",\"edge\",[\"Sequence\",1,[\"Static\",0.8,1.0,0.5],[\"Static\",0.8,1.0,0.5]]]", "[\"Sequence\",1,[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]],[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]"], "state-shadowed IF profile variation": ["[\"If\",\"moving\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]],[\"If\",\"moving\",[\"Static\",0.4,1.5,0.5],[\"Static\",0.6,1.0,0.5]]]", "[\"If\",\"moving\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]],[\"If\",\"moving\",[\"Static\",0.4,1.0,0.5],[\"Static\",0.6,1.0,0.5]]]"]}`

Compact signature cache: `{"hits": 7502, "misses": 4077, "maxsize": 16384, "currsize": 4077}`

## `F4__low__medium__sparse__d2__s0`

| Phase | Calls | Exclusive s | Share |
|---|---:|---:|---:|
| other | 0 | 1.793938 | 14.95% |
| abstract_transformer | 92815 | 1.749859 | 14.58% |
| partial_child_creation | 104424 | 1.553095 | 12.94% |
| envelope_lookup | 277057 | 1.529290 | 12.74% |
| abstract_envelope_construction | 92890 | 1.100441 | 9.17% |
| lower_bound | 91402 | 1.010942 | 8.42% |
| signature_transfer_cache_miss | 21468 | 0.842257 | 7.02% |
| observer | 190162 | 0.756908 | 6.31% |
| complete_leaf_bookkeeping | 21180 | 0.425173 | 3.54% |
| witness_serialization | 21207 | 0.382738 | 3.19% |
| signature_lookup | 64125 | 0.372392 | 3.10% |
| priority_queue_pop | 56427 | 0.199596 | 1.66% |
| priority_queue_push | 91435 | 0.172405 | 1.44% |
| emitted_witness_normalization | 27 | 0.070872 | 0.59% |
| cursor_setup | 1 | 0.038733 | 0.32% |
| emitted_witness_parse | 27 | 0.001350 | 0.01% |
| exact_public_score | 33 | 0.000340 | 0.00% |

| Incoming root | Successors created | Admitted | Expanded | Complete transfers | First-seen scores | Duplicates |
|---|---:|---:|---:|---:|---:|---:|
| ClauseHole | 1 | 1 | 1 | 0 | 0 | 0 |
| Static | 1 | 0 | 0 | 0 | 0 | 0 |
| If | 91436 | 91400 | 35219 | 21180 | 33 | 21147 |
| Sequence | 0 | 0 | 0 | 0 | 0 | 0 |
| Delay | 0 | 0 | 0 | 0 | 0 | 0 |
| ValidFor | 1 | 1 | 0 | 0 | 0 | 0 |
| Offload | 0 | 0 | 0 | 0 | 0 | 0 |

Duplicate root pairs (incoming → incumbent): `{"If → If": 21147}`

Exclusive pattern counts: `{"redundant IF": 1612, "state-shadowed IF profile variation": 13238, "different syntax same signature (unassigned)": 6297}`

Overlapping pattern tags: `{"redundant IF": 1612, "state-shadowed IF profile variation": 13724, "different syntax same signature (unassigned)": 6297}`

Representative equal-signature pairs (incoming, incumbent): `{"redundant IF": ["[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.6,1.0,0.5]],[\"Static\",0.6,1.5,0.5]]", "[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.6,1.5,0.5]]"], "state-shadowed IF profile variation": ["[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.6,2.0,0.5]],[\"Static\",0.6,1.0,0.5]]", "[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.6,1.5,0.5]],[\"Static\",0.6,1.0,0.5]]"], "different syntax same signature (unassigned)": ["[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"If\",\"moving\",[\"Static\",0.6,1.5,0.5],[\"Static\",0.6,1.0,0.5]]]", "[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.4,1.0,0.5]],[\"Static\",0.6,1.0,0.5]]"]}`

Compact signature cache: `{"hits": 42657, "misses": 21468, "maxsize": 16384, "currsize": 16384}`

## `F1__low__medium__rich__d2__s0`

| Phase | Calls | Exclusive s | Share |
|---|---:|---:|---:|
| other | 0 | 1.744204 | 14.53% |
| abstract_transformer | 68326 | 1.687767 | 14.06% |
| partial_child_creation | 73413 | 1.491482 | 12.43% |
| envelope_lookup | 203316 | 1.410691 | 11.76% |
| signature_transfer_cache_miss | 18702 | 1.116216 | 9.30% |
| abstract_envelope_construction | 68374 | 1.015347 | 8.46% |
| lower_bound | 66611 | 0.957439 | 7.98% |
| observer | 146743 | 0.754622 | 6.29% |
| complete_leaf_bookkeeping | 18408 | 0.493577 | 4.11% |
| witness_serialization | 18426 | 0.442814 | 3.69% |
| signature_lookup | 55785 | 0.424823 | 3.54% |
| priority_queue_pop | 43334 | 0.194818 | 1.62% |
| priority_queue_push | 66647 | 0.158975 | 1.32% |
| cursor_setup | 1 | 0.077356 | 0.64% |
| emitted_witness_normalization | 18 | 0.028729 | 0.24% |
| exact_public_score | 36 | 0.000763 | 0.01% |
| emitted_witness_parse | 18 | 0.000607 | 0.01% |

| Incoming root | Successors created | Admitted | Expanded | Complete transfers | First-seen scores | Duplicates |
|---|---:|---:|---:|---:|---:|---:|
| ClauseHole | 1 | 1 | 1 | 0 | 0 | 0 |
| Static | 1 | 0 | 0 | 0 | 0 | 0 |
| If | 64528 | 64276 | 24375 | 18381 | 27 | 18354 |
| Sequence | 2188 | 2188 | 478 | 0 | 0 | 0 |
| Delay | 1 | 1 | 0 | 0 | 0 | 0 |
| ValidFor | 1 | 1 | 0 | 0 | 0 | 0 |
| Offload | 144 | 144 | 54 | 27 | 9 | 18 |

Duplicate root pairs (incoming → incumbent): `{"Offload → Offload": 9, "If → Offload": 9, "Offload → If": 9, "If → If": 18345}`

Exclusive pattern counts: `{"repeated Offload": 9, "redundant IF": 1527, "state-shadowed IF profile variation": 10521, "different syntax same signature (unassigned)": 6315}`

Overlapping pattern tags: `{"repeated Offload": 18, "redundant IF": 1527, "state-shadowed IF profile variation": 10923, "different syntax same signature (unassigned)": 6315}`

Representative equal-signature pairs (incoming, incumbent): `{"repeated Offload": ["[\"Offload\",\"edge\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]", "[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]"], "redundant IF": ["[\"If\",\"moving\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]],[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]", "[\"Offload\",\"edge\",[\"Offload\",\"edge\",[\"Static\",0.8,1.0,0.5]]]"], "state-shadowed IF profile variation": ["[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.5,0.5],[\"Static\",0.6,2.0,0.5]],[\"Static\",0.8,1.0,0.5]]", "[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.5,0.5],[\"Static\",0.6,1.0,0.5]],[\"Static\",0.8,1.0,0.5]]"], "different syntax same signature (unassigned)": ["[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"If\",\"moving\",[\"Static\",0.6,1.5,0.5],[\"Static\",0.8,1.0,0.5]]]", "[\"If\",\"moving\",[\"If\",\"moving\",[\"Static\",0.6,1.0,0.5],[\"Static\",0.4,1.0,0.5]],[\"Static\",0.8,1.0,0.5]]"]}`

Compact signature cache: `{"hits": 37083, "misses": 18702, "maxsize": 16384, "currsize": 16384}`

## `F1__low__medium__sparse__d1__s0`

| Phase | Calls | Exclusive s | Share |
|---|---:|---:|---:|
| cursor_setup | 1 | 0.052577 | 17.15% |
| other | 0 | 0.048869 | 15.94% |
| signature_transfer_cache_miss | 531 | 0.043053 | 14.05% |
| abstract_transformer | 828 | 0.019790 | 6.46% |
| complete_leaf_bookkeeping | 504 | 0.018053 | 5.89% |
| witness_serialization | 1004 | 0.017523 | 5.72% |
| lower_bound | 827 | 0.013740 | 4.48% |
| envelope_lookup | 2451 | 0.013103 | 4.27% |
| abstract_envelope_construction | 868 | 0.012976 | 4.23% |
| observer | 2634 | 0.012876 | 4.20% |
| emitted_witness_parse | 500 | 0.012533 | 4.09% |
| signature_lookup | 1994 | 0.011995 | 3.91% |
| partial_child_creation | 589 | 0.010451 | 3.41% |
| exact_public_score | 504 | 0.007561 | 2.47% |
| emitted_witness_normalization | 500 | 0.004738 | 1.55% |
| priority_queue_pop | 1299 | 0.003560 | 1.16% |
| priority_queue_push | 1331 | 0.003128 | 1.02% |

| Incoming root | Successors created | Admitted | Expanded | Complete transfers | First-seen scores | Duplicates |
|---|---:|---:|---:|---:|---:|---:|
| ClauseHole | 1 | 1 | 1 | 0 | 0 | 0 |
| Static | 1 | 0 | 0 | 0 | 0 | 0 |
| If | 0 | 0 | 0 | 0 | 0 | 0 |
| Sequence | 797 | 797 | 284 | 486 | 486 | 0 |
| Delay | 0 | 0 | 0 | 0 | 0 | 0 |
| ValidFor | 29 | 29 | 10 | 18 | 18 | 0 |
| Offload | 0 | 0 | 0 | 0 | 0 | 0 |

Duplicate root pairs (incoming → incumbent): `{}`

Exclusive pattern counts: `{}`

Overlapping pattern tags: `{}`

Representative equal-signature pairs (incoming, incumbent): `{}`

Compact signature cache: `{"hits": 1463, "misses": 531, "maxsize": 16384, "currsize": 531}`

## Independence

Guard snapshot: `{"forbidden_call_counts": {"semantic_graph_file": 0, "index_gate_artifact": 0, "availability_index_artifact": 0, "unlisted_workspace_input": 0, "write_outside_current_output": 0, "FastLibrary.from_graph": 0, "FastLibrary.__init__": 0, "AvailabilityBundle.load": 0, "read_graph": 0, "graph_library": 0, "compact_dp.compact_library": 0, "compact_graph.compact_library": 0, "semantic_dp.library": 0, "semantic_dp.streaming_reference": 0, "enumeration.candidates": 0, "engine.enumerate_compositions": 0, "generate_instance": 0, "derive_seed": 0}, "blocked": [], "pass": true}`

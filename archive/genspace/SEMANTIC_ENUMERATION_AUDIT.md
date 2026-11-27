# Semantic enumeration audit — current design

**PRE-PILOT-CLOSE-01: BLOCKED.** This audit concerns the fixed public 3-time × 2-state benchmark, 27 configured scalar profiles and rich capability availability. It is engineering evidence, not a SMOKE, PILOT or CONFIRM outcome. The pre-smoke per-instance timing gate has not been established; no research run is authorized. `benchmark_verified` refers only to the finite benchmark, not real-network execution.

The authoritative current evidence is the compact graph audit in `SEMANTIC_LIBRARY_AUDIT.md`, the independent syntax-reference comparison in `EXTERNAL_REFERENCE_AUDIT.md`, and the 20-fixture timing audit in `ENGINEERING_DEPTH2_PERFORMANCE.md`. The earlier tuple-key prototype and its bounded attempts are historical; they do not determine current counts.

## Complete semantic sets for the fixed rich grammar

| Depth limit | Typed syntactic ASTs | Distinct semantic signatures | Syntactic duplicates eliminated | Independent exact set comparison |
|---|---:|---:|---:|---|
| 1 | 1,566 | 1,539 | 27 (1.72%) | Passed for the full 27-profile domain |
| 2 | 4,909,437 | 1,394,064 | 3,515,373 (71.60%) | Passed for the full 27-profile domain |

Static has depth 0. The depth-0 set contains 27 signatures. The depth-1 set is included in the depth-2 graph; 1,392,525 signatures appear at depth 2 beyond that set. The numbers count canonical public semantics under the documented fixed interpreter and registry; they do not establish a result for arbitrary capability registries or public grammars.

The depth-2 reference independently streamed all 4,909,437 syntax ASTs through the benchmark interpreter. A fixed-public-context cache memoized exact original public-only functions; it was checked against the uncached interpreter on a complete smaller grammar, the full depth-1 grammar and a 10,000-tree depth-2 prefix. The distinct signatures from the full stream and the graph were externally sorted and compared as **complete bytes**, not hashes. Both sets contained 1,394,064 keys and matched exactly. The full reference, sorting and comparison took 811.879 seconds under concurrent load. `results/engineering/external_full_depth2_cached_01/report.json` records the matched counts and source/config/dependency, helper and graph fingerprints. This comparison is evidence about the recorded implementation and public fixture; it does not itself prove contextual congruence for arbitrary extensions.

## Library size and engineering costs

The full depth≤2 compact graph was precomputed in **198.097 seconds**. The observed Windows process peak RSS at the end of precomputation was **358,879,232 bytes**; serialization was measured separately, so this does not establish serialization-phase peak memory. The serialized graph is **7,464,460 bytes**, with SHA-256 `11e84c86d15e58f64d8dcfc892e22a813cf1250c835a9d48fa96f22ea112f6fd`. Serialization and subsequent statistics took 12.211 seconds. Depth-1 precomputation time, peak process memory and serialized size were not separately measured for the current graph implementation.

Chosen witness-root counts for the depth≤2 graph are If 699,867; Sequence 691,146; Delay 1,539; ValidFor 756; Offload 756. All selected lexical witnesses have syntactic depth 2, including redundant `If` witnesses. **These are witness-root counts, not marginal per-operator contributions**: their values depend on tie-breaking and do not show how many semantics uniquely require an operator. Per-operator marginal contributions have not been independently measured. Structural novelty is signature non-membership in B2, not a property of witness syntax. The full key-set equality is not a full proof that every stored witness is globally lexical-minimal or recompiles correctly; 28 stored witnesses were sampled for the latter check.

For 20 distinct ENGINEERING fixtures with the graph reused, the O1 scan including per-instance initialization had median **13.2849 seconds** (range 1.0998–110.3071 seconds). Median public filtering was 4.853 seconds, V3–V4 6.702 seconds, and V5 plus representative selection 0.306 seconds; these are independent stage medians and must not be added. Graph loading was separately amortized per worker. Measurements used two workers while the independent reference and other processes ran, so they are not a controlled idle-machine benchmark. The measured median exceeds the tentative **<2 seconds** target and is insufficient to establish that gate; the packed evaluator has only reduced-domain differential verification. Per-instance memory peaks and resource constraints are detailed in `ENGINEERING_DEPTH2_PERFORMANCE.md`.

## Historical prototype measurements

Before the current semantic-aware normalization and compact graph, an instrumented depth-1 tuple-key prototype reported 1,539 signatures, 3.2064 seconds of precomputation, 11,994,131 bytes of peak Python-traced allocation and a 1,608,468-byte Python pickle. Python-traced allocation is not total process peak RSS, and these timing/size numbers are not measurements of the current graph implementation.

An earlier depth-2 tuple-key streaming attempt stopped after 50,000 of 4,909,437 trees at 122.3 seconds with 22,626 signatures observed and 178,961,983 bytes of peak Python-traced allocations. That order-dependent prefix was not an exact count; it is superseded for set equality by the complete independent comparison above. No partial result was used as a full-domain count.

## Remaining boundaries

The semantic outcome-equivalence and restricted context arguments are specified in `SEMANTIC_EQUIVALENCE.md`, `SEMANTIC_CONGRUENCE.md` and `SEMANTIC_DP_COMPLETENESS.md`. Exact full-set comparison complements those arguments but does not establish correctness of every packed per-instance evaluation, arbitrary provider vocabulary, witness, or future grammar. Before closure, resolve or establish the timing gate, strengthen per-instance evaluator and witness validation, verify basis/source/config/dependency fingerprints in the execution path, and complete the remaining checks in `PRE_PILOT_CHECKLIST.md`. The current work did not run SMOKE, PILOT or CONFIRM and did not generate `FROZEN_CONFIG.yaml`.
## Per-operator root derivability audit

A separate fixed-public engineering audit records every possible AST root for each compact signature, rather than attributing a signature to its single lexical witness. Its depth≤2 union matched all **1,394,064** graph keys exactly; the helper, registry/graph, source/config/dependency hashes matched before and after, and no research seeds were used. Full results and overlap table: `results/engineering/operator_derivability_audit.json`. The audit took 116.178 seconds.

| Root | Distinct signatures derivable through depth 1 | Distinct signatures derivable through depth 2 | Depth-2 signatures exclusive to this root |
|---|---:|---:|---:|
| Static | 27 | 27 | 0 |
| If | 729 | 700,596 | 204,849 |
| Sequence | 729 | 1,185,408 | 691,146 |
| Delay | 27 | 1,539 | 783 |
| ValidFor | 27 | 1,512 | 756 |
| Offload | 27 | 1,512 | 0 |

Root counts overlap (for example, If and Sequence overlap on 493,533 signatures) and must not be added. Root-exclusive is not a causal leave-one-operator-out contribution: removing an operator from all nested positions requires a separate full restricted-grammar enumeration. Root derivability uses the compact transfer and the documented fixed-domain congruence; the separate full syntax reference verified the overall union, not each root-specific subset.

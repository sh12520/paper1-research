# ON-DEMAND-GRAMMAR-SEARCH-01

**FAIL_SCALABILITY**

| Gate | Result |
| --- | --- |
| G1 | PASS |
| G2 | INCOMPLETE |
| G3 | INCOMPLETE |
| G4 | FAIL |
| G5 | PASS |

G4 was ruled out after 28 of the measured large-cohort cases exceeded the 0.968341 s threshold. Even with a zero lower bound for unmeasured cases, the full-cohort p95 is at least 3.349228 s. With G4 ruled out, the main batch stopped at 69 of 842 target queries. Longer-limit retries serve fixed-grid correctness coverage only and do not alter the formal performance measurements.

Semantic duplication was the primary observed work bottleneck. All 11 capped K=500 attempts with leaf counts spent 99.46%–99.87% of complete syntax transfers on duplicates.

This is a feasibility gate on the fixed development DSL and frozen FLAT ranking. Top-down partial-program search, A*/best-first search, admissible abstract-interpretation bounds and hole filling are generic techniques. The tested domain-specific components are the contract state/time/resource envelope, capability-aware pruning, FLAT-compatible bounds and a lazy stream consumed by the existing bilateral protocol.

See `GRAMMAR_BOUND_SPEC.md`, `PARTIAL_CONTRACT_ABSTRACT_SEMANTICS.md`, `GRAPH_INDEPENDENCE_AUDIT.md`, `GRAMMAR_CORRECTNESS_REPORT.md` and `GRAMMAR_SEARCH_COST_REPORT.md`. The execution scope is development only. CONFIRM was not invoked.

The preservation audit checked 16,544 historical files, and recorded the clean graph-independence seal for 128 cases.

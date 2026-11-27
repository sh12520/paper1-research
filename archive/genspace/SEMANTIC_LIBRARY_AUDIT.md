# Semantic library engineering audit — ORACLE-REDESIGN-01

This is a deterministic public-grammar precomputation, not a smoke, pilot, or confirmation result. The library supports the documented fixed 3 time × 2 state domain, the 27 configured B2 profiles, and the implementation's all-public-role-predicates-true transfer condition. The later independent full syntax-stream audit matched the graph byte for byte; see `EXTERNAL_REFERENCE_AUDIT.md`. The per-instance O1 timing gate remains unmet.

## Full rich depth ≤2 library

- Typed syntactic ASTs through depth 2: **4,909,437**. Compact graph signatures: **1,394,064**. The reduction against syntactic ASTs is **3,515,373**, or approximately **71.60%**.
- The depth 0 set contains **27** keys; depth 1 adds **1,512** for a depth ≤1 semantic set of **1,539** keys. An independent scan of the serialized graph confirmed all 1,539 are included, with **1,392,525** keys added at depth 2. All 27 B2 static profile signatures are included; **1,394,037** graph keys are not in the B2 semantic set.
- Precomputation wall time: **198.097 s**. Windows process peak RSS at end of precomputation: **358,879,232 bytes**. Serialization happened afterward; the measurement is not a reported serialization-phase peak.
- The lazy witness representation stores an operator, serialized parameter and up to two integer indices into a shared pool of depth ≤1 AST strings. Witness roots were If **699,867**, Sequence **691,146**, Delay **1,539**, ValidFor **756**, Offload **756**. These are root counts, not unique marginal contributions attributable to operators. All chosen lexical witness ASTs have depth **2**; redundant If forms can win the lexical tie without implying a structural gain.
- Serialized artifact: `results/engineering/semantic_library.graph.gz`, deterministic gzip containing sorted exact 49-byte packed keys and 7-byte witness records with a shared pool header. Size **7,464,460 bytes**; SHA-256 `11e84c86d15e58f64d8dc892e22a813cf1250c835a9d48fa96f22ea112f6fd`. Serialization and subsequent statistics took **12.211 s**.
- Independent artifact scan confirmed all 1,394,064 records strictly ordered with no duplicate packed keys, and reconstructed and recompiled **28** deterministically spaced witness samples to their exact stored signatures. This sample is not a full-domain witness proof.

Compact signatures use fixed public registry descriptors and profile ordering as context. Their bytes are not self-contained across different registries, profile domains, or benchmark versions. Before reuse, the library basis must match the instance exactly. This output alone is not proof that `semantic(B0) ⊆ semantic(B1) ⊆ semantic(B2) ⊆ semantic(O1)` for arbitrary inputs, or that per-instance public filtering and V5 meet the time gate.

## Fingerprint and limits

`results/engineering/running_source_hashes.txt` and `completed_source_hashes.txt` record SHA-256 values for the selected implementation, config, and audit script; they matched when compared after the run. Observed source modification times preceded process start (the audit script had the same displayed second). These snapshots were taken during and after the run, rather than embedded atomically at initial process startup. For production reuse, embed source, full public library basis, config and dependency fingerprints in the artifact header and verify them automatically.

The independent full 4,909,437-AST streaming semantic reference and graph match exactly byte for byte, as documented in `EXTERNAL_REFERENCE_AUDIT.md`. Twenty-fixture timings are reported in `ENGINEERING_DEPTH2_PERFORMANCE.md`; their concurrent-load O1 median exceeds the tentative 2-second target. No PRE-PILOT-CLOSE-01 gate is passed by this document alone. The benchmark compiler verifies only this finite abstract machine, not real-network execution.

The root-derivability audit in `SEMANTIC_ENUMERATION_AUDIT.md` separately reports overlapping per-root semantic sets and exclusive-root counts; these differ from the lexical-witness root counts above and are not recursive leave-one-operator-out estimates.

# Depth-3 gate interpretation and independent short-domain check

The official `DEPTH3_PARTIAL` label stands. The original gate required at least 20 of 24 full-length K=500 certificates and at least two pressure levels with that coverage in each family-by-richness cell. It recorded 19 full-length K=500 certificates. The F4 sparse cell supplied one such pressure level. The original full-length criteria were therefore unmet. Neither the official decision nor the run manifest was changed. [Official feasibility report](results/depth3/DEPTH3_FEASIBILITY_REPORT.md)

## Separate outcomes for exactness, domain size, and resource limits

| Interpretation label | Required evidence |
|---|---|
| `EXACT_TOPK_FULL_LENGTH` | K distinct signatures in exact public-score and tie order, with strict separation from every open frontier bound and no earlier buffered key, or an exhausted domain. |
| `EXACT_DOMAIN_EXHAUSTED_SHORT` | Fewer than K signatures, all in exact order, with a proved empty frontier and complete-candidate buffer. These are all eligible signatures. |
| `NOT_CERTIFIED_RESOURCE_LIMIT` | A time, memory, expansion or frontier limit stops the query before the requested result is certified. Any previously certified emissions remain valid for their smaller prefix. |
| `UNSOUND` | A score, order, signature, witness, eligibility, admissible-bound or certificate check fails. |

The first two labels partition the archived `EXACT_TOPK_CERTIFIED` count for this interpretation. The resource label describes the resource-limited subset of archived `NOT_CERTIFIED_WITHIN_BUDGET`. The archived statuses stay in place.

| Requested K | Exact results | Full-length exact results | Exhausted short domains | Resource limited | Unsound |
|---:|---:|---:|---:|---:|---:|
| 10 | 24/24 | 24/24 | 0 | 0 | 0 |
| 100 | 24/24 | 19/24 | 5 | 0 | 0 |
| 500 | 24/24 | 19/24 | 5 | 0 | 0 |

All 72 queried checkpoints retain exact certificates. The read-only recheck used the archived independent validator to verify the sealed output hashes, public inputs, normalized signatures, binary64 scores, order and cutoff evidence. It relies on the documented frontier and bound proof for unopened states. The verification did not run a fresh search. [Certificate records](DEPTH3_EXACT_CERTIFICATES.md) · [Read-only revalidation](results/paper_method_review/sealed_certificate_revalidation.json)

## Independent exhaustive check of the five short domains

The check used each query's existing serialized public grammar and all 27 original profiles. It bound the available canonical capability roles against the original registry. Before enumerating, it verified that the actual grammar contained only unary structural productions and that the full legal syntax count was within 500 ASTs. The independent lane traversed `src/engine.py::enumerate_compositions`, deduplicated with `CompactEncoder.encode` using the original interpreter, and ranked the resulting keys with the original NumPy FLAT public score and unsigned byte tie order. It computed all five domains before reading the sealed candidate results. No depth-3 cursor, semantic graph, history of successful agreements, or new benchmark data was used. [Independent checker](results/paper_method_review/verify_short_domains.py)

| Original fixture | Available structural productions | Raw ASTs, including B2 | Distinct signatures, including B2 | Exact structural signatures | Sealed emitted distinct signatures |
|---|---|---:|---:|---:|---:|
| `F1__low__high__sparse__d2__s0` | `ValidFor`, `Offload` | 405 | 108 | 81 | 81 |
| `F2__high__high__sparse__d2__s0` | `ValidFor` | 108 | 54 | 27 | 27 |
| `F3__high__high__sparse__d2__s0` | `ValidFor`, `Offload` | 405 | 108 | 81 | 81 |
| `F4__medium__high__sparse__d2__s0` | `ValidFor`, `Offload` | 405 | 108 | 81 | 81 |
| `F4__high__high__sparse__d2__s0` | `ValidFor`, `Offload` | 405 | 108 | 81 | 81 |

For these fixed parameters, repeated `ValidFor([0,2])` wrappers keep the same active interval. Repeated `Offload(edge)` wrappers keep the same level. Their declared roles and active roles combine by set union. The two wrappers also commute at the level of the packed semantics. With both available, every nonempty unary wrapper chain produces a validity-only, offload-only, or combined signature for each profile. This yields `27 × 3 = 81` structural signatures. With only validity available, the count is `27 × 1 = 27`. The 27 static B2 signatures are separate from each structural stream. These counts concern typed semantic candidates, prior to public physical checks or bilateral acceptance.

It is exact set equality, not count agreement alone, that substantiates each exhaustion result. For all five domains the independent run matched the complete emitted key set, rank order, binary64 score bits, normalized witness, and both the K=100 and K=500 sealed prefix digest. It also checked the archived case hashes against the clean online seal. [Machine-readable verification](results/paper_method_review/short_domain_verification.json)

## Implication for paper methods and future gates

For the frozen 24 queries, each of the five independently exhausted domains has at most 81 eligible signatures, below 500. Thus the maximum possible full-length K=500 coverage is 24 − 5 = 19. The other 19 queries certified 500 and attained that maximum. F4 sparse has two of the five short domains, so its full-length pressure coverage has a maximum of one. The preregistered requirements were 20/24 overall and two pressure levels per family-by-richness cell. Both were mathematically unreachable on this fixed grid.

The frozen verdict remains `DEPTH3_PARTIAL`. The infeasible full-length threshold is a retrospectively identified design defect for measuring exact retrieval completion. The panel certifies the requested finite-domain prefixes, with no estimate of the full rich depth-3 domains beyond them. The prospective metric counts K certified records or all `N<K` records with an exact exhaustion proof. Full-length coverage remains a separate descriptive metric. The retrospective analysis confers no preregistered pass. [Prospective design](METHOD_CONFIRMATION_PREREGISTRATION_DRAFT.md)

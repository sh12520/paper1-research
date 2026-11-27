# Pre-pilot change log

## ORACLE-REDESIGN-01 / v0.2 (2026-11-16)

Status: draft, not frozen. No smoke, pilot or confirmation outcome has been observed, and no experiment in those namespaces is authorized during this redesign. Unit and engineering fixtures are correctness or performance checks only, not research samples.

- Changed the main `composition_depth` grid from [2,3] to [1,2]; all other grid axes unchanged. There are still 96 configurations. The previous draft remains `PREREGISTRATION.md`; the new draft is `PREREGISTRATION_v0.2.md`.
- The 27-profile rich depth-3 domain has 48,205,158,042,276 typed syntactic ASTs; depth 3 full syntax is not a pre-pilot requirement. Each F1–F4 basic mechanism is expressible with depth 1; depth 2 adds nesting for this bounded existence study. Depth >2 is future work, not an exact confirmation gate.
- O1 is redefined as a finite exact semantic existence oracle with canonical public semantics and deterministic AST witnesses; it remains a diagnostic oracle, not a proposed algorithm.
- Gate B now counts resolved deadlock representatives outside the B2 semantic set, independent of witness syntax. Negative control semantic-set equality is an exact implementation invariant; Gate D's 5pp bound remains a separate sanity criterion.
- Setup cost is zero in the draft model. Runtime resource and execution costs apply to actually executed branches. Identical branches of If must normalize to their shared child before V2, semantics and costing; this explicit benchmark normalization avoids treating redundant controls as new contracts. It is subject to tests and equivalence proof.
- Added engineering fixture namespace isolated from the smoke, pilot and confirmation namespaces. Added source/config/dependency identity capture via `python -m src.fingerprints`; optional `--write PATH` captures and `--check PATH` verifies a snapshot. Fingerprints do not freeze the config and are not a substitute for a software supply-chain audit.

Full-domain semantic equivalence, completeness and computational feasibility remain subject to the independent audit and tests. This entry records the design change, not success of those gates.

## ORACLE-CONGRUENCE-CLOSE-01

Before any SMOKE-01, PILOT or CONFIRM run, a counterexample showed that syntactic-only equal-branch normalization was not context congruent. The benchmark now collapses `If(moving,A,B)` after recursive normalization when the full public semantic signatures of A and B match, choosing the lexical normalized child; this is a model definition change, not a result-driven adjustment. Context and invalid-state arguments are in `SEMANTIC_CONGRUENCE.md`. The prior isolated unit fixtures under the legacy SMOKE default were not a SMOKE-01 run and produced no research outcomes.

## ORACLE-REDESIGN-01 repeated request review (2026-11-17)

The descriptive mechanism-label implementation and draft definitions were corrected before any SMOKE-01, PILOT or CONFIRM run: a cell comparison now includes active role and resource/execution cost as well as service profile and offload; inactive-to-active transitions alone do not count as phased. Semantic novelty remains signature nonmembership in B2. This affects reporting, not the recorded contract-signature generation or reference audit.

## ORACLE-RUNTIME-CLOSE-02 (2026-11-17)

Recorded a 20-fixture single-worker quiet legacy baseline, then—after depth-1/depth-2 F1–F4 full-candidate and ULP-boundary differential reports passed on the execution snapshot—ran a separate fixed 24-fixture ENGINEERING-only FAST scaling check. One- and two-worker serialized outputs matched exactly; 4/8 workers were not attempted because of the memory guard. The 1-worker warm O1 median on these fixtures was below the provisional 2-second target; p95 exceeded it. `QUIET_BASELINE_02.md` and `FAST_SCALING_02.md` preserve scope, stage measurements, memory limits, fingerprints and planning-only projections. The later benchmark did not access study seed namespaces, change the research model or create a frozen configuration.

A later artifact-inclusive conditioned FAST benchmark (`FAST_SCALING_04.md`) measured all 24 engineering fixtures with per-class first-failure NPZ writes and checked decoded artifact equality across one and two workers. The provisional warm-O1 median target was met on that engineering set; four/eight workers were not attempted under the memory guard. This is not a research outcome or a decision to run SMOKE.

Final timing provenance: `FAST_SCALING_04.md` and `results/engineering/fast_scaling_04/report.json` supersede the interim 02/03/03b FAST measurements. The final 24-fixture engineering batch wrote per-class NPZ layers and compared decoded artifacts and all non-timing outputs exactly for one and two workers; four/eight workers were skipped by the memory guard. Cold graph plus 17-index loading and warm timings are separated. These engineering measurements and the derived compute projections are not study outcomes; SMOKE, PILOT and CONFIRM were not run and no `FROZEN_CONFIG.yaml` was created.

## SMOKE-01 diagnostic execution

Status: SMOKE_FAIL. Completed 35/192; snapshot SHA256 09e3031791c759badfeb97ec2381f67aa429e18fc39496bac3e98079e3ee6a37. Engineering/exploratory pipeline check only; no confirmation claim.

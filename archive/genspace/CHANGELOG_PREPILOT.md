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

## WINDOWS-LIFECYCLE-FINALIZE-01 — initiated

User revised the engineering process-lifecycle gate: a terminated, waited child with expected exit code, zero active non-breakaway Job processes, and no breakaway may remain queryable without being considered running or a memory failure. The prior SMOKE-01 failure and 4/32 ENGINEERING audit remain unchanged historical records. Parent-side suspended Job containment and its ENGINEERING tests are in progress; no research-model, seed-distribution, or gate changes are authorized. SMOKE-02, PILOT and CONFIRM are not run in this task.

### WINDOWS-LIFECYCLE-FINALIZE-01 — engineering outcome

A parent-side CREATE_SUSPENDED, assign-and-verify Job, then resume launcher was exercised on 32 ENGINEERING instances across eight batches; all matched their non-timing references, and each final Job accounting check returned zero active processes. The specified minimal normal/P4/snapshot mismatch regression passed. These results do not imply a completed SMOKE-02 execution pipeline: real SMOKE-02 orchestration and its preregistered audits/repeats remain unimplemented. Historical failures remain preserved. No SMOKE-02, PILOT or CONFIRM run or FROZEN_CONFIG was created.
# SMOKE02-PIPELINE-INTEGRATION-01 status

BLOCKED before execution: identity-only plans and fail-closed aggregation/scaffold prepared, but native SHADOW namespace support is absent from the protected FAST evaluator. No instance execution occurred; no SMOKE-02, PILOT or CONFIRM run or seed was created. The generated snapshot is a locked non-executable draft, not evidence of execution compatibility. See `SMOKE02_PIPELINE_INTEGRATION_REPORT.md`.


## SMOKE02-ROUTING-CLOSE-01

Completed 16-instance SHADOW engineering diagnostic with planned stop/resume, 4 candidate audits, 8 reruns, 16 fresh repeats, and C01–C13 PASS. Formal verifier-compatible snapshot generated; SMOKE/PILOT/CONFIRM remain disabled. The SHADOW-only orchestrator and incomplete general recovery/authorization integration keep PRE-SMOKE ENGINEERING BLOCKED. No SMOKE-02, PILOT or CONFIRM experiment was run and no FROZEN_CONFIG was created.

## SMOKE02-FORMAL-ORCHESTRATOR-CLOSE-01

The common orchestrator and shared atomic primitive passed 16-instance SHADOW, prior-reference equality, all C01–C13, real partial-batch interruption and controlled memory-pause recovery, and new real FAST P1–P5. Formal and shadow execution snapshots verify; current authorization remains SHADOW=true and SMOKE/PILOT/CONFIRM=false. PRE-SMOKE ENGINEERING is CLOSED; SMOKE-02 is ready only for explicit authorization. No SMOKE-02/PILOT/CONFIRM run or seed was produced and no FROZEN_CONFIG was created.

## SMOKE-02 execution

192/192 completed, C01–C13 passed and preregistered candidate and rerun sets matched; SMOKE_PASS is limited to those specified engineering invariants. The phase-specific worker/orchestrator memory events mandated by smoke preregistration were not captured and require review. Descriptive distributions trigger DISTRIBUTION_REVIEW_REQUIRED. The run is not confirmation evidence, and no PILOT/CONFIRM execution was authorized or performed. See `SMOKE_REPORT.md`.

Instrumentation clarification: complete worker/orchestrator and system samples at instance start/end and child exit were also not recorded; periodic samples cannot reconstruct them.

## PILOT-INSTRUMENTATION-CLOSE-01

Prospective phase and Job telemetry passed a 16-instance SHADOW ON/OFF equivalence check; previous SMOKE data and its recorded deviation are preserved. The requested new PILOT file is verifier-compatible as a locked preparation scope, but cannot yet be used to execute PILOT because the PILOT route is hard denied. PILOT/CONFIRM remain unauthorized; no parameter, distribution, model or research gate was tuned.

## PILOT-ROUTING-CLOSE-01

PILOT native routing, independent authorization, identity-only 1,920-slot plan and verifier-compatible executable snapshot are complete. The 16-instance SHADOW non-timing comparison and telemetry/Job checks passed. Historical preparation and SMOKE evidence remain intact. PILOT and CONFIRM remain unauthorized; no seeds or instances from either namespace were generated. No FROZEN_CONFIG was created. The four canonical cases remain separate for the eventual authorized PILOT record. See `PILOT_ROUTING_CLOSE_REPORT.md`.

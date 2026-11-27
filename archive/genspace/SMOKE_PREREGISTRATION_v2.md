# SMOKE-02 engineering preregistration v2

Status: preparation only; this document does not authorize or start SMOKE-02. SMOKE-01 remains permanently FAILED_MEMORY_GUARD, archived independently. This version changes execution reliability rules only; it leaves research preregistration, instances, seed derivation, models, grammar, utilities, resources, registry, distributions and Gates A–E unchanged. It was prepared before any SMOKE-02 execution.

## Plan and namespace

`SMOKE02_PLAN.json` fixes exactly 192 distinct identities in the same grid/order as SMOKE-01: family F1–F4 × pressure low/medium/high × conflict medium/high × richness sparse/rich × depth 1/2 × seed index 0/1. The sole experimental namespace is `GENSPACE-FAIL-01-SMOKE`, and existing seed derivation is unchanged. Every method reads the same serialized instance; one instance is serialized once and retained. Nothing from the SMOKE-01 output is incorporated as SMOKE-02 results. Neither PILOT nor CONFIRM may run under this authorization.

## Execution and preflight

Formal execution uses one worker, never simultaneous evaluator children. The intended isolated-batch child limit is four instances; a smaller limit requires memory audit support. The 768 MiB minimum available physical memory remains unchanged; before starting or continuing work, safety failures cause a recorded pause, not a lowered threshold. Capture worker and orchestrator RSS, system physical used/available memory before each instance, at evaluator stages, after each instance, and after child exit. Safe pause plus same-snapshot validated resume is not an unexplained crash; the segment and interrupted identity must be explicitly recorded. Formal future PILOT/CONFIRM are also single worker, subject to their separate authorizations and preregistration.

Before any SMOKE-02 execution: MEMORY-RECOVERY-ENGINEERING-01 must pass; long-lived and batch-child outputs must match exactly; atomic commit, resume simulation, interrupted-child recovery, snapshot mismatch fail-closed, and fresh-process deterministic tests must all pass. The dedicated `SMOKE02_EXECUTION_SNAPSHOT_FINGERPRINT.json` must bind and verify source, config, Python/NumPy, model, registry, semantic graph and all 17 availability indices. Any mismatch prohibits resume under the run ID; use a new run ID only under appropriate prior authorization. This preregistration and the exact plan must be hashed before execution.

## Atomic commits and resume

Output each instance into a unique temporary directory, check schema, paired hash and full execution snapshot, flush and fsync files, atomically rename to the final directory, then atomically create a flushed `COMPLETE.json` marker. Only a final directory with a fully verified marker counts complete; incomplete temporary directories are not results. On start or resume, inspect each planned ID. Skip a completed result only after validating marker contents, namespace, snapshot, original serialized instance hash, schema, four distinct method outputs, and payload integrity. Missing instances run; any mismatched existing complete result fails closed. Never regenerate an already serialized instance during resume. A segment manifest records timestamps, planned/completed/validated-skip identities, interrupted identity, memory samples and snapshot hash.

## Output and fixed audits

Main execution stores per-instance metadata/hash, four method summaries, existence, representative, utilities, Nash, candidate/generated/public-eligible counts, first-failure counts and incrementally computed digest, mechanism, novelty, timing and fingerprint. No candidate-level NPZ is written during the main phase. Public eligible means candidate count minus V1/V2/V3 first-failure counts; finite and unit-interval checks apply to defined outputs and V5-reached values. After 192/192 complete, create each of four full candidate-level artifacts sequentially in its own child: family F1/F2/F3/F4, pressure medium, conflict high, richness rich, depth 2, seed index 0. Each child exits before the next one begins.

After main completion rerun the fixed eight identities: family F1/F2/F3/F4 × medium × high × rich × depth2 × seed index 0/1. The fixed 16 fresh-child repeat identities are family F1/F2/F3/F4 × pressure low/high × conflict medium × richness sparse × depth 1/2 × seed index 0. Run each 16-subset identity in a fresh process; all non-timing, non-timestamp research outputs must match the primary instance exactly. Compare the original eight independently for C11. A two-worker check is optional engineering only, not a PASS condition, and must not start if unsafe.

## Invariants and reporting

SMOKE-02 PASS requires: C01 192/192 COMPLETE; C02 zero unexplained crash; C03 zero silent skip; C04 paired hash exact; C05 M0 ⊆ MR ⊆ B2 ⊆ MC; C06 exact no-structural O1/B2 semantic set equality; C07 no invalid candidate benchmark_verified; C08 finite defined outputs; C09 utilities within [0,1]; C10 complete schemas and four correct candidate audits; C11 eight-instance non-timing rerun equality; C12 sixteen-instance fresh-process non-timing equality; C13 fixed snapshot and plan throughout. A failed or uncheckable requirement is not PASS. Legitimate safety pauses are documented and require valid resume.

Do not calculate or judge Gates A–E, bootstrap confidence intervals, statistical significance, or research success/failure. Family/method agreement/deadlock counts are raw exploratory engineering diagnostics only, not evidence for a hypothesis. No parameter or model changes may be informed by SMOKE-01 observations. `benchmark_verified` means only verification against the frozen abstract benchmark semantics, not proof of real network execution.

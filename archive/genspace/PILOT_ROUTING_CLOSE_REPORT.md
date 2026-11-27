# PILOT-ROUTING-CLOSE-01

**PILOT-ROUTING-CLOSE-01 = CLOSED**  
**PILOT-01 READY FOR EXPLICIT AUTHORIZATION**

This is engineering routing closure, not permission to run PILOT or CONFIRM. Both remain disabled. No PILOT/CONFIRM seed or research instance was generated, and no FROZEN_CONFIG.yaml was created.

## Evidence

- The execution verifier accepts the new immutable `pilot-execution` snapshot, SHA-256 `18c3ef2eda454dd91a607eaecdd7501f5f82624f907d09bd6939cc77dd6bec0f`. The separate authorization file binds that hash and keeps PILOT=false and CONFIRM=false.
- An isolated no-instance test loaded the actual 1,394,064-class graph and availability indices through `FastLibrary.from_graph(scope='pilot-execution')`, with authorization mocked only for that test. Actual authorization denies execution. The `pilot-preparation` scope remains non-executable.
- The real common CLI returned `AUTHORIZATION_DENIED` for PILOT and CONFIRM without creating the requested output directories. A spy test verified that the denied PILOT request calls neither the seed nor instance generator. A synthetic authorization flag/version test did not generate a seed or instance.
- The identity-only plan covers 1,920 unique slots, 96 configurations and 20 indices each, in deterministic order. Template SHA-256: `3e70c49620ff50f7a02fbb4bbbaa7e3ec3531e4caff7d2acd43c2f37b175939d`.
- A single routing regression reused 16 saved SHADOW instances covering F1–F4, both richnesses and both depths. All 16 non-timing result envelopes matched prior instrumented ON results. All required phase events passed; four suspended Jobs each finished with ActiveProcesses=0. The 228 recorded events show minimum sampled system physical availability of 4,628.9 MiB and maximum event-recorded worker peak working set of 669.2 MiB. These are event samples, not unobserved instantaneous peaks.
- The graph, independent reference, 17 availability indices, model, registry, configuration and research core matched prior evidence. The authorized change in the instances core is an exactly defined authorization guard; removing it yields the independently audited original hash. The entire changed source is bound by the new snapshot.
- All 1,204 preflight-hashed historical files remained byte-identical, including the prior preparation snapshot and SMOKE evidence. The preparation snapshot verifies with its historical staged source and original Python/NumPy; a current-tree hash match is not expected after routing changes.
- PILOT and SHADOW share the scheduler, FAST evaluation, atomic transactions, resume, memory guards, instrumentation and aggregation. PILOT phase telemetry is required even if `GENSPACE_TELEMETRY` is set to off.
- Twenty-eight targeted routing, plan, telemetry, invariant and aggregation tests passed. Machine-readable evidence: `results/pilot_routing_preflight/final_audit.json` and `results/pilot_routing_regression_staging/audit_report.json`.

## Future authorized PILOT

The shared engine's 4/8/16 subsets are inherited engineering diagnostics, not previously registered PILOT research gates; see `PILOT_ENGINEERING_SUBSETS.md`. The four preregistered canonical cases must be accounted for separately in the actual PILOT record. Gate A–E, model, distributions and reservation rules were not altered. The engine retains the internal `SMOKE_COMPLETE` completion status name for a successful shared run; that name does not authorize or identify a SMOKE run.

`benchmark_verified` means verification only under the abstract benchmark semantics, not proof of execution on a real network.

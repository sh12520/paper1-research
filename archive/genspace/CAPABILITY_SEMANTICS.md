# Capability and benchmark state-machine semantics

Status: pre-pilot prototype. A `benchmark_verified` result is a claim only about this abstract finite benchmark. It is not a real network execution proof. No RDINP, ns-3, real network, or remote action is used.

`verify_instance` accepts the public and private parts of a serialized instance; only V5 calls private utility. V1 checks AST node types and configured operator depth (Static depth 0). V2 binds each required role to an available capability with identical input/output types, public predicates, effects, resource/execution costs and scopes; IDs and providers can differ. It validates the closed predicate vocabulary: motion observability requires both benchmark states; profile fields must belong to the public scalar profile grid; durations/offsets/intervals must be within the horizon; condition and offload values must be supported; reservation predicates use the public reservation flag. Unknown predicates fail. Missing capabilities fail. The registry descriptors are benchmark declarations, not external APIs.

V3 evaluates each AST at every time and every exogenous state. `If(moving,a,b)` evaluates `a` in moving, `b` in still. `Sequence(d,a,b)` runs `a` before local time d and `b` afterwards with time rebased by d. `Delay(o,a)` idles until local time o and then runs `a` with time rebased by o. `ValidFor((start,end),a)` is active over the half-open local interval and rebases time by start. `Offload(edge,a)` changes the resource model for active descendants. These semantics compose recursively; validity and delay are local to their enclosing subtree.

Compilation creates a finite guarded sequence for each (time,state) alternative. Each cell begins with its capacity vector. An idle action leaves it unchanged. An active cell deterministically reserves RAN, FH and EDGE in that order, rejecting if any demand exceeds capacity; each resource demand includes registry resource costs for each distinct role on the selected active path only. Execution costs are summed for those active roles and charged per cell in network utility. Idle cells have no runtime charge; setup cost is zero; the subsequent quality, deadline, rate and offload instructions preserve the remaining resource vector. Cells are alternative exogenous-state scenarios, not parallel workloads. V4 checks each cell and public hard constraints; V5 computes normalized utility and reservations. Details and limits of demand and utility are in `MODEL_SPEC.md`.

`semantic_key` records the complete active/idle guarded profile/offload schedule, per-cell active roles and costs, and normalized whole-contract descriptors, required scopes and precondition results; on a fixed public instance, equal keys produce equal demand and utility. A bare schedule without the footprint would be unsafe for pre-validation pruning because ASTs can have different capability and scope requirements. The full semantic key retains those requirements; `safe_public_dedup_key` further refines it with reporting metadata. Exhaustive semantic enumeration still requires independent completeness tests. Public predicates and enumeration completeness still require independent checks.

The normalization step recursively replaces `If(moving,A,B)` with the lexically smaller normalized child when their public semantic signatures agree, before capability checks and runtime cost accounting. It applies in particular to `If(moving,P,P)`. This is an explicit semantic definition, not a claim that an actual deployment would incur no setup or condition-observation cost. Unknown condition names are not normalized away.

### Behavioral mechanism labels

Labels describe the normalized guarded semantic cells and are independent of the witness AST. An active cell is compared using its profile, offload level, active role set and role resource/execution costs; an idle cell is a distinct value.

- `STATIC`: every guarded cell is active, has the same full semantic value, and uses no offload. This label describes constant behavior; structural novelty remains a separate B2 membership test.
- `STATE_CONDITIONAL`: at least one time has different cell values across exogenous states. A difference solely in role or cost counts.
- `DELAYED_START`: at least one state is idle at the first time and active at a later time.
- `TEMPORAL_PHASED`: at least one state has two adjacent **active** cells with different values. An idle-to-active or active-to-idle transition alone does not count as phased.
- `OFFLOAD`: at least one active cell uses a non-`none` offload level.
- `HYBRID`: at least two of the preceding four labels apply.

These are deterministic descriptive labels. They do not independently establish structural novelty, which the preregistration defines by semantic-set non-membership in B2.

# Canonical test fixtures

These four hand-constructed deterministic unit cases test the validator and grammar only. They are not random pilot observations, empirical data, or confirmation evidence. Code: `src/canonical_cases.py`; tests: `tests/test_canonical_cases.py`.

Shared domain: quality 0.4 or 0.9, deadline 1, rate 1; all registered capabilities and symbolic preconditions are available. Every active slot has FH demand 0.1; unoffloaded RAN demand equals quality, EDGE demand 0; offloaded RAN and EDGE demand are each half quality. Capacity for FH and EDGE is 1 in every slot/state. Network utility is 0.8 with reservation 0.5. Application utility is the sum of active-slot quality over all enumerated time/state pairs, divided by the total number of time/state pairs; inactive slots count as zero. The only additional hard constraint in these fixtures requires at least one active action. These deliberately minimal utilities are fixtures, not the proposed finalized pilot utility model.

- F1: horizon 2, states still/moving, RAN capacity 1/0.5 respectively, application reservation 0.6. `If(moving, Static(0.4), Static(0.9))` passes; both static profiles fail acceptance or feasibility.
- F2: horizon 3, one state, RAN capacity 0.1 at time 0 and 1 thereafter, application reservation 0.55. `Delay(1, Static(0.9))` passes; both statics exceed initial capacity.
- F3: horizon 2, one state, RAN capacity 0.5 at time 0 and 1 thereafter, application reservation 0.6. `Sequence(1, Static(0.4), Static(0.9))` passes; static low fails acceptance and high exceeds initial capacity.
- F4: horizon 2, one state, RAN capacity 0.5 throughout, application reservation 0.8. `Offload(edge, Static(0.9))` passes; low fails acceptance and high exceeds capacity.

All tests validate a witness and check all fixed profiles. The typed depth-two enumeration test independently constructs the set of ASTs for a small restricted grammar. This test is not a runtime proof that the full depth-three enumeration is tractable.

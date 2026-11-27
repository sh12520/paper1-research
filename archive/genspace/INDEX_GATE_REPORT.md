# INDEX-GATE-01

**PASS**

The replay uses the existing serialized PILOT instances and the frozen 1,394,064-class semantic graph. It tests the feasibility of exact indexed retrieval of the original FLAT order.

| Gate | Result |
| --- | --- |
| G1 | PASS |
| G2 | PASS |
| G3 | PASS |
| G4 | PASS |
| G5 | PASS |

The result supports proceeding to `ON-DEMAND-GRAMMAR-SEARCH-01` as the next feasibility study. This gate evaluated retrieval from the existing depth-2 graph.

## Public feature boundary

- The builder reads the frozen semantic graph, public model and registry, original public scorer and existing availability masks. It does not open serialized PILOT cases or outcomes.
- The cursor receives FLAT's sanitized PublicView, the bound public library, and the availability entry derived from public capabilities. Complete feature records and node bounds contain structural features and public costs only.
- The audit harness selects the development cohort outside retrieval. It opens the historical FLAT outcome after the query and passes preferences only to the preserved bilateral protocol and offline witness verifier.
- The replay harness guards the instance and seed generators and records their call counters.

## Preservation

Source and artifact preservation verified for 16,485 distinct files. CONFIRM stayed disabled and FROZEN_CONFIG.yaml was absent.

The correctness, candidate costs, runtime and generic-index differential are documented in the companion reports. Use the query and agreement CSVs for per-instance detail.

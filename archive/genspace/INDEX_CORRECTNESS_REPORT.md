# INDEX-GATE-01 exactness and agreement

- G1 contract top-K comparisons PASS.
- G2 agreement-path equivalence PASS.

The fixed-grid selection uses existing seed-index 0 in every configuration. The target cohort has 842 instances. Thirty-seven belong to both sets. Each indexed result is checked for candidate IDs, order and exact binary64 score bits against the original FLAT score and tie-break.

The union contains 901 instances. The captured Top-K rows include 3,604 contract and 3,604 generic comparisons out of 3,604 expected per variant. The two cohort views below share the 37 overlapping instances.

| Variant | Cohort | K | Compared | Expected | Mismatches |
| --- | --- | --- | --- | --- | --- |
| contract | fixed_grid | 10 | 96 | 96 | 0 |
| contract | fixed_grid | 50 | 96 | 96 | 0 |
| contract | fixed_grid | 100 | 96 | 96 | 0 |
| contract | fixed_grid | 500 | 96 | 96 | 0 |
| contract | target | 10 | 842 | 842 | 0 |
| contract | target | 50 | 842 | 842 | 0 |
| contract | target | 100 | 842 | 842 | 0 |
| contract | target | 500 | 842 | 842 | 0 |
| generic | fixed_grid | 10 | 96 | 96 | 0 |
| generic | fixed_grid | 50 | 96 | 96 | 0 |
| generic | fixed_grid | 100 | 96 | 96 | 0 |
| generic | fixed_grid | 500 | 96 | 96 | 0 |
| generic | target | 10 | 842 | 842 | 0 |
| generic | target | 50 | 842 | 842 | 0 |
| generic | target | 100 | 842 | 842 | 0 |
| generic | target | 500 | 842 | 842 | 0 |

Agreement replay compares the common verifier and bilateral protocol outcomes, selected representative, uA, uN, Nash welfare, verification calls and the recorded protocol history. All target instances are required at each budget.

| Budget | Paired target | Expected | Mismatches |
| --- | --- | --- | --- |
| 100 | 842 | 842 | 0 |
| 500 | 842 | 842 | 0 |
| 5000 | 842 | 842 | 0 |

The comparator calls the preserved FLAT make_plan and independently recomputes candidate scores with its original proxy. The indexed replay substitutes the B2 ID lookup and structural order provider in an in-memory copy of the V1 runner. The verifier, agent behavior and protocol come from V1.

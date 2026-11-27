# Grammar search correctness and bilateral agreement

G1 **PASS**. G2 **INCOMPLETE**. The sealed online batch contains 128 existing fixtures. The independent reference loaded the semantic graph after the seal was verified (True).

Top-K uses original FLAT `make_plan` and recomputes the selected prefix scores with the original `_proxy` and score expression. The reference compares 49-byte semantic signatures in FLAT class-ID order and exact binary64 score bits. Each emitted prefix is checked even when the query later reaches a limit.

Agreement compares the original hash-bound FLAT record for that serialized fixture. The checker compares the agreement result, class signature, normalized representative, both utility bit patterns, Nash, verification calls and proposal history through each budget. Missing certificates or snapshots are counted as incomplete. Fixed-grid coverage and zero observed differences are required for G1 and G2.

| Coverage | Check | Expected | Exact matches | Mismatches | Incomplete |
| --- | --- | --- | --- | --- | --- |
| Fixed grid | Top-10 | 96 | 96 | 0 | 0 |
| Fixed grid | Top-50 | 96 | 96 | 0 | 0 |
| Fixed grid | Top-100 | 96 | 96 | 0 | 0 |
| Fixed grid | Top-500 | 96 | 96 | 0 | 0 |
| Fixed grid | Protocol B=100 | 96 | 94 | 0 | 2 |
| Fixed grid | Protocol B=500 | 96 | 94 | 0 | 2 |
| Fixed grid | Protocol B=5000 | 96 | 94 | 0 | 2 |
| Target cohort | Top-10 | 842 | 69 | 0 | 773 |
| Target cohort | Top-50 | 842 | 69 | 0 | 773 |
| Target cohort | Top-100 | 842 | 68 | 0 | 774 |
| Target cohort | Top-500 | 842 | 61 | 0 | 781 |
| Target cohort | Protocol B=100 | 842 | 69 | 0 | 773 |
| Target cohort | Protocol B=500 | 842 | 69 | 0 | 773 |
| Target cohort | Protocol B=5000 | 842 | 69 | 0 | 773 |

See `results/grammar_gate/topk_correctness.csv` and `results/grammar_gate/agreement_correctness.csv` for original formal row details.

Separately sealed longer-limit correctness runs apply only to formal fixed-grid limits. The merged evidence is in `topk_correctness_combined.csv` and `agreement_correctness_combined.csv`. G3/G4 and all work distributions retain the original formal measurements.

| Mode | Replayed queries | New exact checks | New differences |
| --- | --- | --- | --- |
| topk | 3 | 4 | 0 |
| protocol | 9 | 21 | 0 |

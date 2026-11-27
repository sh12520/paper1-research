# DG-PCE development results

Exploratory development evaluation on the same 1,920 PILOT instances; this is not confirmation evidence. No new random benchmark instance or benchmark seed was generated. RANDOM-BUDGET uses a deterministic method PRNG derived only from allowed public fields.

Development gate: **METHOD_WEAK_V1**; individual checks: `{"beats_flat": false, "beats_random": true, "beats_random_families_at_least_3": true, "multi_group_nonzero": true, "no_opponent_private_leakage": true, "orc_at_least_080": true}`.

Primary ORC uses 842 oracle-recoverable B2 deadlocks; family ORC uses the recoverable subset of that family. Nash/utility gaps are conditional on an actual agreement and are not zero-filled for failures; `nash_gap_n` reports the denominator. FULL-O1 is the existing unlimited offline oracle; it has no online budget/runtime. Search reduction counts exact verification calls, not public scan work.

| Method | B | ORC | Recovered / eligible | Median calls | Mean Nash gap | Gap n | Median runtime s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B2 | 100 | 0.0 | 0/842 | 27.0 | None | 0 | 0.0423107499955222 |
| B2 | 500 | 0.0 | 0/842 | 27.0 | None | 0 | 0.04231999999319669 |
| B2 | 1000 | 0.0 | 0/842 | 27.0 | None | 0 | 0.042333699988375884 |
| B2 | 5000 | 0.0 | 0/842 | 27.0 | None | 0 | 0.04234294999332633 |
| B2 | 10000 | 0.0 | 0/842 | 27.0 | None | 0 | 0.04235109999717679 |
| RANDOM-BUDGET | 100 | 0.37648456057007124 | 317/842 | 100.0 | 0.04693664748494527 | 317 | 0.1148044499932439 |
| RANDOM-BUDGET | 500 | 0.671021377672209 | 565/842 | 180.0 | 0.045429639271998466 | 565 | 0.12002295000274898 |
| RANDOM-BUDGET | 1000 | 0.7232779097387173 | 609/842 | 180.0 | 0.0462981162356758 | 609 | 0.12117765000584768 |
| RANDOM-BUDGET | 5000 | 0.8527315914489311 | 718/842 | 180.0 | 0.04953246704956956 | 718 | 0.12134050000167917 |
| RANDOM-BUDGET | 10000 | 0.9085510688836105 | 765/842 | 180.0 | 0.049854245429382 | 765 | 0.12134515000798274 |
| FLAT-FEASIBILITY | 100 | 0.9774346793349169 | 823/842 | 43.0 | 0.007884302813580619 | 823 | 0.12594444999558618 |
| FLAT-FEASIBILITY | 500 | 0.998812351543943 | 841/842 | 43.0 | 0.007725203022928908 | 841 | 0.12595884999609552 |
| FLAT-FEASIBILITY | 1000 | 0.998812351543943 | 841/842 | 43.0 | 0.007725203022928908 | 841 | 0.1259710499944049 |
| FLAT-FEASIBILITY | 5000 | 1.0 | 842/842 | 43.0 | 0.007716028197485999 | 842 | 0.12598014999821316 |
| FLAT-FEASIBILITY | 10000 | 1.0 | 842/842 | 43.0 | 0.007716028197485999 | 842 | 0.12598884999169968 |
| GLOBAL-FREQUENCY | 100 | 0.9418052256532067 | 793/842 | 43.0 | 1.8588682650359867e-05 | 793 | 0.12584659999993164 |
| GLOBAL-FREQUENCY | 500 | 0.9857482185273159 | 830/842 | 43.0 | 1.7760030532211297e-05 | 830 | 0.1261694499917212 |
| GLOBAL-FREQUENCY | 1000 | 0.9857482185273159 | 830/842 | 43.0 | 1.7760030532211297e-05 | 830 | 0.12617594999755966 |
| GLOBAL-FREQUENCY | 5000 | 0.998812351543943 | 841/842 | 43.0 | 1.75277352458209e-05 | 841 | 0.12618109999311855 |
| GLOBAL-FREQUENCY | 10000 | 0.998812351543943 | 841/842 | 43.0 | 1.75277352458209e-05 | 841 | 0.1261861500024679 |
| SINGLETON-ONLY | 100 | 0.47030878859857483 | 396/842 | 100.0 | 0.009046015538274395 | 396 | 0.11337779999303166 |
| SINGLETON-ONLY | 500 | 0.9513064133016627 | 801/842 | 171.0 | 0.009393400112726368 | 801 | 0.123697799994261 |
| SINGLETON-ONLY | 1000 | 0.9513064133016627 | 801/842 | 171.0 | 0.009393400112726368 | 801 | 0.12370229999214644 |
| SINGLETON-ONLY | 5000 | 0.9513064133016627 | 801/842 | 171.0 | 0.009393400112726368 | 801 | 0.12371134999557398 |
| SINGLETON-ONLY | 10000 | 0.9513064133016627 | 801/842 | 171.0 | 0.009393400112726368 | 801 | 0.12372850000247126 |
| DG-PCE | 100 | 0.47030878859857483 | 396/842 | 100.0 | 0.009046015538274395 | 396 | 0.1308183500004816 |
| DG-PCE | 500 | 0.9572446555819477 | 806/842 | 171.0 | 0.009335128399868263 | 806 | 0.14267665000079433 |
| DG-PCE | 1000 | 0.9572446555819477 | 806/842 | 171.0 | 0.009335128399868263 | 806 | 0.14340039999660803 |
| DG-PCE | 5000 | 0.998812351543943 | 841/842 | 171.0 | 0.008946627217947468 | 841 | 0.14344039999559755 |
| DG-PCE | 10000 | 0.998812351543943 | 841/842 | 171.0 | 0.008946627217947468 | 841 | 0.1434791499923449 |
| FULL-O1 | 100 | 1.0 | 842/842 | None | 0.0 | 842 | 0.34999684998911107 |
| FULL-O1 | 500 | 1.0 | 842/842 | None | 0.0 | 842 | 0.34999684998911107 |
| FULL-O1 | 1000 | 1.0 | 842/842 | None | 0.0 | 842 | 0.34999684998911107 |
| FULL-O1 | 5000 | 1.0 | 842/842 | None | 0.0 | 842 | 0.34999684998911107 |
| FULL-O1 | 10000 | 1.0 | 842/842 | None | 0.0 | 842 | 0.34999684998911107 |

Numerical long-form results: `raw_results.csv` and `summary.csv`. Public setup/probe/ranking counts and times, pair use among agreements, first mechanisms, paths and utility gaps are in `summary.csv`. FULL-O1 runtime uses its recorded historical PILOT O1 stage time; unlike method end-to-end times it omits B2 and was not measured contemporaneously, so it is not directly comparable. The four method source hashes and locked configuration hash are in the run manifest. API-level information isolation is not an operating-system security boundary.

Timing boundary: each method's `elapsed_seconds` starts inside `runtime.run`, after the graph has been loaded and the input deserialized, sanitized public adapter and private-agent ports constructed. It includes B2, the method's public setup/probes/ranking, candidate checks and protocol, but excludes graph loading, input/agent setup, offline reference validation and orchestration. The complete final guarded segment took approximately 64.0 minutes. Mean and median per-instance times have different sensitivity to the heavily skewed public ranking workload.

Observed B=5000 failure indicators: `{"flat_resolved_same_instance": 1, "interpretation": "Observed path/budget/proposal indicators are not unique or causal failure classifications. Without the full verified candidate pool and private acceptance history at each checkpoint, selection, ranking, negotiation and budget effects are not separately identifiable.", "multi_group_unresolved": 0, "multi_group_without_pair_stage": 0, "random_resolved_same_instance": 1, "reached_budget": 1, "stage_cap_hit": 1, "stage_counts": {"B2": 1, "C": 1, "D": 1, "D+C": 1, "D+P": 1, "P": 1, "P+C": 1}, "termination_reason_counts": {"budget_exhausted": 1}, "unresolved_instance_evidence": [{"family": "F3", "first_mechanism": "D", "flat_succeeds": true, "instance_id": "F3__low__medium__sparse__d2__s9", "path": ["D", "P", "C", "D+P", "D+C", "P+C"], "proposals": 2309, "random_succeeds": true, "stage_details": [{"available": 27, "cap_hit": false, "public_feasible": 9, "quota": 27, "stage": "B2", "verified": 27}, {"available": 54, "cap_hit": false, "public_feasible": 54, "quota": 128, "stage": "D", "verified": 54}, {"available": 41580, "cap_hit": true, "public_feasible": 0, "quota": 128, "stage": "P", "verified": 128}, {"available": 729, "cap_hit": true, "public_feasible": 0, "quota": 128, "stage": "C", "verified": 128}, {"available": 3024, "cap_hit": true, "public_feasible": 1294, "quota": 1600, "stage": "D+P", "verified": 1600}, {"available": 2160, "cap_hit": true, "public_feasible": 952, "quota": 1600, "stage": "D+C", "verified": 1600}, {"available": 1180224, "cap_hit": false, "public_feasible": 0, "quota": 1600, "stage": "P+C", "verified": 1463}], "successful_singleton_groups_offline": ["P"], "verification_calls": 5000}], "unresolved_recoverable": 1, "with_one_or_more_proposals": 1}`. These indicators overlap; they do not establish distinct causal failure categories.

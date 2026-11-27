# FLAT successful-rank analysis

Post-hoc developmental diagnostics on the 842 existing B2-deadlock / full-O1-agreement PILOT instances. The public ordering was reconstructed before private acceptance was inspected; none of these offline results is available online or fed back to either method. These ranks are not confirmation evidence.

Ranks are one-based in the structural candidate ordering, after the 27 B2 verifications. For each target FLAT did find an agreement; therefore scanning through its verified prefix suffices to establish the exact first public-feasible and first mutually acceptable ranks. `best verified Nash` means the best among the candidates actually verified by FLAT, not the complete oracle space.

Percentiles: median / p75 / p90 / p95 / p99 / max, NumPy linear interpolation.

| Family | First public feasible | First mutually acceptable | FLAT selected | Best Nash among actually verified agreements |
|---|---:|---:|---:|---:|
| ALL | 1, 1, 1, 4, 79, 1009 (n=842) | 1, 1, 1, 10, 127, 1009 (n=842) | 1, 10, 10, 16, 127, 1009 (n=842) | 1, 1, 1, 10, 127, 1009 (n=842) |
| F1 | 1, 1, 1, 1, 10, 82 (n=234) | 1, 1, 1, 10, 82, 163 (n=234) | 1, 10, 10, 16, 82, 163 (n=234) | 1, 1, 1, 10, 82, 163 (n=234) |
| F2 | 1, 1, 1, 1, 1, 82 (n=122) | 1, 1, 9.1, 10, 127, 154 (n=122) | 1, 1, 9.1, 10, 127, 154 (n=122) | 1, 1, 9.1, 10, 127, 154 (n=122) |
| F3 | 1, 1, 1, 4.6, 61.84, 1009 (n=257) | 1, 1, 1, 10, 122.68, 1009 (n=257) | 1, 10, 10, 16, 122.68, 1009 (n=257) | 1, 1, 1, 10, 122.68, 1009 (n=257) |
| F4 | 1, 1, 1, 10, 79, 163 (n=229) | 1, 1, 1.6, 10, 79, 163 (n=229) | 1, 10, 10, 10, 79, 163 (n=229) | 1, 1, 1.6, 10, 79, 163 (n=229) |

GLOBAL has an untruncated grouped ranking and a different quota-truncated verification sequence. Its selected candidate’s grouped rank and actual structural verification ordinal, and the first mutually acceptable candidate found in the actual verification sequence, are below. Their totals exclude 27 B2 checks; a failed run can have no selected/first-success rank.

| Family | GLOBAL selected grouped rank | GLOBAL selected actual ordinal | First mutual actual ordinal |
|---|---:|---:|---:|
| ALL | 1, 1, 10, 811, 65017, 67177 (n=841) | 1, 1, 10, 129, 1938, 3538 (n=841) | 1, 1, 10, 129, 1938, 3538 (n=841) |
| F1 | 1, 1, 10, 41581, 65017, 65017 (n=234) | 1, 1, 10, 210, 1938, 1938 (n=234) | 1, 1, 10, 210, 1938, 1938 (n=234) |
| F2 | 1, 1, 42391, 42391, 42391, 67177 (n=122) | 1, 1, 338, 338, 338, 3538 (n=122) | 1, 1, 338, 338, 338, 3538 (n=122) |
| F3 | 1, 1, 1, 10, 42391, 42472 (n=256) | 1, 1, 1, 10, 338, 419 (n=256) | 1, 1, 1, 10, 338, 419 (n=256) |
| F4 | 1, 1, 1.6, 10, 10, 10 (n=229) | 1, 1, 1.6, 10, 10, 10 (n=229) | 1, 1, 1.6, 10, 10, 10 (n=229) |

# Depth-three exact frontier certificates

The independent checker used the fixed public profiles, operators, registry and packed semantics. It re-encoded emitted normalized witnesses, recomputed their score bits using the original NumPy FLAT `_proxy` and checked unique ordered `(score, signature)` keys. The check used no depth-three graph or historical rank array.

For each requested K, the certificate binds the emitted prefix by SHA-256 of successive big-endian binary64 scores and compact signature bytes. A nonempty frontier must have a strictly larger lower bound than the boundary score. A buffered complete candidate must sort strictly after the boundary key. A fully exhausted domain may certify a prefix shorter than K. These cases are counted separately from full-length certificates. This verifies the certificate against the documented admissible envelope. The lower-bound proof in the method documentation supplies the guarantee for subtrees the checker did not enumerate.

Validated 9,851 emitted records and 72 checkpoint rows. Unsound checkpoints: **0**.

| Instance | K | Status | Returned | Boundary score | Frontier min LB | Open frontier | Proof reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1__low__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0281005 | 0.0287924 | 6 |  |
| F1__low__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 81 | 0.0609781 | NA | 0 |  |
| F1__low__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 81 | 0.0609781 | NA | 0 |  |
| F1__low__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0200887 | 0.0205277 | 3013 |  |
| F1__low__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0239905 | 0.0241147 | 4265 |  |
| F1__low__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0248304 | 0.0248424 | 5308 |  |
| F1__medium__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0362264 | 0.0367346 | 2445 |  |
| F1__medium__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0423256 | 0.0423922 | 5384 |  |
| F1__medium__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.042731 | 0.042731 | 5582 |  |
| F1__medium__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.025804 | 0.0258706 | 1597 |  |
| F1__medium__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.026004 | 0.02604 | 1686 |  |
| F1__medium__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.026276 | 0.0263427 | 2147 |  |
| F1__high__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0317843 | 0.0321032 | 335 |  |
| F1__high__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0408924 | 0.0409327 | 5004 |  |
| F1__high__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0412946 | 0.0412946 | 5358 |  |
| F1__high__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.034827 | 0.0351907 | 779 |  |
| F1__high__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0411581 | 0.0412098 | 2649 |  |
| F1__high__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0418206 | 0.0418281 | 3053 |  |
| F2__low__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0287218 | 0.0287885 | 305 |  |
| F2__low__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0287885 | 0.0288552 | 498 |  |
| F2__low__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.029086 | 0.0291183 | 1274 |  |
| F2__low__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0286288 | 0.0286722 | 1662 |  |
| F2__low__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0286955 | 0.0287389 | 1991 |  |
| F2__low__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0289927 | 0.0290249 | 3020 |  |
| F2__medium__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.049658 | 0.0503667 | 284 |  |
| F2__medium__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0572388 | 0.0575932 | 330 |  |
| F2__medium__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0679476 | 0.0679851 | 508 |  |
| F2__medium__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0356618 | 0.0357285 | 976 |  |
| F2__medium__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0358988 | 0.0359654 | 1198 |  |
| F2__medium__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0361357 | 0.0361357 | 1550 |  |
| F2__high__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.308202 | 0.308894 | 3 |  |
| F2__high__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 27 | 0.462147 | NA | 0 |  |
| F2__high__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 27 | 0.462147 | NA | 0 |  |
| F2__high__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0409711 | 0.0410378 | 1271 |  |
| F2__high__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0412125 | 0.0412125 | 1503 |  |
| F2__high__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.041454 | 0.0415207 | 1810 |  |
| F3__low__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0220053 | 0.022072 | 550 |  |
| F3__low__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.022072 | 0.0221386 | 723 |  |
| F3__low__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0224032 | 0.0224435 | 1489 |  |
| F3__low__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0172159 | 0.0172826 | 2838 |  |
| F3__low__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0172826 | 0.0173493 | 3289 |  |
| F3__low__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.017612 | 0.0176786 | 3958 |  |
| F3__medium__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0262071 | 0.0265634 | 160 |  |
| F3__medium__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0330094 | 0.033205 | 237 |  |
| F3__medium__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.040168 | 0.0403116 | 502 |  |
| F3__medium__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0254485 | 0.025513 | 1887 |  |
| F3__medium__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0256485 | 0.0256796 | 1996 |  |
| F3__medium__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0259198 | 0.0259865 | 2487 |  |
| F3__high__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.043969 | 0.0441243 | 10 |  |
| F3__high__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 81 | 0.266984 | NA | 0 |  |
| F3__high__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 81 | 0.266984 | NA | 0 |  |
| F3__high__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0320044 | 0.032021 | 1041 |  |
| F3__high__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0322044 | 0.0322466 | 1098 |  |
| F3__high__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0324888 | 0.0325555 | 1554 |  |
| F4__low__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0249415 | 0.0250082 | 3182 |  |
| F4__low__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0251415 | 0.0251715 | 3291 |  |
| F4__low__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0254014 | 0.0254014 | 3792 |  |
| F4__low__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0251564 | 0.0252231 | 3182 |  |
| F4__low__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0253564 | 0.0253874 | 3291 |  |
| F4__low__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0256183 | 0.0256549 | 3792 |  |
| F4__medium__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0295455 | 0.0302531 | 6 |  |
| F4__medium__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 81 | 0.144064 | NA | 0 |  |
| F4__medium__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 81 | 0.144064 | NA | 0 |  |
| F4__medium__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0270454 | 0.0271121 | 1620 |  |
| F4__medium__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0272454 | 0.0272831 | 1709 |  |
| F4__medium__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0275207 | 0.0275873 | 2170 |  |
| F4__high__high__sparse__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0312167 | 0.0319408 | 6 |  |
| F4__high__high__sparse__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 81 | 0.258971 | NA | 0 |  |
| F4__high__high__sparse__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 81 | 0.258971 | NA | 0 |  |
| F4__high__high__rich__d2__s0 | 10 | EXACT_TOPK_CERTIFIED | 10 | 0.0425367 | 0.0426034 | 980 |  |
| F4__high__high__rich__d2__s0 | 100 | EXACT_TOPK_CERTIFIED | 100 | 0.0427367 | 0.0427802 | 1069 |  |
| F4__high__high__rich__d2__s0 | 500 | EXACT_TOPK_CERTIFIED | 500 | 0.0430236 | 0.0430903 | 1530 |  |

Machine-readable keys, digests and work counters are in `results/depth3/per_query.csv`.

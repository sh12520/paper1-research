# V1 runtime decomposition — development diagnostics

Measured 96 existing PILOT serialized instances, one seed-index 0 per public configuration; no instance or seed generation. Every timed method run was checked against the historical history prefix through the B=5,000 checkpoint and all non-timing fields for each checkpoint through 5,000, including offline uA/uN/Nash. For every expansion run, timed candidate order and public-plan fields were separately compared with the unmodified original make_plan. Timing reflects the instrumented implementation, so wrappers add overhead; the residual includes instrumentation overhead and unclassified work.

Online timing starts immediately before public view, public compatibility and private agent setup, and ends after runtime.run returns. It excludes instance file reads/deserialization, semantic library load/basis initialization, hook construction, offline witness re-verification, and the independent repeat of original public ranking. Exact verification is public V1–V4; bilateral protocol covers local private decisions. Mechanism probes include their own proxy features and scoring. Stage construction includes DG group ordering and quota-compatible candidate grouping. No full-space private evaluator is part of online timing.

The replay uses the original V1 fixed checkpoints through stop budget 5,000; a method can terminate earlier at agreement or exhaustion. Values in seconds. Percentages are sums of each exclusive phase divided by sum of total times, not an average of per-instance percentages. All-config cohort includes early B2 exits; recoverable cohort is the sampled B2-no-agreement/full-O1-agreement subset.

## all: FLAT-FEASIBILITY (n=96; public plan equality checks=78)

| Phase | Median | p90 | p95 | Mean | Share of total |
|---|---:|---:|---:|---:|---:|
| public_view_setup | 0.000753 | 0.001423 | 0.001613 | 0.000871 | 0.11% |
| plan_public_setup | 0.000313 | 0.000714 | 0.000770 | 0.000358 | 0.05% |
| conditioning | 0.125850 | 0.161063 | 0.175871 | 0.117742 | 15.51% |
| feature_calculation | 0.002087 | 1.858083 | 1.990500 | 0.458603 | 60.42% |
| proxy_score_calculation | 0.000068 | 0.054240 | 0.059629 | 0.012317 | 1.62% |
| sorting_topk | 0.000090 | 0.136211 | 0.152070 | 0.032508 | 4.28% |
| mechanism_probes | 0.000024 | 0.000047 | 0.000079 | 0.000028 | 0.00% |
| stage_construction | 0.000025 | 0.000055 | 0.000057 | 0.000026 | 0.00% |
| exact_verification | 0.005407 | 0.190464 | 0.359309 | 0.061041 | 8.04% |
| bilateral_protocol | 0.001624 | 0.088390 | 0.363493 | 0.053532 | 7.05% |
| representative_reconstruction | 0.000467 | 0.001655 | 0.001811 | 0.000633 | 0.08% |
| residual | 0.005513 | 0.053999 | 0.104044 | 0.021411 | 2.82% |
| total | 0.167795 | 2.401666 | 2.784466 | 0.759071 | 100.00% |

## all: DG-PCE (n=96; public plan equality checks=78)

| Phase | Median | p90 | p95 | Mean | Share of total |
|---|---:|---:|---:|---:|---:|
| public_view_setup | 0.000747 | 0.001342 | 0.001534 | 0.000841 | 0.11% |
| plan_public_setup | 0.000280 | 0.000668 | 0.000779 | 0.000343 | 0.05% |
| conditioning | 0.120727 | 0.151350 | 0.159128 | 0.113169 | 15.45% |
| feature_calculation | 0.001757 | 1.804683 | 1.864839 | 0.449284 | 61.32% |
| proxy_score_calculation | 0.000054 | 0.053109 | 0.058617 | 0.012855 | 1.75% |
| sorting_topk | 0.000082 | 0.118973 | 0.147234 | 0.030375 | 4.15% |
| mechanism_probes | 0.004610 | 0.008984 | 0.010127 | 0.004876 | 0.67% |
| stage_construction | 0.000254 | 0.057758 | 0.066783 | 0.013284 | 1.81% |
| exact_verification | 0.008505 | 0.169730 | 0.233558 | 0.045446 | 6.20% |
| bilateral_protocol | 0.003211 | 0.085080 | 0.165345 | 0.041796 | 5.70% |
| representative_reconstruction | 0.000525 | 0.001328 | 0.001459 | 0.000582 | 0.08% |
| residual | 0.005022 | 0.048415 | 0.071935 | 0.019851 | 2.71% |
| total | 0.163419 | 2.342323 | 2.665631 | 0.732702 | 100.00% |

## recoverable: FLAT-FEASIBILITY (n=37; public plan equality checks=37)

| Phase | Median | p90 | p95 | Mean | Share of total |
|---|---:|---:|---:|---:|---:|
| public_view_setup | 0.000765 | 0.001528 | 0.001761 | 0.000930 | 0.10% |
| plan_public_setup | 0.000337 | 0.000695 | 0.000767 | 0.000409 | 0.05% |
| conditioning | 0.133797 | 0.161805 | 0.165419 | 0.129482 | 14.53% |
| feature_calculation | 0.004079 | 1.893453 | 1.992265 | 0.679217 | 76.22% |
| proxy_score_calculation | 0.000120 | 0.054162 | 0.059754 | 0.017590 | 1.97% |
| sorting_topk | 0.000210 | 0.145854 | 0.156006 | 0.049639 | 5.57% |
| mechanism_probes | 0.000030 | 0.000047 | 0.000083 | 0.000034 | 0.00% |
| stage_construction | 0.000031 | 0.000055 | 0.000061 | 0.000033 | 0.00% |
| exact_verification | 0.004284 | 0.006667 | 0.008128 | 0.004713 | 0.53% |
| bilateral_protocol | 0.001464 | 0.002479 | 0.002912 | 0.001543 | 0.17% |
| representative_reconstruction | 0.001165 | 0.001842 | 0.001968 | 0.001287 | 0.14% |
| residual | 0.005449 | 0.010740 | 0.011648 | 0.006298 | 0.71% |
| total | 0.173546 | 2.257226 | 2.332250 | 0.891177 | 100.00% |

## recoverable: DG-PCE (n=37; public plan equality checks=37)

| Phase | Median | p90 | p95 | Mean | Share of total |
|---|---:|---:|---:|---:|---:|
| public_view_setup | 0.000792 | 0.001264 | 0.001501 | 0.000856 | 0.09% |
| plan_public_setup | 0.000344 | 0.000668 | 0.000674 | 0.000399 | 0.04% |
| conditioning | 0.122347 | 0.154445 | 0.167780 | 0.125818 | 13.23% |
| feature_calculation | 0.003201 | 1.826860 | 1.870691 | 0.678321 | 71.33% |
| proxy_score_calculation | 0.000111 | 0.055954 | 0.060984 | 0.019551 | 2.06% |
| sorting_topk | 0.000176 | 0.133761 | 0.159866 | 0.047249 | 4.97% |
| mechanism_probes | 0.006126 | 0.009117 | 0.009582 | 0.006135 | 0.65% |
| stage_construction | 0.000475 | 0.065115 | 0.069752 | 0.021991 | 2.31% |
| exact_verification | 0.008988 | 0.035743 | 0.065382 | 0.022521 | 2.37% |
| bilateral_protocol | 0.005802 | 0.034104 | 0.043109 | 0.017314 | 1.82% |
| representative_reconstruction | 0.000876 | 0.001648 | 0.002599 | 0.001174 | 0.12% |
| residual | 0.006073 | 0.014256 | 0.020300 | 0.009651 | 1.01% |
| total | 0.198106 | 2.308729 | 2.375174 | 0.950981 | 100.00% |

Memory telemetry (sampled every 250 ms): `{"emergency": false, "min_available": 3532304384, "peak_rss": 634060800}`.

These measurements are development engineering diagnostics, not confirmation evidence.

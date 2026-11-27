# INDEX-GATE-01 runtime

The table compares paired public search at K=500 on existing serialized instances. The FLAT measurement includes its complete conditioning, scoring and sorting. The retrieval measurement includes setup, node bounds, traversal and candidate scoring. The main replay runs serially within one worker and uses the same warm public graph. Graph and index build and load are accounted for separately. Preliminary engineering checks are outside these timing summaries.

| Cohort | Paired n | FLAT median / p95 s | Contract median / p95 s | p95 reduction |
| --- | --- | --- | --- | --- |
| target | 842/842 | 0.124843 / 1.805547 | 0.010324 / 0.308825 | 82.90% |
| large | 340/340 | 1.587407 / 1.931413 | 0.044335 / 0.484170 | 74.93% |
| rich_depth2 | 298/298 | 1.606237 / 1.930187 | 0.044228 / 0.467000 | 75.81% |

The gate uses 100 × (1 − indexed p95 / FLAT p95) for the same large-cohort IDs. Each quantile uses linear interpolation. The runtime CSV also records the mean and p90.

## Agreement replay at B=5,000

The indexed method extends the prefix only as verification asks for more candidates. These paired method timings use the actual stopping points.

| Cohort | Phase | Paired n | FLAT median / p95 s | Contract median / p95 s | p95 reduction |
| --- | --- | --- | --- | --- | --- |
| target | public_search_s | 842/842 | 0.124843 / 1.805547 | 0.004076 / 0.037829 | 97.90% |
| target | total_method_s | 842/842 | 0.129756 / 1.811733 | 0.009131 / 0.044220 | 97.56% |
| large | public_search_s | 340/340 | 1.587407 / 1.931413 | 0.009707 / 0.081385 | 95.79% |
| large | total_method_s | 340/340 | 1.595755 / 1.945815 | 0.014941 / 0.088743 | 95.44% |
| rich_depth2 | public_search_s | 298/298 | 1.606237 / 1.930187 | 0.009707 / 0.074250 | 96.15% |
| rich_depth2 | total_method_s | 298/298 | 1.610529 / 1.941543 | 0.014941 / 0.079844 | 95.89% |

## topk at 500

| Cohort | Variant | Phase | n | Median s | p90 s | p95 s | Mean s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target | flat | query_setup_s | 842 | 0.045776 | 0.058872 | 0.065961 | 0.047762 |
| target | flat | flat_feature_s | 842 | 0.002670 | 1.478884 | 1.561439 | 0.566058 |
| target | flat | total_public_search_s | 842 | 0.124843 | 1.718695 | 1.805547 | 0.724449 |
| target | contract | query_setup_s | 842 | 0.000069 | 0.000168 | 0.000221 | 0.000093 |
| target | contract | node_bound_s | 842 | 0.003153 | 0.054723 | 0.153980 | 0.023323 |
| target | contract | traversal_s | 842 | 0.003145 | 0.033860 | 0.088444 | 0.015107 |
| target | contract | candidate_scoring_s | 842 | 0.003381 | 0.027807 | 0.075366 | 0.013373 |
| target | contract | total_public_search_s | 842 | 0.010324 | 0.119548 | 0.308825 | 0.052534 |
| target | generic | query_setup_s | 842 | 0.000079 | 0.000196 | 0.000259 | 0.000104 |
| target | generic | node_bound_s | 842 | 0.072144 | 0.185111 | 0.278365 | 0.090062 |
| target | generic | traversal_s | 842 | 0.052661 | 0.114375 | 0.170871 | 0.059627 |
| target | generic | candidate_scoring_s | 842 | 0.020333 | 0.082359 | 0.119848 | 0.033277 |
| target | generic | total_public_search_s | 842 | 0.144821 | 0.375852 | 0.560690 | 0.183722 |
| large | flat | query_setup_s | 340 | 0.045639 | 0.060164 | 0.067527 | 0.048091 |
| large | flat | flat_feature_s | 340 | 1.350484 | 1.589974 | 1.697113 | 1.394478 |
| large | flat | total_public_search_s | 340 | 1.587407 | 1.822782 | 1.931413 | 1.634065 |
| large | contract | query_setup_s | 340 | 0.000075 | 0.000173 | 0.000261 | 0.000099 |
| large | contract | node_bound_s | 340 | 0.017277 | 0.161890 | 0.237345 | 0.052788 |
| large | contract | traversal_s | 340 | 0.012335 | 0.097723 | 0.139239 | 0.032851 |
| large | contract | candidate_scoring_s | 340 | 0.014066 | 0.085915 | 0.108317 | 0.028204 |
| large | contract | total_public_search_s | 340 | 0.044335 | 0.341734 | 0.484170 | 0.114612 |
| large | generic | query_setup_s | 340 | 0.000086 | 0.000204 | 0.000260 | 0.000112 |
| large | generic | node_bound_s | 340 | 0.062603 | 0.312590 | 0.394236 | 0.120306 |
| large | generic | traversal_s | 340 | 0.035009 | 0.180505 | 0.251390 | 0.071350 |
| large | generic | candidate_scoring_s | 340 | 0.023045 | 0.125015 | 0.212997 | 0.053422 |
| large | generic | total_public_search_s | 340 | 0.121279 | 0.628521 | 0.859865 | 0.245871 |
| rich_depth2 | flat | query_setup_s | 298 | 0.045627 | 0.060870 | 0.068682 | 0.048160 |
| rich_depth2 | flat | flat_feature_s | 298 | 1.353545 | 1.584371 | 1.693289 | 1.395105 |
| rich_depth2 | flat | total_public_search_s | 298 | 1.606237 | 1.821938 | 1.930187 | 1.635382 |
| rich_depth2 | contract | query_setup_s | 298 | 0.000073 | 0.000164 | 0.000224 | 0.000096 |
| rich_depth2 | contract | node_bound_s | 298 | 0.017277 | 0.157864 | 0.219021 | 0.051476 |
| rich_depth2 | contract | traversal_s | 298 | 0.012245 | 0.094493 | 0.138279 | 0.032149 |
| rich_depth2 | contract | candidate_scoring_s | 298 | 0.014066 | 0.084306 | 0.106476 | 0.027660 |
| rich_depth2 | contract | total_public_search_s | 298 | 0.044228 | 0.325129 | 0.467000 | 0.112057 |
| rich_depth2 | generic | query_setup_s | 298 | 0.000087 | 0.000191 | 0.000249 | 0.000110 |
| rich_depth2 | generic | node_bound_s | 298 | 0.062603 | 0.305071 | 0.387934 | 0.119209 |
| rich_depth2 | generic | traversal_s | 298 | 0.035009 | 0.177413 | 0.244353 | 0.070571 |
| rich_depth2 | generic | candidate_scoring_s | 298 | 0.023440 | 0.124042 | 0.210204 | 0.052653 |
| rich_depth2 | generic | total_public_search_s | 298 | 0.121279 | 0.614235 | 0.827345 | 0.243232 |

## agreement at 5000

| Cohort | Variant | Phase | n | Median s | p90 s | p95 s | Mean s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target | flat | public_search_s | 842 | 0.124843 | 1.718695 | 1.805547 | 0.724449 |
| target | flat | query_setup_s | 842 | 0.045776 | 0.058872 | 0.065961 | 0.047762 |
| target | flat | flat_feature_s | 842 | 0.002670 | 1.478884 | 1.561439 | 0.566058 |
| target | flat | exact_verification_s | 842 | 0.002646 | 0.004240 | 0.005072 | 0.002955 |
| target | flat | negotiation_s | 842 | 0.000928 | 0.001828 | 0.002301 | 0.001119 |
| target | flat | reconstruction_s | 842 | 0.000639 | 0.001471 | 0.001916 | 0.000861 |
| target | flat | total_method_s | 842 | 0.129756 | 1.724680 | 1.811733 | 0.730076 |
| target | contract | public_search_s | 842 | 0.004076 | 0.026605 | 0.037829 | 0.010657 |
| target | contract | query_setup_s | 842 | 0.000584 | 0.001005 | 0.001204 | 0.000661 |
| target | contract | node_bound_s | 842 | 0.001420 | 0.012233 | 0.018121 | 0.004675 |
| target | contract | traversal_s | 842 | 0.000917 | 0.006943 | 0.009961 | 0.002726 |
| target | contract | candidate_scoring_s | 842 | 0.000965 | 0.006634 | 0.010752 | 0.002568 |
| target | contract | exact_verification_s | 842 | 0.002372 | 0.004044 | 0.005052 | 0.002766 |
| target | contract | negotiation_s | 842 | 0.000887 | 0.001845 | 0.002326 | 0.001079 |
| target | contract | reconstruction_s | 842 | 0.000601 | 0.001411 | 0.001783 | 0.000800 |
| target | contract | total_method_s | 842 | 0.009131 | 0.032192 | 0.044220 | 0.015732 |
| large | flat | public_search_s | 340 | 1.587407 | 1.822782 | 1.931413 | 1.634065 |
| large | flat | query_setup_s | 340 | 0.045639 | 0.060164 | 0.067527 | 0.048091 |
| large | flat | flat_feature_s | 340 | 1.350484 | 1.589974 | 1.697113 | 1.394478 |
| large | flat | exact_verification_s | 340 | 0.002693 | 0.004522 | 0.005430 | 0.003174 |
| large | flat | negotiation_s | 340 | 0.000976 | 0.001909 | 0.002302 | 0.001260 |
| large | flat | reconstruction_s | 340 | 0.000792 | 0.001822 | 0.002172 | 0.001037 |
| large | flat | total_method_s | 340 | 1.595755 | 1.829760 | 1.945815 | 1.640299 |
| large | contract | public_search_s | 340 | 0.009707 | 0.039722 | 0.081385 | 0.020859 |
| large | contract | query_setup_s | 340 | 0.000595 | 0.001029 | 0.001294 | 0.000687 |
| large | contract | node_bound_s | 340 | 0.004339 | 0.019450 | 0.041750 | 0.009718 |
| large | contract | traversal_s | 340 | 0.002431 | 0.010327 | 0.022502 | 0.005479 |
| large | contract | candidate_scoring_s | 340 | 0.002359 | 0.010927 | 0.016699 | 0.004940 |
| large | contract | exact_verification_s | 340 | 0.002463 | 0.004009 | 0.004832 | 0.002914 |
| large | contract | negotiation_s | 340 | 0.000892 | 0.001769 | 0.002185 | 0.001103 |
| large | contract | reconstruction_s | 340 | 0.000662 | 0.001543 | 0.002036 | 0.000894 |
| large | contract | total_method_s | 340 | 0.014941 | 0.047698 | 0.088743 | 0.026253 |
| rich_depth2 | flat | public_search_s | 298 | 1.606237 | 1.821938 | 1.930187 | 1.635382 |
| rich_depth2 | flat | query_setup_s | 298 | 0.045627 | 0.060870 | 0.068682 | 0.048160 |
| rich_depth2 | flat | flat_feature_s | 298 | 1.353545 | 1.584371 | 1.693289 | 1.395105 |
| rich_depth2 | flat | exact_verification_s | 298 | 0.002688 | 0.004510 | 0.005443 | 0.003136 |
| rich_depth2 | flat | negotiation_s | 298 | 0.000974 | 0.001909 | 0.002328 | 0.001283 |
| rich_depth2 | flat | reconstruction_s | 298 | 0.000793 | 0.001771 | 0.002115 | 0.001001 |
| rich_depth2 | flat | total_method_s | 298 | 1.610529 | 1.829313 | 1.941543 | 1.641565 |
| rich_depth2 | contract | public_search_s | 298 | 0.009707 | 0.039253 | 0.074250 | 0.019395 |
| rich_depth2 | contract | query_setup_s | 298 | 0.000597 | 0.001032 | 0.001298 | 0.000690 |
| rich_depth2 | contract | node_bound_s | 298 | 0.004374 | 0.019094 | 0.031755 | 0.008949 |
| rich_depth2 | contract | traversal_s | 298 | 0.002431 | 0.010229 | 0.019328 | 0.005053 |
| rich_depth2 | contract | candidate_scoring_s | 298 | 0.002359 | 0.010811 | 0.016419 | 0.004675 |
| rich_depth2 | contract | exact_verification_s | 298 | 0.002448 | 0.003903 | 0.004714 | 0.002883 |
| rich_depth2 | contract | negotiation_s | 298 | 0.000890 | 0.001772 | 0.002163 | 0.001120 |
| rich_depth2 | contract | reconstruction_s | 298 | 0.000653 | 0.001512 | 0.001898 | 0.000861 |
| rich_depth2 | contract | total_method_s | 298 | 0.014941 | 0.045448 | 0.079844 | 0.024735 |

FLAT's `flat_feature_s` records its original proxy feature calculation. The full FLAT plan time also includes its scalar score combination and complete sort. For fixed-K indexed rows, the cursor setup phase is reported separately from other setup included in the total, such as the public view and static lookup. The agreement replay includes candidate retrieval, exact verification, negotiation and reconstruction at the recorded checkpoints. The two experiment types have separate timing boundaries and CSV entries. Use the raw rows to inspect phase totals and any overhead outside the named phases.

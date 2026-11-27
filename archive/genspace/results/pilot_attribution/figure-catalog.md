# Figure catalog — exploratory PILOT attribution

Both plots use the original serialized PILOT instance as the unit of analysis.
They are descriptive post-PILOT figures, not confirmation evidence. They show
no confidence intervals, hypothesis tests, or research-gate decisions.

## mechanism_attribution_by_family

- Purpose: distinguish whether OFFLOAD alone suffices, whether OFFLOAD is
  necessary, and whether a no-OFFLOAD structural space suffices.
- Data: `results/pilot_attribution/family_summary.csv`. Each denominator is
  the family count with B2 deadlock and full O1 agreement. Labels show counts
  over denominators. The three conditions can overlap and are not a partition.
- Caption: specify the exact semantic-space definitions and the per-family
  denominator; clarify the same-instance, exploratory scope.
- Interpretation checklist: compare relative frequencies and raw denominators;
  no single selected representative determines necessity; no causal or network
  deployment conclusion follows solely from these bars.

## same_instance_depth_by_family

- Purpose: identify agreements that appear only when the *same original
  depth-2 instance* is evaluated in the nested depth≤2 rather than depth≤1
  space.
- Data: family rows of `results/pilot_attribution/depth_summary.csv`. Bars are
  a partition of all original depth-2 instances per family; segment labels
  are instance counts. Do not compare separately sampled depth-1 configurations.
- Caption: state nested-space construction and denominators; no uncertainty
  intervals are shown.
- Interpretation checklist: focus on the incremental segment and its raw count,
  not on the size of the depth-2 candidate library. Depth attribution is
  conditional on this abstract benchmark and current fixed distribution.

## Observed descriptive counts

- OFFLOAD necessity and OFFLOAD-only sufficiency, respectively: F1: 177/234 necessary, 213/234 sufficient alone, F2: 121/122 necessary, 99/122 sufficient alone, F3: 194/257 necessary, 242/257 sufficient alone, F4: 229/229 necessary, 229/229 sufficient alone. The two categories are not disjoint.
- Additional agreements at depth≤2 on the same instances: F1: 12/240, F2: 23/240, F3: 5/240, F4: 0/240. These counts distinguish depth-specific existence evidence from separately sampled group comparisons.

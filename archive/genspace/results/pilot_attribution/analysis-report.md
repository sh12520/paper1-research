# Exploratory mechanism-attribution analysis

This analysis reuses 1,920 serialized PILOT instances and the fixed abstract benchmark; it does not create experimental samples or provide confirmation evidence. See `PILOT_MECHANISM_ATTRIBUTION_REPORT.md` for the exact 16-subset matrix, `PILOT_OFFLOAD_ATTRIBUTION.md` for sufficiency and necessity, and `PILOT_SAME_INSTANCE_DEPTH_ANALYSIS.md` for the nested-depth comparison.

The targeted set is the 842 instances where B2 has no agreement and full O1 does. OFFLOAD-only is sufficient in 783, no-OFFLOAD is sufficient in 121, and OFFLOAD is necessary in 721; sufficiency categories may overlap. Forty instances require multiple mechanism groups, all involving OFFLOAD. These are exactly the 40 depth-2-only cases observed in the original depth-2 instances, not two independent groups of evidence.

`figure-catalog.md` documents two exported descriptive figures and their denominators. Exact instance and subset records are in `per_instance.csv`; family, subset, minimal-set and same-instance depth tables are provided alongside it. The independent integrity report states the scope of the semantic-space proof, reproducibility and original-artifact checks.

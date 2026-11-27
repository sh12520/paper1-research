# Figure catalog

## Candidate work

- File: `figures/figure_01_candidate_work.pdf` and `.png`.
- Purpose: compare the distribution of structural proxy scores with exact calls for the same 842 target instances. The dashed line marks the number of full-graph role-metadata records scanned; it is not an additional proxy-scoring or verification distribution.
- Axes and uncertainty: empirical cumulative fractions, logarithmic count axis; no confidence intervals. Exact calls include 27 B2 checks.
- Caption guidance: identify the development cohort, paired instance unit, B=5,000 checkpoint and three distinct units of work.
- Interpretation: the distance between curves shows why counting exact calls alone omits substantial candidate work. The cost distribution is heterogeneous and the full-graph line describes this implementation's metadata pass, not proof of a lower bound.

## First mutually acceptable rank

- File: `figures/figure_02_first_mutual_rank.pdf` and `.png`.
- Purpose: show the offline first mutually acceptable structural position within each family, not the verifier batch count or the protocol's selected position.
- Axes and uncertainty: empirical cumulative fractions within each family, one-based logarithmic rank axis; no confidence intervals.
- Caption guidance: identify the 842 target instances and note that private acceptance was inspected only after the public ranking had been reconstructed.
- Interpretation: rank one is common, but the observed upper tail and family mix remain relevant. A rank found offline is unavailable to the method before verification; the plot does not demonstrate online early stopping or generalization.

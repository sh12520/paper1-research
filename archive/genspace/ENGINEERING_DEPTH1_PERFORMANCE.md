# Depth-1 engineering performance fixture

Purpose: implementation timing only, not research outcomes. The script `python -m src.engineering_perf` generated 20 instances solely in `GENSPACE-FAIL-01-ENGINEERING`, with rich capability availability and depth 1. It precomputed one semantic library and reused it across all fixtures after checking the public grammar/registry basis hash. The benchmark does not write acceptance rates or other outcomes.

On this run, the library contained 1,539 semantic signatures and took 0.8610 seconds to precompute. Per-instance signature rechecking plus combined V1–V5 execution had median 1.7145 seconds, minimum 1.6083 seconds and maximum 1.9688 seconds.

These are depth-1 engineering timings only. They do not establish depth-2 semantic equality or feasibility, omit representative selection and runner/output overhead, do not split V2–V4 from V5, and are not sufficient to pass the user's engineering gate. No SMOKE, PILOT or CONFIRM instance was executed.

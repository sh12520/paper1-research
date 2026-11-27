# Capability-conditioned witness index audit

Status: engineering precomputation completed. This document does not authorize SMOKE, PILOT, or CONFIRM. The index addresses a previously identified discrepancy: rich-grammar redundant lexical witnesses may use unavailable structural operators even when their normalized semantic class is available.

The four low bits encode availability of IF (both roles), SEQUENCE, DELAY, and OFFLOAD (both roles); bit 4 encodes validity. Patterns 16–31 cover the configured 16 masks; pattern 0 is NO_STRUCTURAL_CAPABILITY. Base/static roles remain in the precomputation; if missing at execution they must fail V2 rather than disappear from the generated universe. Provider substitution must be resolved by equivalent public descriptors before selecting the pattern. Unsupported masks must fail closed.

For each pattern the builder generated the depth≤2 public semantic graph with a pattern-specific lexical witness for every generated class, checked its entire generated signature set against rich-graph signatures filtered by that pattern’s structural role mask, and compared full-27-profile depth1 lexical witnesses to legacy syntactic enumeration. A separate two-profile exhaustive test compared legacy depth1 and depth2 semantic sets and exact lexical witnesses for all 17 patterns. Full-27-profile depth2 independent syntactic witness comparison for all patterns is not yet completed.

| Pattern | Depth≤1 classes | Depth≤2 classes | Set mismatches | File bytes | Seconds |
|---:|---:|---:|---:|---:|---:|
| 16 | 54 | 54 | 0 | 10,640 | 0.208 |
| 17 | 756 | 2,943 | 0 | 24,390 | 22.922 |
| 18 | 783 | 41,607 | 0 | 111,065 | 23.391 |
| 19 | 1,485 | 1,222,560 | 0 | 2,806,753 | 181.209 |
| 20 | 81 | 162 | 0 | 11,135 | 0.209 |
| 21 | 783 | 6,669 | 0 | 33,457 | 25.801 |
| 22 | 810 | 44,685 | 0 | 118,595 | 23.747 |
| 23 | 1,512 | 1,288,278 | 0 | 2,926,404 | 182.304 |
| 24 | 81 | 108 | 0 | 11,025 | 0.260 |
| 25 | 783 | 6,615 | 0 | 34,075 | 24.892 |
| 26 | 810 | 64,260 | 0 | 161,611 | 25.047 |
| 27 | 1,512 | 1,326,105 | 0 | 3,007,937 | 180.436 |
| 28 | 108 | 243 | 0 | 11,573 | 0.346 |
| 29 | 810 | 11,826 | 0 | 45,988 | 25.274 |
| 30 | 837 | 68,121 | 0 | 170,827 | 28.091 |
| 31 | 1,539 | 1,394,064 | 0 | 3,139,628 | 195.963 |
| 0 | 27 | 27 | 0 | 10,309 | 0.136 |

Total wall time **943.91 s**; observed peak RSS **699,772,928 bytes**. Total 17 compressed artifacts **12,635,412 bytes**. Manifest SHA-256 `0ffe3360afd73e63e57ba130ade9de703c68e2e69fc599f0da43d0cacaa441bf`.

Independent artifact verification recomputed all 17 file SHA-256 values, checked per-file header and size, rich graph binding, configuration hash, full vector length, present-mask count and depth1 witness count. The rich variant shares the exact witness-pool/operator/parameter metadata and all **1,394,064** witness pointers byte-for-byte with the separately preserved rich semantic graph. In the negative control, generated semantic signatures equal the **27** B2 static signatures exactly, and every d2 and d1 witness is Static.

Each artifact stores a sorted witness pool in its JSON header and a class-aligned 7-byte token per rich class (`>BHHH`), with 0xFF in the first byte marking NOT_GENERATED; the header separately holds depth1 class IDs and exact lexical witnesses. No private preferences or utility enter construction. The builder generated only one ENGINEERING public basis instance; no study seed was generated or read.

The manifest captures per-file source hashes and config hash at build; the fingerprint was unchanged at the end of the run. Subsequent changes to the runner/loader require a new full execution snapshot and an explicit unchanged semantic-core/builder/config/graph reconciliation. The recorded `fingerprint()` dependency metadata does not itself include NumPy. A contemporaneous external observation, `results/engineering/availability_indices/build_environment_observation.json`, records the builder PID/executable, Python version, NumPy version and executable SHA-256; NumPy package bytes were not independently hashed.

These files are untrusted until their manifest, source/core/config/graph binding and individual SHA-256 hashes are validated fail closed. Unsupported availability patterns must not fall back to rich witnesses. Corrected runner integration, complete four-family differential evidence, fresh snapshot and quiet performance gates remain outstanding.

# PAPER-BASELINE-ABLATION-01 · Cost accounting and comparator fairness

The public comparison uses identical serialized development queries, effective depth, capability availability, eligible canonical semantic classes, FLAT binary64 arithmetic and unsigned lexicographic signature tie order. The structural domain through depth two has one or two groups. Depth three has one through four groups. Full FLAT and both index controls are applicable only through depth two. Entries for their depth-three timing, working set and coverage are N/A. [Frozen domain and correctness scope](DEPTH3_SOUNDNESS_REVIEW.md)

## Resource and timing boundaries

| Quantity | Measurement boundary and interpretation |
|---|---|
| Warm public query | From query setup and capability conditioning to an exact Top-K checkpoint or detected limit. It includes scoring, frontier work, ordered emissions and witness construction. Graph and index assets are resident before the clock starts. Search continued after a valid cutoff in the no-lazy-stop ablation has its own additional-work boundary. |
| Bilateral prefix replay | The unchanged B2 stage, exact verifier, batching and bilateral protocol replay the already-certified structural prefix. A replay can complete at budget 5,000 when the protocol terminates within that prefix. Where a later budget needs unseen candidates, report only supported checkpoints or an insufficient-prefix status. The replay never substitutes prefix exhaustion for whole-domain exhaustion and its time is separate from warm public Top-K. |
| Fresh-process setup | Record verified graph load, availability load, public-basis binding, shared features load and tree loads separately. A cold-start comparison is defined as a fresh process with an uncontrolled filesystem page cache. The setup manifest and comparisons must state if subprocess/Python imports are in the measured boundary. |
| RSS | The Windows working set is a process quantity. Distinguish observed peak within the query window, OS lifetime peak, and the resident asset baseline. A process loading both trees has a shared memory baseline. That peak cannot be attributed to a standalone tree or to query allocation alone. |
| Mutable costs | On-demand template/shape construction, equivalence tracking, assignment expansion and witness recovery are charged to the query whenever the method performs them. Public graph construction, fixed arrays and tree construction are charged offline. |
| Work | Grammar partial expansions, concrete AST materializations, partition probes and lower bounds are separate quantities. For graph methods use graph records inspected, conditioned semantic records scored, internal/leaf nodes visited, graph-node bound requests and canonical witnesses materialized. Missing/non-applicable counts remain empty. |
| Censoring | Report completion and resource-limited counts alongside timing quantiles. The elapsed time of a capped query is a lower bound on its time to a later certificate. A completed-only median or p95 is conditional and potentially selective. Include paired matched-complete effects and all-query coverage or a prespecified cap-penalized analysis. |

The graph controls use the archived FLAT plan and the archived two index kernels. The wrapper observes the score vector passed to the one FLAT lexicographic sort. It performs no duplicate approximate or exact public scoring pass. The three controls fetch the normalized canonical witness only for candidates delivered to the interface. The pure Top-K lane omits the separate protocol B2 stage for all methods. The bilateral replay charges the original 27 B2 calls. [Graph controls](results/paper_method_dev/index_controls.py) · [FLAT plan](results/method_dev_v1/public_search.py) · [Index cursor](results/index_gate/index_query.py)

The warm comparison interleaves the fixed queries and rotates method order deterministically. A graph worker and a graph-free worker stay resident. The controller sends one attempt at a time and receives its result before sending the next. The other worker sits idle, so no two method queries compete for CPU, although both resident working sets contribute to overall memory pressure. The warm graph worker keeps both tree variants resident and its RSS includes the graph, availability bundle and both indices. Process RSS measures that allocation along with transient work.

All methods share the effective-depth wall allowance of 12 seconds for depth≤2 or 45 seconds for depth 3 and the 2 GiB working-set ceiling. The 300,000/180,000 and 2,000,000/260,000 depth-specific expansion/frontier limits apply in their documented search units. Graph-node visits and syntactic states retain different counters. The controller's system-available memory thresholds are 1,280 MiB before a run and 768 MiB during samples. These are the development-run settings. The cold-start diagnostic uses fresh children with an uncontrolled filesystem page cache. [Development plan](results/paper_method_dev/development_plan.json) · [Warm comparison implementation](results/paper_method_dev/run_comparison.py)

For graph-backed order, class IDs are positions of ascending packed signatures. In each index frontier the node pair is `(score lower bound, minimum possible class ID)`. Every descendant key is lexicographically at least that pair. Equality on the score coordinate remains certifiable only when the node's lower class ID sorts after the emitted key. Buffer the minimum complete key separately. Both tests use the same final exact order as the grammar cursor. The unresolved-state counts and lower-bound units differ across the two methods. [Index bound](INDEX_BOUND_SPEC.md) · [Historical certificate rationale](DEPTH3_SOUNDNESS_REVIEW.md)

## Archived offline build and storage

The oldest graph and availability builds and the later index build ran in separate engineering processes. Their measurements are included as provenance. No graph, availability bundle or index is rebuilt for the development comparison. Add elapsed build phases when estimating total startup work. Use the maximum of measured phase peaks only as an observed offline high-water reading. Phases with unmeasured peaks can exceed that reading.

| Artifact or phase | Archived time | Process peak working set | Serialized bytes |
|---|---:|---:|---:|
| Complete depth≤2 graph | 198.097 s precompute + 12.211 s serialization/statistics | 358,879,232 during graph precompute | 7,464,460 |
| 17 capability-conditioned witness/availability artifacts | 943.91 s | 699,772,928 observed | 12,635,412 compressed data, 12,646,343 including manifest |
| Shared index feature arrays | 0.894671 s feature construction | See combined index build | 51,583,460 |
| Generic multidimensional tree | 8.932863 s tree build | See combined index build | 51,019,057 |
| Contract-aware forest | 10.342719 s tree build | See combined index build | 55,036,723 |
| Index package with both trees | 20.866014 s build and serialization, excluding graph boot | 864,468,992 | 157,648,503 including manifest |

Direct package totals including the graph and availability bundle are 20,110,803 bytes for Full FLAT and 177,759,306 bytes for a worker loading both indices. Counting only each index's required shared and dedicated arrays gives 122,713,320 bytes for the generic lane or 126,730,986 for the contract-aware lane, plus a separate index-manifest share. These single-lane totals describe physical asset requirements. They do not represent observed single-lane peak working sets.

The existing paired cold-load audit observed 0.575719 s graph load plus 0.915661 s availability load. Its 0.550733 s combined index load includes 0.191405 s shared features, 0.115131 s generic tree and 0.238634 s contract tree. The combined load process reached 503,382,016 bytes peak working set. Use new measured setup phase clocks for the run's cold-start estimate and display these historical numbers as archival provenance. [Semantic graph audit](SEMANTIC_LIBRARY_AUDIT.md) · [Availability audit](AVAILABILITY_INDEX_AUDIT.md) · [Index build and load audit](INDEX_COST_REPORT.md)

## Graph adapter precheck

All three graph controls passed 24 checkpoint comparisons in a narrow precheck of two existing queries at K=10/50/100/500. The test compared ordered compact identities, binary64 scores, normalized representatives, indexed frontier tuples and complete buffers against the sealed depth-two reference. The sparse F4 query exhausted at 81 structural signatures. The rich F1 query returned the exact 500-record prefix from 1,252,611 conditioned classes. This read-only precheck is separate from the rotated comparison. [Sealed depth-two regression](DEPTH2_REGRESSION_REPORT.md)

The first adapter trial in the system Python failed the executable snapshot's version check before graph load. The precheck used the original CPython 3.12.14 and NumPy 2.3.5 runtime, where verification succeeded without an authorization or snapshot change. Its fresh-process resident setup for both trees was 4.690 s, including 0.769 s graph verification and load, 0.942 s availability load, 2.434 s public-basis binding and 0.410 s index setup. These phase measurements exclude imports.

## Isolated cold-start observations

The cold diagnostic used the fixed `F1__low__medium__sparse__d1__s0` fixture. Five sequential fresh suspended children ran one primary method each. No child loaded an unrelated tree. All five certified the same 500 entries, matching the sealed signatures, binary64 scores and normalized witnesses. All jobs ended with zero active processes. The system's minimum available memory was 2,304.72 MiB. File-cache state was uncontrolled. The latencies are single-query diagnostics and do not estimate the panel's cold p95. [Cold diagnostic results](results/paper_method_dev/cold_start_costs.json) · [Diagnostic implementation](results/paper_method_dev/cold_start_diagnostic.py)

| Primary method | Verified setup s | First public query s | Child init through query s | Parent launch through child exit s | Resident after setup MiB | OS lifetime peak MiB |
|---|---:|---:|---:|---:|---:|---:|
| FULL_FLAT | 3.7680 | 0.0789 | 4.0526 | 4.2534 | 386.16 | 501.76 |
| GENERIC_INDEX | 4.0086 | 0.1996 | 4.4149 | 4.5880 | 484.09 | 501.89 |
| CONTRACT_AWARE_INDEX | 3.6857 | 0.0249 | 3.9147 | 4.1059 | 488.08 | 501.92 |
| GENERIC_ABSTRACT_BEST_FIRST | 0.0045 | 0.4797 | 0.7255 | 0.9016 | 34.06 | 35.51 |
| CURRENT_ON_DEMAND_GRAMMAR_SEARCH | 0.0109 | 0.0964 | 0.2965 | 0.4399 | 34.21 | 35.38 |

Verified setup starts after the common fixture projection. It includes method-specific imports and all applicable artifact loads. Child init aggregates common imports and fixture projection, setup, and query execution. Parent launch through exit also includes interpreter startup and the completed child's prefix-check and output overhead. For graph lanes the working set includes both the graph and all 17 availability artifacts. Generic and contract-aware index workers loaded only their own trees. Graph-free ablations share the on-demand route's offline asset boundary. Each switch's distinct runtime and memory cost comes from the rotated warm panel.

## Multi-query cost comparison

For an observed ordered batch of N queries, report the time sum `C(N) = offline build + asset setup + Σ query elapsed_i`. The new-deployment scenario charges graph construction and availability builds once for any graph-based route. The reuse scenario starts from persisted, verified assets and charges load. The on-demand route charges its query-time synthesis and cache work to each run and reports its ordinary process setup separately. When several methods share a built graph, show the shared cost once and the incremental cost for each tree. Use measured batch sums and make any hypothetical amortization assumptions explicit. Cold startup and observed pairwise query timings must stay separate. A throughput or break-even calculation depends on completion and comparably certified result scope.

Observed common graph prerequisites sum to 1,154.218 s of offline work across the archived graph-build, graph-serialization and availability-build phases. This common work alone contributes 11.542 s/query over 100 queries or 1.154 s/query over 1,000. Building the archived package with both trees adds 20.866 s once, or 0.209 s/query and 0.021 s/query at those respective sizes. These are fixed-work amortizations before online elapsed time. In deployment with already-verified persisted assets, omit the construction term and retain graph, availability, basis and applicable index setup. The graph-free methods require no persisted semantic-class or tree assets. They still incur interpreter startup and their query-time preparation.

## Observed warm batch of 96 original-depth queries

| Method | K=500 exact delivered | Warm elapsed sum, s | Warm elapsed per query, s |
|---|---:|---:|---:|
| Full FLAT | 96/96 | 65.127 | 0.678 |
| Generic index | 96/96 | 29.585 | 0.308 |
| Contract-aware index | 96/96 | 17.485 | 0.182 |
| Current on-demand grammar search | 96/96 | 23.053 | 0.240 |
| Generic abstract best-first | 92/96 | 158.984 | 1.656 |

The generic synthesis sum includes four timed-out attempts. Its observed sum describes work within the limit. The shared warm graph process loaded its verified graph, availability bundle and both trees in 3.575 s before timing the panel. Its process RSS therefore includes both trees. Across all 1,248 attempt windows the maximum sampled working set was 567.03 MiB. The lowest available physical memory measured at a query boundary was 2,238.02 MiB. [Per-query results](results/paper_method_dev/per_query.csv) · [Resident-worker setup](results/paper_method_dev/worker_startup.json)

On this complete warm batch the contract-aware index used 5.568 fewer seconds of retrieval than the current method. Persistent assets, verified setup and the number of repeated queries determine the net comparison. The observed warm totals and cold setup sample are presented separately so this trade-off remains visible.

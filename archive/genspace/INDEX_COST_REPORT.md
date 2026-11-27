# INDEX-GATE-01 work and storage

TouchRatio divides complete candidate records inspected by the original FLAT conditioned structural count. A metadata or node-bound check is tallied separately from a complete candidate record and an exact public score. NodeVisitRatio divides internal node visits by the internal node denominator recorded for that query. Pruned counts are reported with the counting boundary of the implementation.

For indexed prefixes, a candidate whose complete features were loaded for scoring is counted once. Bound-pruned candidates are eligible candidates left unscored at the returned cutoff. The count can fall for a longer prefix. FLAT metadata passes, leaf membership checks and internal-node pops have separate fields.

| Contract K=500 cohort | Paired n | TouchRatio median / p95 | Coverage ≤5% | Coverage ≤1% | Internal visits median / p95 | NodeVisitRatio median / p95 | Exact scores median / p95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target | 842/842 | 55.4894% / 100.0000% | 347/842 (41.21%) | 270/842 (32.07%) | 62.00 / 4,106.45 | 0.0870% / 5.7640% | 1,243.00 / 26,876.50 |
| large | 340/340 | 0.4668% / 3.1028% | 340/340 (100.00%) | 270/340 (79.41%) | 500.00 / 7,074.00 | 0.7018% / 9.9294% | 5,847.00 / 38,865.85 |
| rich_depth2 | 298/298 | 0.4668% / 2.7012% | 298/298 (100.00%) | 238/298 (79.87%) | 498.50 / 5,120.70 | 0.6997% / 7.1877% | 5,847.00 / 33,835.10 |

Internal-node visits, candidate touches, eligibility rejects, bound prunes, scores, returned counts and working-set measurements are in the query CSV. The median and p95 for each value are in the summary CSV. Working sets refer to the resident worker including the shared graph and both trees. The ticker samples running calls and measures their endpoints.

## Public feature schema

The index is versioned as `INDEX-GATE-01-public-tree-v1`. Array offsets are class IDs. For each class, the six uint8 cell codes index an immutable 55 × 3 binary64 RAN/FH/EDGE demand-basis table. The basis codes distinguish 27 local profiles, 27 offloaded profiles and idle. Separate uint8 masks record active cells and offloaded cells. Binary64 arrays store FLAT's exact averaged quality and capability cost. Additional arrays store mechanism bits and group count, the required capability-role mask, the minimum rich derivable depth and exact availability bitsets for each query depth.

Each node has a contiguous member range, child IDs, 18 demand minima and maxima, minimum capability cost, maximum quality, minimum group count and class ID, depth extrema and depth-1 count, and role and availability summaries. The on-disk manifest records source and per-array hashes. The standalone tree audit checks all nodes and all 17 × 2 availability/depth domains.

## Offline measurements

The existing semantic graph was built in 198.097 s and serialized in another 12.211 s. Its 7,464,460-byte compressed artifact and 358,879,232-byte precompute process peak come from the historical semantic-library audit. The following measurements describe the new index.

| Measurement | Value |
| --- | --- |
| Index build and serialization, excluding graph boot | 20.866014 s |
| Peak process working set during index build | 864,468,992 B |
| Shared feature arrays | 51,583,460 B |
| Full index artifact including both variants and manifest | 157,648,503 B |
| Compressed graph plus both variants | 165,112,963 B |
| Existing availability artifacts, separately | 12,646,343 B |
| Graph, index and existing availability artifacts | 177,759,306 B |
| Index load and integrity checks, excluding graph boot | 0.550733 s |

| Variant | Roots | Nodes | Leaves | Tree build s | Tree bytes | Graph plus shared arrays plus this tree bytes |
| --- | --- | --- | --- | --- | --- | --- |
| contract | 31 | 142517 | 71274 | 10.342719 | 55,036,723 | 114,084,643 |
| generic | 1 | 131071 | 65536 | 8.932863 | 51,019,057 | 110,066,977 |

Per-variant storage sums exclude the manifest. The raw metadata includes the separate graph/index boot timings.

```json
{
  "build": {
    "graph_and_availability_load": {
      "availability_index_count": 17,
      "availability_indices_load_s": 0.9301553999976022,
      "graph_load_s": 0.45623900000646245
    },
    "graph_bytes": 7464460,
    "graph_plus_index_bytes": 165112963,
    "index_build_s": 20.866013699996984,
    "index_bytes_total": 157648503,
    "peak_build_working_set_bytes": 864468992,
    "shared_bytes": 51583460,
    "shared_features_s": 0.8946708000003127,
    "trees": {
      "contract": {
        "build_s": 10.342718700005207,
        "leaves": 71274,
        "nodes": 142517,
        "roots": 31,
        "serialized_bytes": 55036723
      },
      "generic": {
        "build_s": 8.932862700006808,
        "leaves": 65536,
        "nodes": 131071,
        "roots": 1,
        "serialized_bytes": 51019057
      }
    },
    "version": "INDEX-GATE-01-public-tree-v1"
  },
  "load": {
    "graph_and_availability_load": {
      "availability_index_count": 17,
      "availability_indices_load_s": 0.9156609999918146,
      "graph_load_s": 0.5757193000026746
    },
    "index_load_breakdown": {
      "contract_tree_load_s": 0.23863419999543112,
      "generic_tree_load_s": 0.11513079999713227,
      "shared_features_load_s": 0.19140539999352768
    },
    "index_load_s": 0.5507327999948757,
    "process_peak_working_set_bytes": 503382016
  }
}
```

# CS-ODS

This subproject contains the graph-free contract-search implementation from the CS-ODS research branch. It enumerates an ordered prefix in a finite, capability-constrained communication-service contract language. The rank uses public inputs. The model covers three time steps and two public states and uses illustrative RAN, fronthaul, and edge capacities.

For the manuscript, development results, and independent-proof evidence, see the [evidence index](../docs/evidence-index.md). The development record preserves the original route decisions and the confirmation authorization status.

## Quick start

Run from this subproject directory with Python 3.10 or later. The demo and tests use the standard library. They need no input download.

```sh
python -B -m csods --depth 2 --top-k 5
python -B -m csods --method generic --depth 2 --top-k 5
python -B -m unittest discover -s tests -v
```

The fixture has two profiles, a delay, and an offload production. Add `--conditional` to enable a conditional production. The output includes each entry's packed semantic key, public score, and normalized contract witness. A finite prefix and an exhausted domain have separate status values. The engineering example also reports search limits when reached.

## Layout

| Path | Contents |
| --- | --- |
| `csods/depth_search.py` | CS-ODS lazy shape and assignment frontiers |
| `csods/abstract_semantics.py` | Public abstraction and typed grammar |
| `csods/generic_search.py` | Generic best-first control |
| `csods/ablations.py` | Development ablation cursor builders |
| `csods/state_machine.py` | Benchmark semantic and resource/utility verification |
| `schemas/` | Contract and capability JSON Schemas |
| `SOURCE_MAP.json` | Original component locations, source digests, and export adaptations |

The benchmark ranks candidates by public score and breaks ties by packed semantic key. Search emits a contract only once an unresolved frontier cannot change its position. The test suite compares the resulting order and scores against exhaustive small grammar domains and checks that normalized witnesses yield the reported keys. The exactness analysis applies within the documented finite grammar, score, and predicate basis. [Method notes](METHOD.md)

The bundled demo and tests provide a portable development check. The manuscript's full experiments, graph-based benchmark runners, independent certificate artifacts, and performance measurements require separate materials. The included state machine verifies the abstract benchmark and has no network deployment interface.

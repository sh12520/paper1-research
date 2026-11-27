"""Read-only instrumentation of the frozen current-method public cursor."""

from time import perf_counter

from symbolic_format import FORMAT, K_VALUES, descriptor, digest, template_descriptor
from depth_search import DepthCursor
from grammar_search import Limits, SearchLimit
from runtime import verification_public


def produce_symbolic(public, binding, sample, seconds=120.0):
    pools = {}
    uses = 0
    checkpoints = {}
    prefix = []
    emission = 0.0

    def add(kind, *fields):
        nonlocal uses
        item = (kind, *fields)
        key = digest(item)
        answer = pools.setdefault(key, item)
        if answer != item:
            raise RuntimeError("Unsafe proof identity collision")
        uses += 1
        if len(pools) > 200_000:
            raise SearchLimit("proof_node_limit")
        return key

    class Observer(DepthCursor):
        """Record fully processed skeletons after the native transition."""
        def __init__(self, *args, **kwargs):
            self.observed_compiles = []
            self.observed_seconds = 0.0
            super().__init__(*args, **kwargs)

        def _compile(self, shape):
            super()._compile(shape)
            at = perf_counter()
            self.observed_compiles.append(add("COMPILED_SHAPE", descriptor(shape)))
            self.observed_seconds += perf_counter() - at

    started = perf_counter()
    cursor = Observer(verification_public(public), 3, Limits(seconds, 2_000_000, 260_000), sample)
    emitted = []

    def capture(k, exhausted):
        nonlocal emission
        at = perf_counter()
        if cursor.inflight_lb is not None:
            raise AssertionError("Cutoff observed during an unfinished expansion")
        templates = [add("TEMPLATE", *template_descriptor(t.prefix, t.cells, t.visible, t.groups))
                     for t in cursor.templates]
        shapes = [add("OPEN_SHAPE", descriptor(shape), lb.hex()) for lb, _, shape in cursor.shapes]
        assigned = [add("OPEN_ASSIGNMENT", templates[t], values, mask, lb.hex())
                    for lb, _, t, values, mask, _ in cursor.partial]
        buffered = [add("COMPLETE_CANDIDATE", templates[t], values, key.hex(), score.hex())
                    for score, key, t, values, _ in cursor.complete]
        # Emitted template/assignment is identifiable from its canonical
        # packed key. The cursor does not retain a separate native tie ID.
        checkpoints[str(k)] = {
            "compiled": list(cursor.observed_compiles), "open_shapes": sorted(shapes),
            "open_assignments": sorted(assigned), "buffered": sorted(buffered),
            "prefix": list(emitted), "exhausted": exhausted,
        }
        emission += perf_counter() - at

    reason = None
    try:
        for k in K_VALUES:
            while len(prefix) < k and not cursor.exhausted:
                entry = cursor.next_contract()
                if entry is None:
                    break
                at = perf_counter()
                row = {"key": entry.key.hex(), "score": entry.score, "witness": entry.witness}
                prefix.append(row)
                emitted.append(add("EMITTED", row))
                emission += perf_counter() - at
            capture(k, cursor.exhausted)
    except SearchLimit as exc:
        reason = str(exc)
    elapsed = perf_counter() - started
    reachable = set()
    for cut in checkpoints.values():
        for field in ("compiled", "open_shapes", "open_assignments", "buffered", "prefix"):
            reachable.update(cut[field])
    reachable.update(pools[key][1] for key in admissible_template_references(pools, reachable))
    proof = {
        "format": FORMAT,
        "binding": binding,
        "nodes": {key:pools[key] for key in sorted(reachable)},
        "checkpoints": checkpoints,
    }
    references = sum(len(cut[field]) for cut in checkpoints.values()
                     for field in ("compiled", "open_shapes", "open_assignments", "buffered", "prefix"))
    references += sum(pools[key][0] in {"OPEN_ASSIGNMENT", "COMPLETE_CANDIDATE"} for key in reachable)
    return proof, {
        "wall_s": elapsed, "synchronous_observation_s": emission + cursor.observed_seconds,
        "proof_nodes": len(reachable), "shared_references": references - len(reachable),
        "certified_cut_materials": sorted(int(k) for k in checkpoints), "limit_reason": reason,
        "native_prefix": prefix,
    }


def admissible_template_references(pools, reachable):
    return tuple(key for key in reachable if pools[key][0] in {"OPEN_ASSIGNMENT", "COMPLETE_CANDIDATE"})

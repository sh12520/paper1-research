"""Partition enumeration and public-state scoring for scheduling policies."""


def partitions(items):
    """Enumerate each set partition exactly once in a deterministic order."""
    items = tuple(sorted(items))
    if not items:
        yield ()
        return
    first, rest = items[0], items[1:]
    for partition in partitions(rest):
        yield ((first,),) + partition
        for i in range(len(partition)):
            yield partition[:i] + ((first,) + partition[i],) + partition[i + 1:]


def choose_best(state):
    """Exhaustively select by public, current-state one-step score."""
    from negotiation_engine import evaluate_partition
    candidates = list(partitions(state.active))
    # Deterministic tie-breaking, independent of runtime process hash seed.
    return max(candidates, key=lambda p: (evaluate_partition(state, p), tuple(tuple(g) for g in p)))


def restrict(partition, active):
    active = set(active)
    return [tuple(s for s in group if s in active) for group in partition if any(s in active for s in group)]

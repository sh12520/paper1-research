from coupling import coupling_score
from .common import restrict


class StaticCluster:
    """Connected components of initially strong public coupling edges."""
    def __init__(self):
        self.initial = None

    def select(self, state):
        if self.initial is None:
            ids = sorted(state.active)
            edges = []
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    pa = state.profiles[a][state.indices[a]]
                    pb = state.profiles[b][state.indices[b]]
                    score = coupling_score(pa, pb, state.capacity, state.deadlines[a], state.deadlines[b], state.time)
                    edges.append((a, b, score))
            parent = {s: s for s in ids}
            def find(x):
                while parent[x] != x:
                    x = parent[x]
                return x
            strongest = max((e[2] for e in edges), default=0)
            for a, b, score in edges:
                if strongest > 0 and score >= 0.8 * strongest:
                    parent[find(b)] = find(a)
            groups = {}
            for s in ids:
                groups.setdefault(find(s), []).append(s)
            self.initial = tuple(tuple(group) for group in groups.values())
        return restrict(self.initial, state.active)

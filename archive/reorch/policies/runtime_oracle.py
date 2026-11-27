from .common import choose_best


class RuntimeRepartitionOracle:
    """Diagnostic current-state exhaustive policy; not a clairvoyant optimum."""
    def select(self, state):
        return list(choose_best(state)) if state.active else []

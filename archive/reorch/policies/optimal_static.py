from .common import choose_best, restrict


class OptimalStaticPartition:
    """Exhaustive partition search once, under the public one-step evaluator."""
    def __init__(self):
        self.initial = None

    def select(self, state):
        if self.initial is None:
            self.initial = choose_best(state)
        return restrict(self.initial, state.active)

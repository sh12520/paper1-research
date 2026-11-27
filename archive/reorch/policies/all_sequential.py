class AllSequential:
    """Earliest deadline first, retaining the current session until it ends."""
    def __init__(self):
        self.current = None

    def select(self, state):
        if self.current not in state.active:
            self.current = min(state.active, key=lambda s: (state.deadlines[s], s)) if state.active else None
        return [(self.current,)] if self.current is not None else []

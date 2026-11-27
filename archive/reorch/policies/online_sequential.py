class OnlineSequentialReschedule:
    """Re-evaluate the singleton choice after the current session ends."""
    def __init__(self):
        self.current = None

    def select(self, state):
        if self.current not in state.active:
            from negotiation_engine import evaluate_partition
            self.current = max(state.active, key=lambda s: (
                evaluate_partition(state, ((s,),)),
                -state.deadlines[s],
                s,
            )) if state.active else None
        return [(self.current,)] if self.current is not None else []

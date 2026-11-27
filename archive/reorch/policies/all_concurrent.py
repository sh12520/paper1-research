class AllConcurrent:
    def select(self, state):
        return [tuple(sorted(state.active))] if state.active else []

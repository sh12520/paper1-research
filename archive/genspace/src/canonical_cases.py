"""Hand-constructed verification fixtures; not random benchmark distributions.

Each case tests a single mechanism with transparent, deliberately simplified
resource and utility functions. These inputs are not empirical evidence and
must not be included in pilot or confirmation rates.
"""
from itertools import product
from dataclasses import dataclass
from .models import Profile, Static, If, Sequence, Delay, Offload
from .engine import PublicContext, PrivateAcceptance, BASE, STRUCTURAL
from .registry import default_registry


@dataclass(frozen=True)
class CanonicalCase:
    family: str
    profiles: tuple
    target: object
    context: PublicContext
    private: PrivateAcceptance


def canonical_cases():
    low, high = Profile(.4, 1., 1.), Profile(.9, 1., 1.)
    caps = frozenset(default_registry())
    registry = default_registry()
    predicates = set(caps)
    predicates.update(x for cap in registry.values() for x in cap.preconditions)
    preconditions = {name: (lambda _: True) for name in predicates}
    cases = []
    for family in ('F1', 'F2', 'F3', 'F4'):
        horizon = 3 if family == 'F2' else 2
        states = ('still', 'moving') if family == 'F1' else ('normal',)
        def capacity_at(t, state, family=family):
            if family == 'F1': return .5 if state == 'moving' else 1.
            if family == 'F2': return .1 if t == 0 else 1.
            if family == 'F3': return .5 if t == 0 else 1.
            return .5
        capacity = {(t, s): {'RAN': capacity_at(t, s), 'FH': 1., 'EDGE': 1.}
                    for t, s in product(range(horizon), states)}
        def demand(p, level, t, state):
            return {'RAN': p.quality * (.5 if level == 'edge' else 1.),
                    'FH': p.rate * .1, 'EDGE': p.quality * (.5 if level == 'edge' else 0.)}
        ctx = PublicContext(horizon, states, {'moving': lambda state: state == 'moving'},
                            ('edge',), caps, preconditions, capacity, demand,
                            lambda actions: bool(actions))
        # Missing service slots contribute zero; no private data enters generation.
        app_utility = lambda actions, denominator=horizon * len(states): sum(a[2].quality for a in actions) / denominator
        reservation = .55 if family == 'F2' else (.8 if family == 'F4' else .6)
        private = PrivateAcceptance(app_utility, lambda _: .8, reservation, .5)
        targets = {'F1': If('moving', Static(low), Static(high)),
                   'F2': Delay(1, Static(high)),
                   'F3': Sequence(1, Static(low), Static(high)),
                   'F4': Offload('edge', Static(high))}
        cases.append(CanonicalCase(family, (low, high), targets[family], ctx, private))
    return tuple(cases)

"""Independent ENGINEERING-only checks of family inputs and label semantics.

These checks do not compare negotiations, agreement rates or research outcomes.
"""
import unittest

from src.engine import Domain, enumerate_compositions
from src.instances import demand, generate_instance
from src.models import Delay, If, Offload, Sequence, Static
from src.registry import default_registry
from src.runner import mechanism_labels
from src.state_machine import semantic_key


def instance(family):
    config = {'resource_pressure': 'low', 'preference_conflict': 'medium',
              'capability_richness': 'rich', 'composition_depth': 2}
    return generate_instance(family, config, 'family-review-' + family,
                             namespace='GENSPACE-FAIL-01-ENGINEERING')


def independent_labels(signature):
    """Derive labels directly from guarded cells, not witness node types."""
    _, valid, cells = signature
    if not valid:
        return ()
    values = {(t, s): v for t, s, v in cells}
    states = sorted({s for _, s, _ in cells})
    times = sorted({t for t, _, _ in cells})
    active = [v for _, _, v in cells if v is not None]
    result = set()
    if len(active) == len(cells) and len(set(active)) == 1 and active[0][3] == 'none':
        result.add('STATIC')
    if any(len({values[t, s] for s in states}) > 1 for t in times):
        result.add('STATE_CONDITIONAL')
    if any(values[times[0], s] is None and any(values[t, s] is not None for t in times[1:]) for s in states):
        result.add('DELAYED_START')
    if any(values[t1, s] is not None and values[t2, s] is not None
           and values[t1, s] != values[t2, s] for s in states
           for t1, t2 in zip(times, times[1:])):
        result.add('TEMPORAL_PHASED')
    if any(v[3] != 'none' for v in active):
        result.add('OFFLOAD')
    if len(result - {'STATIC'}) >= 2:
        result.add('HYBRID')
    return tuple(sorted(result))


class MechanismReview(unittest.TestCase):
    def test_families_are_public_mechanism_inputs(self):
        x = {family: instance(family) for family in ('F1', 'F2', 'F3', 'F4')}
        caps = {family: {(t, s): ran for t, s, ran, _, _ in value.public.capacity}
                for family, value in x.items()}
        for t in range(3):
            self.assertLess(caps['F1'][t, 'moving'], caps['F1'][t, 'still'])
            self.assertGreaterEqual(caps['F1'][t, 'moving'], .4)
            self.assertLess(caps['F1'][t, 'moving'], .8)
            self.assertGreaterEqual(caps['F1'][t, 'still'], .8)
        for state in ('still', 'moving'):
            self.assertLess(caps['F2'][0, state], .4)
            self.assertGreaterEqual(caps['F2'][1, state], .8)
            self.assertGreaterEqual(caps['F3'][0, state], .4)
            self.assertLess(caps['F3'][0, state], .8)
            self.assertGreaterEqual(caps['F3'][1, state], .8)
        p = next(p for p in x['F4'].public.b2_profiles
                 if (p.quality, p.deadline, p.rate) == (.8, 1., 1.))
        normal = demand(x['F4'].public, p, 'none', 0, 'still')
        edge = demand(x['F4'].public, p, 'edge', 0, 'still')
        self.assertLess(edge['RAN'], normal['RAN'])
        self.assertLess(edge['FH'], normal['FH'])
        self.assertGreater(edge['EDGE'], normal['EDGE'])
        self.assertLessEqual(edge['RAN'], caps['F4'][0, 'still'])
        self.assertGreater(normal['RAN'], caps['F4'][0, 'still'])
        cap_f4 = next(row for row in x['F4'].public.capacity
                      if row[0] == 0 and row[1] == 'still')
        offload_edge_cost = x['F4'].public.registry['enable_edge_offload']['resource_cost']['EDGE']
        self.assertLessEqual(edge['FH'], cap_f4[3])
        self.assertLessEqual(edge['EDGE'] + offload_edge_cost, cap_f4[4])

        for family, structure, expected in (
            ('F1', lambda lo, hi: If('moving', lo, hi), 'STATE_CONDITIONAL'),
            ('F2', lambda lo, hi: Delay(1, hi), 'DELAYED_START'),
            ('F3', lambda lo, hi: Sequence(1, lo, hi), 'TEMPORAL_PHASED'),
            ('F4', lambda lo, hi: Offload('edge', hi), 'OFFLOAD'),
        ):
            public = x[family].public
            lo = Static(next(p for p in public.b2_profiles
                             if (p.quality, p.deadline, p.rate) == (.4, 1., 1.)))
            hi = Static(next(p for p in public.b2_profiles
                             if (p.quality, p.deadline, p.rate) == (.8, 1., 1.)))
            self.assertIn(expected, independent_labels(semantic_key(structure(lo, hi), public)))

    def test_label_classifier_matches_independent_guarded_behavior(self):
        public = instance('F1').public
        profiles = (public.b2_profiles[0], public.b2_profiles[-1])
        domain = Domain(profiles, public.conditions, public.durations,
                        public.offsets, public.intervals, public.offload_levels)
        seen = {}
        for node in enumerate_compositions(domain, 2, default_registry()):
            sig = semantic_key(node, public)
            labels = mechanism_labels(sig)
            self.assertEqual(labels, independent_labels(sig), repr(node))
            if sig in seen:
                self.assertEqual(labels, seen[sig])
            seen[sig] = labels

    def test_redundant_if_is_b2_static_not_structural_gain(self):
        public = instance('F1').public
        scalar = Static(public.b2_profiles[0])
        redundant = If('moving', scalar, scalar)
        b2 = {semantic_key(Static(p), public) for p in public.b2_profiles}
        self.assertIn(semantic_key(redundant, public), b2)
        self.assertEqual(mechanism_labels(semantic_key(redundant, public)), ('STATIC',))


if __name__ == '__main__':
    unittest.main()

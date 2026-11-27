"""Small independent checks of the full-differential helper itself."""
import unittest
from types import SimpleNamespace
from dataclasses import asdict

from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.models import Profile
from src.registry import default_registry
from src.runner import mechanism_labels
from src.state_machine import semantic_key
from tools.fast_reference_diff import independent_label_bits


class DifferentialHelperTests(unittest.TestCase):
    def test_independent_packed_labels_match_reference_guarded_cells(self):
        registry = default_registry()
        profiles = (Profile(.4, 1., 1.), Profile(.8, 1., 1.))
        public = SimpleNamespace(
            b2_profiles=profiles, conditions=('moving',), durations=(1,),
            offsets=(1,), intervals=((0, 2),), offload_levels=('edge',),
            capabilities=tuple(registry), registry={k: asdict(v) for k, v in registry.items()},
            horizon=3, states=('still', 'moving'), public_constraints={'reservation_supported': True})
        domain = Domain(profiles, public.conditions, public.durations,
                        public.offsets, public.intervals, public.offload_levels)
        encoder = CompactEncoder(public)
        mapping = {'STATIC': 1, 'STATE_CONDITIONAL': 2, 'DELAYED_START': 4,
                   'TEMPORAL_PHASED': 8, 'OFFLOAD': 16, 'HYBRID': 32}
        count = 0
        for node in enumerate_compositions(domain, 2, registry):
            sig = semantic_key(node, public)
            expected = sum(mapping[x] for x in mechanism_labels(sig))
            self.assertEqual(independent_label_bits(encoder.pack(sig)), expected, repr(node))
            count += 1
        self.assertEqual(count, 562)


if __name__ == '__main__':
    unittest.main()

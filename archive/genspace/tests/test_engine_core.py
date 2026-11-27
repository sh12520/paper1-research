import inspect
import unittest
from itertools import product

from src.engine import (BASE, STRUCTURAL, Domain, PrivateAcceptance, PublicContext,
                        enumerate_compositions, enumerate_fixed, verify)
from src.models import Profile, Static, Delay, If
from src.registry import default_registry


class EngineCore(unittest.TestCase):
    def setUp(self):
        self.p = Profile(.5, 1., 1.)
        self.caps = BASE | frozenset().union(*STRUCTURAL.values())
        self.private = PrivateAcceptance(lambda _: .8, lambda _: .8, .5, .5)
        self.context = PublicContext(
            2, ('still', 'moving'), {'moving': lambda s: s == 'moving'}, ('low',),
            self.caps, {p: lambda _: True for c in default_registry().values() for p in c.preconditions},
            {(t, s): {'RAN': 1, 'FH': 1, 'EDGE': 1}
             for t, s in product(range(2), ('still', 'moving'))},
            lambda p, offload, t, state: {'RAN': p.quality, 'FH': 0, 'EDGE': 0},
            lambda actions: bool(actions))

    def test_fixed_exhaustive(self):
        ps = tuple(Profile(*p) for p in product((.2, .8), (1., 2.), (1., 2.)))
        self.assertEqual(list(enumerate_fixed(ps)), [Static(p) for p in ps])

    def test_depth_one_exact_trees(self):
        domain = Domain((self.p,), ('moving',), (1,), (1,), ((0, 1),), ('low',))
        candidates = list(enumerate_compositions(domain, 1, self.caps))
        self.assertEqual(len(candidates), 6)
        self.assertEqual(len(set(candidates)), 6)
        self.assertIn(If('moving', Static(self.p), Static(self.p)), candidates)
        self.assertIn(Delay(1, Static(self.p)), candidates)

    def test_negative_control_is_scalar_only(self):
        ps = (self.p, Profile(.9, 2., 1.))
        domain = Domain(ps, ('moving',), (1,), (1,), ((0, 1),), ('low',))
        self.assertEqual(list(enumerate_compositions(domain, 3, BASE)), list(enumerate_fixed(ps)))

    def test_generator_has_no_private_argument(self):
        self.assertEqual(tuple(inspect.signature(enumerate_compositions).parameters),
                         ('domain', 'max_depth', 'available_capabilities'))

    def test_types_missing_capabilities_and_capacity(self):
        self.assertEqual(verify(Delay('1', Static(self.p)), self.context, self.private, 2).failed_layer, 'V1')
        no_structure = PublicContext(**{**self.context.__dict__, 'capabilities': BASE})
        self.assertEqual(verify(Delay(1, Static(self.p)), no_structure, self.private, 2).failed_layer, 'V2')
        overloaded = PublicContext(**{**self.context.__dict__, 'demand':
            lambda p, o, t, s: {'RAN': 2, 'FH': 0, 'EDGE': 0}})
        self.assertEqual(verify(Static(self.p), overloaded, self.private, 2).failed_layer, 'V4')
        self.assertTrue(verify(Static(self.p), self.context, self.private, 2).verified)


if __name__ == '__main__':
    unittest.main()

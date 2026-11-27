import unittest
from dataclasses import asdict
from itertools import product
from src.models import Profile, Static
from src.registry import default_registry
from src.engine import Domain, enumerate_compositions
from src.enumeration import independent_reference, exact_syntax_count, syntax_key

class EnumerationTests(unittest.TestCase):
    def test_reference_depth_two_all_constructors(self):
        d = Domain((Profile(.4,1,1), Profile(.8,1,1)), ('moving',), (1,), (1,), ((0,2),), ('edge',))
        caps = frozenset(default_registry())
        for depth in range(3):
            with self.subTest(depth=depth):
                actual = list(enumerate_compositions(d,depth,caps))
                self.assertEqual(set(actual), independent_reference(d,depth,caps))
                self.assertEqual(len(actual), exact_syntax_count(d,depth,caps))
                self.assertEqual(len({syntax_key(x) for x in actual}), len(actual))
    def test_reference_depth_two_semantic_sets_all_constructors(self):
        from types import SimpleNamespace
        from src.state_machine import semantic_key
        d = Domain((Profile(.4,1,1), Profile(.8,1,1)), ('moving',), (1,), (1,), ((0,2),), ('edge',))
        caps = tuple(default_registry())
        public = SimpleNamespace(horizon=3, states=('still','moving'), capabilities=caps, registry={k:asdict(v) for k,v in default_registry().items()}, b2_profiles=d.profiles, public_constraints={'reservation_supported': True})
        def keys(nodes):
            result = set()
            for node in nodes:
                try:
                    result.add(semantic_key(node, public))
                except ValueError:
                    pass
            return result
        self.assertEqual(keys(enumerate_compositions(d, 2, caps)),
                         keys(independent_reference(d, 2, caps)))

    def test_dedup_key_is_not_a_prevalidation_pass(self):
        from types import SimpleNamespace
        from src.models import If
        from src.state_machine import safe_public_dedup_key, verify_instance
        p = Profile(.4,1.,1.)
        node = If('moving', Static(p), Static(p))
        caps = tuple(default_registry())
        public = SimpleNamespace(horizon=3, states=('still','moving'), capabilities=caps, registry={k:asdict(v) for k,v in default_registry().items()}, b2_profiles=(p,), public_constraints={'reservation_supported': False})
        self.assertIsNotNone(safe_public_dedup_key(node, public))
        self.assertEqual(verify_instance(node, SimpleNamespace(public=public, private=None), 2).failed_layer, 'V2')

    def test_profile_cartesian_nested_sets(self):
        low = (.8,)
        relaxed = (.4,.8)
        expanded = (.4,.6,.8)
        def profiles(q): return {Static(Profile(*x)) for x in product(q,(1.,),(1.,))}
        self.assertLessEqual(profiles(low), profiles(relaxed))
        self.assertLessEqual(profiles(relaxed), profiles(expanded))
        d = Domain(tuple(x.profile for x in profiles(expanded)))
        self.assertLessEqual(profiles(expanded), set(enumerate_compositions(d, 2, default_registry())))
    def test_semantically_equivalent_capability_id_substitution(self):
        from types import SimpleNamespace
        from dataclasses import replace
        from src.enumeration import candidates
        reg = default_registry()
        profiles = (Profile(.4,1.,1.),)
        kw = dict(m0_profiles=profiles, mr_profiles=profiles, b2_profiles=profiles,
                  conditions=('moving',), durations=(), offsets=(), intervals=(), offload_levels=())
        original = SimpleNamespace(**kw, capabilities=tuple(reg), registry={k:asdict(v) for k,v in reg.items()})
        replacement = dict(reg)
        replacement['other_condition_provider'] = replace(reg['apply_conditional_policy'], id='other_condition_provider', provider='other')
        changed = SimpleNamespace(**kw, capabilities=tuple(x for x in replacement if x != 'apply_conditional_policy'), registry={k:asdict(v) for k,v in replacement.items()})
        self.assertEqual({syntax_key(x) for x in candidates('O1', original, 1, reg)},
                         {syntax_key(x) for x in candidates('O1', changed, 1, replacement)})

    def test_identity_key_preserves_cost_relevant_structure(self):
        from src.models import Delay
        s = Static(Profile(.4,1.,1.))
        self.assertNotEqual(syntax_key(s), syntax_key(Delay(1,s)))

if __name__ == '__main__': unittest.main()

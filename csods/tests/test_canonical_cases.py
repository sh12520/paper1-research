import unittest
from dataclasses import replace
from itertools import product
from csods.canonical_cases import canonical_cases
from csods.engine import (BASE, STRUCTURAL, Domain, enumerate_compositions,
                        enumerate_fixed, verify)
from csods.models import If, Sequence, Delay, ValidFor, Offload, Static


class CanonicalCases(unittest.TestCase):
    def test_four_structural_mechanisms_resolve_fixed_deadlock(self):
        cases = canonical_cases()
        self.assertEqual([c.family for c in cases], ['F1', 'F2', 'F3', 'F4'])
        for case in cases:
            with self.subTest(family=case.family):
                self.assertTrue(all(not verify(x, case.context, case.private, 3).verified
                                    for x in enumerate_fixed(case.profiles)))
                result = verify(case.target, case.context, case.private, 3)
                self.assertTrue(result.verified, result)
                for t, state, profile, level in result.actions:
                    loads = case.context.demand(profile, level, t, state)
                    for k, cap in case.context.capacity[t, state].items():
                        self.assertLessEqual(loads[k], cap)

    def test_missing_capability_rejects_each_structure(self):
        for c in canonical_cases():
            for cap in STRUCTURAL[type(c.target)]:
                context = replace(c.context, capabilities=c.context.capabilities - {cap})
                self.assertEqual(verify(c.target, context, c.private, 3).failed_layer, 'V2')

    def test_order_of_capability_ids_does_not_change_existence(self):
        c = canonical_cases()[0]
        domain = Domain(c.profiles, ('moving',))
        ids = list(c.context.capabilities)
        def exists(order):
            return any(verify(x, c.context, c.private, 1).verified
                       for x in enumerate_compositions(domain, 1, order))
        self.assertEqual(exists(ids), exists(list(reversed(ids))))

    def test_exact_depth_two_against_independent_closed_form(self):
        c = canonical_cases()[0]
        # Single unary and binary constructor domains, independently expand layers.
        domain = Domain((c.profiles[0],), ('moving',), (), (1,), (), ())
        base = {Static(c.profiles[0])}
        def expand(children):
            return base | {Delay(1, x) for x in children} | {
                If('moving', a, b) for a, b in product(children, repeat=2)}
        expected = expand(expand(base))
        caps = BASE | STRUCTURAL[If] | STRUCTURAL[Delay]
        self.assertEqual(set(enumerate_compositions(domain, 2, caps)), expected)


if __name__ == '__main__': unittest.main()

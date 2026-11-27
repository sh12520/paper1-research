import unittest
from dataclasses import replace, asdict
from src.instances import generate_instance, PrivatePreferences
from src.models import Static, If, Sequence, Delay, ValidFor, Offload
from src.registry import default_registry
from src.state_machine import verify_instance


class StateMachineTests(unittest.TestCase):
    def instance(self):
        config = dict(resource_pressure='low', preference_conflict='medium', capability_richness='rich', composition_depth=2)
        inst = generate_instance('F1', config, 91, namespace='GENSPACE-FAIL-01-ENGINEERING')
        cap = tuple((t, s, 10., 10., 10.) for t in range(inst.public.horizon) for s in inst.public.states)
        public = replace(inst.public, capacity=cap)
        ap, net = dict(inst.private.application), dict(inst.private.network)
        ap['reservation'] = net['reservation'] = 0.
        return replace(inst, public=public, private=PrivatePreferences(ap, net))

    def test_schedule_and_resource_transitions(self):
        inst = self.instance()
        low, high = inst.public.b2_profiles[0], inst.public.b2_profiles[-1]
        node = Sequence(1, Static(low), Delay(1, Offload('edge', Static(high))))
        result = verify_instance(node, inst, 3)
        self.assertTrue(result.verified, result)
        self.assertEqual({(t, s) for t,s,_,_ in result.actions}, {(0,'still'),(0,'moving'),(2,'still'),(2,'moving')})
        for step in result.compiled_actions:
            self.assertEqual(len(step.before), 3)
            self.assertEqual(len(step.after), 3)
            self.assertTrue(all(b >= a for b,a in zip(step.before,step.after)))
            if not step.operation.startswith('reserve_'):
                self.assertEqual(step.before, step.after)
        self.assertEqual(sum(x.operation == 'idle' for x in result.compiled_actions), 2)

    def test_if_and_validity_use_time_and_state_guards(self):
        inst = self.instance()
        low, high = inst.public.b2_profiles[0], inst.public.b2_profiles[-1]
        node = ValidFor((0,2), If('moving', Static(low), Static(high)))
        result = verify_instance(node, inst, 3)
        self.assertTrue(result.verified, result)
        by_guard = {(t,s):p for t,s,p,l in result.actions}
        self.assertEqual(by_guard[(1,'still')], high)
        self.assertEqual(by_guard[(1,'moving')], low)
        self.assertNotIn((2,'still'), by_guard)

    def test_missing_and_equivalent_provider(self):
        inst = self.instance()
        registry = default_registry()
        high = inst.public.b2_profiles[-1]
        node = Offload('edge', Static(high))
        original = verify_instance(node, inst, 2, registry)
        self.assertTrue(original.verified, original)
        old = registry['enable_edge_offload']
        registry['different_provider_id'] = replace(old, id='different_provider_id', provider='substitute')
        ids = tuple(x for x in inst.public.capabilities if x != old.id) + ('different_provider_id',)
        changed = replace(inst, public=replace(inst.public, capabilities=ids, registry={k: asdict(v) for k,v in registry.items()}))
        self.assertNotEqual(inst.public_hash, changed.public_hash)
        with self.assertRaises(ValueError):
            verify_instance(node, inst, 2, registry)
        other = verify_instance(node, changed, 2, registry)
        self.assertEqual(original.verified, other.verified)
        self.assertEqual(original.actions, other.actions)
        broken = replace(changed, public=replace(changed.public, capabilities=tuple(x for x in ids if x != 'different_provider_id')))
        self.assertEqual(verify_instance(node, broken, 2, registry).failed_layer, 'V2')

    def test_substitution_preserves_whole_o1_agreement_existence(self):
        from src.enumeration import candidates, syntax_key
        from src.state_machine import semantic_key
        inst = self.instance()
        profiles = (inst.public.b2_profiles[0], inst.public.b2_profiles[-1])
        public = replace(inst.public, m0_profiles=profiles[:1], mr_profiles=profiles,
                         b2_profiles=profiles)
        inst = replace(inst, public=public)
        registry = default_registry()
        orig = registry['enable_edge_offload']
        registry['other_offload_provider'] = replace(orig, id='other_offload_provider', provider='other')
        ids = tuple(x for x in public.capabilities if x != orig.id) + ('other_offload_provider',)
        changed = replace(inst, public=replace(public, capabilities=ids,
                          registry={k:asdict(v) for k,v in registry.items()}))
        self.assertIs(inst.private, changed.private)
        self.assertNotEqual(inst.public_hash, changed.public_hash)

        def verified_sets(instance):
            generated = list(candidates('O1', instance.public, 2))
            passed = [n for n in generated if verify_instance(n, instance, 2).verified]
            return ({syntax_key(n) for n in generated},
                    {syntax_key(n) for n in passed},
                    {semantic_key(n, instance.public) for n in passed}, passed)
        gen_a, passed_a, sem_a, accepted = verified_sets(inst)
        gen_b, passed_b, sem_b, _ = verified_sets(changed)
        self.assertEqual(gen_a, gen_b)
        self.assertEqual(passed_a, passed_b)
        self.assertEqual(sem_a, sem_b)
        self.assertEqual(bool(passed_a), bool(passed_b))
        self.assertTrue(any(isinstance(n, Offload) for n in accepted))

    def test_redundant_conditional_normalized_before_capabilities(self):
        from src.state_machine import semantic_key
        inst = self.instance()
        node = Static(inst.public.b2_profiles[0])
        redundant = If('moving', node, node)
        without_if = replace(inst, public=replace(inst.public, capabilities=tuple(
            c for c in inst.public.capabilities if c not in ('observe_motion_state','apply_conditional_policy'))))
        self.assertEqual(semantic_key(redundant, without_if.public), semantic_key(node, without_if.public))
        a, b = verify_instance(node, without_if, 2), verify_instance(redundant, without_if, 2)
        self.assertTrue(a.verified)
        self.assertEqual(a, b)

    def test_context_equivalent_distinct_branches_normalize(self):
        from src.state_machine import semantic_key
        inst = self.instance()
        p = Static(inst.public.b2_profiles[0])
        a, b = Delay(1, Offload('edge', p)), Offload('edge', Delay(1, p))
        self.assertNotEqual(a, b)
        self.assertEqual(semantic_key(a, inst.public), semantic_key(b, inst.public))
        ca, cb = If('moving', a, a), If('moving', a, b)
        self.assertEqual(semantic_key(ca, inst.public), semantic_key(cb, inst.public))
        self.assertEqual(verify_instance(ca, inst, 3).verified, verify_instance(cb, inst, 3).verified)

    def test_v3_invalid_child_cannot_be_repaired_by_parent(self):
        from src.state_machine import semantic_key
        from src.models import Profile
        inst = self.instance()
        valid = Static(inst.public.b2_profiles[0])
        invalid = (Static(Profile(1.5,1.,1.)), Delay(99,valid),
                   If('unknown',valid,valid), ValidFor((2,1),valid), Offload('bad',valid))
        for bad in invalid:
            self.assertFalse(semantic_key(bad, inst.public)[1])
            contexts = (Delay(1,bad), Sequence(1,bad,valid), Sequence(1,valid,bad),
                        If('moving',bad,valid), If('moving',valid,bad),
                        If('moving',bad,bad), Offload('edge',bad), ValidFor((0,2),bad))
            for node in contexts:
                self.assertFalse(semantic_key(node, inst.public)[1], repr(node))

    def test_current_registry_v2_failure_survives_constructor_wrapping(self):
        from src.models import Profile
        inst = self.instance()
        good = Static(inst.public.b2_profiles[0])
        no_offload = replace(inst, public=replace(inst.public, capabilities=tuple(
            c for c in inst.public.capabilities if c != 'enable_edge_offload')))
        bad_profile = Static(Profile(.123, 1., 1.))
        no_reservation = replace(inst, public=replace(inst.public,
            public_constraints={**inst.public.public_constraints, 'reservation_supported': False}))
        wrong_scope_registry = {k: dict(v) for k, v in inst.public.registry.items()}
        wrong_scope_registry['set_quality']['supported_scope'] = ['delayed']
        wrong_scope = replace(inst, public=replace(inst.public, registry=wrong_scope_registry))
        unknown_registry = {k: dict(v) for k, v in inst.public.registry.items()}
        unknown_registry['set_quality']['preconditions'] = ['unknown_predicate']
        unknown = replace(inst, public=replace(inst.public, registry=unknown_registry))
        cases = ((no_offload, Offload('edge', good)), (inst, bad_profile),
                 (no_reservation, good), (wrong_scope, good), (unknown, good))
        for instance, child in cases:
            self.assertEqual(verify_instance(child, instance, 3).failed_layer, 'V2')
            contexts = (Delay(1,child), ValidFor((0,2),child), Offload('edge',child),
                        Sequence(1,child,good), Sequence(1,good,child),
                        If('moving',child,good), If('moving',good,child),
                        If('moving',child,child))
            for parent in contexts:
                self.assertEqual(verify_instance(parent, instance, 3).failed_layer, 'V2', repr(parent))

    def test_alternate_interpreter_can_repair_unsupported_static_scope(self):
        from unittest.mock import patch
        inst = self.instance()
        registry = default_registry()
        cap = registry['set_quality']
        registry['set_quality'] = replace(cap, supported_scope=tuple(
            scope for scope in cap.supported_scope if scope != 'static'))
        changed = replace(inst, public=replace(inst.public,
            registry={k: asdict(v) for k, v in registry.items()}))
        leaf = Static(inst.public.b2_profiles[0])
        # This explicitly changes the interpreter's supported vocabulary. The
        # production registry permits both scopes; this is a counterexample to
        # a claim quantified over arbitrary alternate capability semantics.
        with patch('src.state_machine.default_registry', return_value=registry):
            self.assertEqual(verify_instance(leaf, changed, 2).failed_layer, 'V2')
            self.assertNotEqual(verify_instance(Delay(1, leaf), changed, 2).failed_layer, 'V2')

    def test_runtime_cost_charged_only_on_selected_branch(self):
        from src.instances import demand
        inst = self.instance()
        p = inst.public.b2_profiles[0]
        q = inst.public.b2_profiles[-1]
        node = If('moving', Offload('edge', Static(p)), Static(q))
        result = verify_instance(node, inst, 2)
        self.assertTrue(result.verified, result)
        edge_steps = {(a.time,a.state): a.arguments[0] for a in result.compiled_actions if a.operation == 'reserve_edge'}
        self.assertAlmostEqual(edge_steps[(0,'moving')], demand(inst.public,p,'edge',0,'moving')['EDGE'] + .1)
        self.assertNotIn((0,'still'), edge_steps)

    def test_equal_semantic_signatures_imply_verification_outcomes(self):
        from itertools import product
        from src.enumeration import candidates
        from src.state_machine import semantic_key
        inst = self.instance()
        profiles = (inst.public.b2_profiles[0],)
        public = replace(inst.public,m0_profiles=profiles,mr_profiles=profiles,b2_profiles=profiles)
        inst = replace(inst,public=public)
        nodes = list(candidates('O1', public, 2))
        nodes += [If('invalid', Static(profiles[0]), Static(profiles[0])),
                  Delay(9, Static(profiles[0]))]
        groups = {}
        for node in nodes:
            groups.setdefault(semantic_key(node,public), []).append(node)
        paired = [group for group in groups.values() if len(group) > 1]
        self.assertTrue(paired)
        for group in paired:
            outcomes = [verify_instance(x,inst,2) for x in group]
            base = outcomes[0]
            for outcome in outcomes[1:]:
                self.assertEqual((base.verified,base.failed_layer,base.actions,base.application_utility,base.network_utility),
                                 (outcome.verified,outcome.failed_layer,outcome.actions,outcome.application_utility,outcome.network_utility))

    def test_registry_costs_charged_in_capacity_and_network_utility(self):
        from src.instances import demand, utilities
        inst = self.instance()
        node = Offload('edge', Static(inst.public.b2_profiles[0]))
        result = verify_instance(node, inst, 2)
        self.assertTrue(result.verified, result)
        edge = next(x for x in result.compiled_actions if x.operation == 'reserve_edge')
        profile = node.clause.profile
        self.assertAlmostEqual(edge.arguments[0], demand(inst.public, profile, 'edge', edge.time, edge.state)['EDGE'] + 0.1)
        _, uncharged = utilities(inst.public, inst.private, result.actions)
        self.assertLess(result.network_utility, uncharged)
        tight = tuple((t,s,ran,fh,.05) for t,s,ran,fh,_ in inst.public.capacity)
        small = replace(inst, public=replace(inst.public, capacity=tight))
        self.assertEqual(verify_instance(node, small, 2).failed_layer, 'V4')

    def test_nonpermissive_public_predicates(self):
        inst = self.instance()
        p = inst.public.b2_profiles[0]
        invalid = Delay(0, Static(p))
        self.assertEqual(verify_instance(invalid, inst, 3).failed_layer, 'V2')
        constrained = replace(inst.public, public_constraints={**inst.public.public_constraints, 'reservation_supported':False})
        self.assertEqual(verify_instance(Static(p), replace(inst, public=constrained), 3).failed_layer, 'V2')


if __name__ == '__main__': unittest.main()

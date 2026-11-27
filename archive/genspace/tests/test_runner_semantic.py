import unittest
from dataclasses import replace
from unittest.mock import patch
from src.instances import generate_instance, PrivatePreferences
from src.models import Static, If, Sequence, Delay, Offload
from src.semantic_dp import Entry
from src.state_machine import semantic_key
from src.runner import run_paired, mechanism_labels, precompute_library

C = {'resource_pressure':'low', 'preference_conflict':'medium', 'capability_richness':'rich', 'composition_depth':1}

class RunnerSemanticTest(unittest.TestCase):
    def fixture(self):
        instance = generate_instance('F1', C, 'runner-unit', namespace='GENSPACE-FAIL-01-ENGINEERING')
        p = instance.public
        profile = p.m0_profiles[0]
        public = replace(p, m0_profiles=(profile,), mr_profiles=(profile,), b2_profiles=(profile,),
            capacity=tuple((t,s,10.,10.,10.) for t in range(p.horizon) for s in p.states))
        private = PrivatePreferences({**instance.private.application, 'reservation':0.},
                                     {**instance.private.network, 'reservation':0.})
        return replace(instance, public=public, private=private)

    def test_uses_dp_and_novelty_is_b2_semantic_nonmembership(self):
        x = self.fixture(); profile = x.public.b2_profiles[0]
        static = Static(profile)
        redundant = If('moving',static,static)
        delay = Delay(1,static)
        self.assertEqual(semantic_key(static,x.public),semantic_key(redundant,x.public))
        entries = {semantic_key(redundant,x.public): Entry(redundant,static),
                   semantic_key(delay,x.public): Entry(delay,delay)}
        with patch('src.runner.library',return_value=entries) as dp:
            rows = run_paired(x.serialize())
        self.assertTrue(dp.called)
        oracle = rows[-1]
        self.assertTrue(oracle['any_verified_structural'])
        self.assertFalse(rows[2]['any_verified_structural'])
        self.assertEqual(oracle['candidate_count_unit'],'semantic_classes')
        self.assertEqual(oracle['oracle_status'],'EXPERIMENTAL_NOT_VALIDATED')

    def test_behavioral_mechanism_labels(self):
        x=self.fixture(); static=Static(x.public.b2_profiles[0])
        self.assertEqual(mechanism_labels(semantic_key(If('moving',static,static),x.public)), ('STATIC',))
        self.assertIn('DELAYED_START', mechanism_labels(semantic_key(Delay(1,static),x.public)))
        self.assertIn('OFFLOAD', mechanism_labels(semantic_key(Offload('edge',static),x.public)))

    def test_labels_include_state_dependent_role_costs_and_idle_is_not_phased(self):
        x = self.fixture()
        static = Static(x.public.b2_profiles[0])
        # Both branches serve the same profile, but only moving pays for the
        # phased-policy role. This is a conditional execution difference.
        conditional = If('moving', Sequence(1, static, static), static)
        labels = mechanism_labels(semantic_key(conditional, x.public))
        self.assertEqual(labels, ('STATE_CONDITIONAL',))
        delayed_offload = Delay(1, Offload('edge', static))
        labels = mechanism_labels(semantic_key(delayed_offload, x.public))
        self.assertEqual(labels, ('DELAYED_START', 'HYBRID', 'OFFLOAD'))
        phased = Sequence(1, static, Offload('edge', static))
        labels = mechanism_labels(semantic_key(phased, x.public))
        self.assertEqual(labels, ('HYBRID', 'OFFLOAD', 'TEMPORAL_PHASED'))

    def test_precomputed_library_reused_only_when_basis_matches(self):
        x = self.fixture()
        prepared = precompute_library(x.public, 1)
        changed_capacity = replace(x, public=replace(x.public, capacity=tuple((t,s,8.,8.,8.) for t in range(x.public.horizon) for s in x.public.states)))
        with patch('src.runner.library', side_effect=AssertionError('unexpected recompute')):
            rows = run_paired(changed_capacity.serialize(), prepared_library=prepared)
        self.assertEqual(rows[-1]['method'], 'O1')
        different = replace(x, public=replace(x.public, offsets=(2,)))
        with self.assertRaises(ValueError):
            run_paired(different.serialize(), prepared_library=prepared)

    def test_capability_count_uses_public_semantic_normalization(self):
        from src.engine import required_capabilities
        from src.state_machine import normalize
        x = self.fixture()
        # Depth three is a direct regression fixture, not a study configuration.
        x = replace(x, public=replace(x.public,
            configuration={**x.public.configuration, 'composition_depth': 3}))
        static = Static(x.public.b2_profiles[0])
        a = Delay(1, Offload('edge', static))
        b = Offload('edge', Delay(1, static))
        witness = If('moving', a, b)
        sig = semantic_key(witness, x.public)
        self.assertEqual(semantic_key(a, x.public), semantic_key(b, x.public))
        self.assertGreater(len(required_capabilities(normalize(witness))),
                           len(required_capabilities(normalize(witness, x.public))))
        entries = {sig: Entry(witness, normalize(witness, x.public))}
        with patch('src.runner.library', return_value=entries):
            rows = run_paired(x.serialize())
        oracle = rows[-1]
        self.assertTrue(oracle['agreement'])
        self.assertEqual(oracle['capability_count'],
                         len(required_capabilities(normalize(witness, x.public))))

    def test_research_namespaces_blocked_without_generating_seeds(self):
        x=self.fixture()
        for namespace in ('GENSPACE-FAIL-01-SMOKE','GENSPACE-FAIL-01-PILOT','GENSPACE-FAIL-01-CONFIRM'):
            with self.subTest(namespace=namespace), self.assertRaises(RuntimeError):
                run_paired(replace(x,namespace=namespace).serialize())

if __name__ == '__main__': unittest.main()

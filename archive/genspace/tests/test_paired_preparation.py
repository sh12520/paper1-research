import unittest
from dataclasses import replace
from src.instances import generate_instance as _generate_instance, PrivatePreferences
from src.enumeration import METHODS, candidates, syntax_key
from src.engine import BASE
from src.registry import default_registry
from src.runner import run_paired
from src.state_machine import verify_instance, semantic_key

CONF = {'resource_pressure': 'medium', 'preference_conflict': 'medium',
        'capability_richness': 'rich', 'composition_depth': 2}

def generate_instance(family, configuration, seed):
    return _generate_instance(family, configuration, seed, namespace='GENSPACE-FAIL-01-ENGINEERING')

class PairedAndInformationTests(unittest.TestCase):
    def fixture(self):
        x = generate_instance('F1', CONF, 'unit-pairing')
        # A small, explicit test domain, not a smoke or pilot configuration.
        p = x.public
        return replace(x, public=replace(p, m0_profiles=p.m0_profiles[:1],
            mr_profiles=p.m0_profiles[:1], b2_profiles=p.m0_profiles[:1],
            capabilities=tuple(sorted(BASE))))

    def test_paired_methods_read_same_serialized_instance(self):
        x = self.fixture()
        rows = run_paired(x.serialize())
        self.assertEqual([r['method'] for r in rows], list(METHODS))
        self.assertEqual({r['instance_hash'] for r in rows}, {x.instance_hash})
        self.assertEqual({r['public_hash'] for r in rows}, {x.public_hash})
        self.assertEqual({r['private_hash'] for r in rows}, {x.private_hash})

    def test_noninterference_all_private_fields(self):
        x = self.fixture()
        x = replace(x, public=replace(x.public, capabilities=tuple(sorted(default_registry()))))
        a = {k: 1-v if k == 'reservation' else v*0.5 for k,v in x.private.application.items()}
        n = {k: 1-v if k == 'reservation' else v*0.5 for k,v in x.private.network.items()}
        y = replace(x, private=PrivatePreferences(a, n))
        self.assertNotEqual(x.private_hash, y.private_hash)
        self.assertEqual(x.public_hash, y.public_hash)
        for method in METHODS:
            left = {syntax_key(t) for t in candidates(method, x.public, 2)}
            right = {syntax_key(t) for t in candidates(method, y.public, 2)}
            self.assertEqual(left, right)

    def test_negative_control_verified_static_set(self):
        x = generate_instance('F1', CONF, 'negative-control-unit')
        x = replace(x, public=replace(x.public, capabilities=tuple(sorted(BASE))))
        x = replace(x, public=replace(x.public, capacity=tuple((t,s,10.,10.,10.) for t in range(x.public.horizon) for s in x.public.states)), private=PrivatePreferences({**x.private.application, 'reservation': 0.0}, {**x.private.network, 'reservation': 0.0}))
        def verified(method):
            return {semantic_key(t, x.public) for t in candidates(method, x.public, 2)
                    if verify_instance(t, x, 2).verified}
        self.assertTrue(verified('B2'))
        self.assertEqual(verified('B2'), verified('O1'))

if __name__ == '__main__':
    unittest.main()

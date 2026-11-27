import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.execution_snapshot import build_snapshot, verify_snapshot, verify_public_instance, verify_private_preferences
from src.instances import generate_instance


class ExecutionSnapshotTests(unittest.TestCase):
    def test_snapshot_rejects_tampered_values(self):
        saved = build_snapshot()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.json'
            path.write_text(json.dumps(saved), encoding='utf-8')
            self.assertEqual(verify_snapshot(path), saved)
            saved['semantic_library_sha256'] = '0' * 64
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_snapshot(path)
            saved = build_snapshot()
            saved['availability_manifest_sha256'] = '0' * 64
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_snapshot(path)

    def test_public_basis_fails_closed(self):
        cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
               'capability_richness': 'rich', 'composition_depth': 2}
        instance = generate_instance('F1', cfg, 'snapshot-unit',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        snapshot = build_snapshot()
        verify_public_instance(instance.public, snapshot)
        with self.assertRaises(ValueError):
            verify_public_instance(replace(instance.public, offsets=(2,)), snapshot)
        with self.assertRaises(ValueError):
            verify_public_instance(replace(instance.public, capacity=instance.public.capacity[:-1]), snapshot)
        registry = dict(instance.public.registry)
        registry['set_rate'] = {**registry['set_rate'], 'execution_cost': 0.123}
        with self.assertRaises(ValueError):
            verify_public_instance(replace(instance.public, registry=registry), snapshot)


    def test_invalid_configuration_fails_closed(self):
        cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
               'capability_richness': 'rich', 'composition_depth': 2}
        instance = generate_instance('F1', cfg, 'grid-invalid-unit',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        snapshot = build_snapshot()
        for depth in (0, 3, True):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                verify_public_instance(replace(instance.public, configuration={**cfg,'composition_depth':depth}),snapshot)
        with self.assertRaises(ValueError):
            verify_public_instance(replace(instance.public, family='unknown'),snapshot)
        with self.assertRaises(ValueError):
            verify_public_instance(replace(instance.public, configuration={**cfg,'resource_pressure':'unknown'}),snapshot)

    def test_invalid_private_weights_and_reservations_fail_closed(self):
        cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
               'capability_richness': 'rich', 'composition_depth': 2}
        instance = generate_instance('F1', cfg, 'private-invalid-unit',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        verify_private_preferences(instance.private)
        for value in (-1., float('nan'), float('inf'), 1.0001):
            prefs = replace(instance.private, application={**instance.private.application, 'reservation':value})
            with self.subTest(reservation=value), self.assertRaises(ValueError):
                verify_private_preferences(prefs)
        for value in (0., -1., float('nan'), float('inf')):
            prefs = replace(instance.private, network={**instance.private.network, 'ran_cost':value})
            with self.subTest(weight=value), self.assertRaises(ValueError):
                verify_private_preferences(prefs)



if __name__ == '__main__':
    unittest.main()

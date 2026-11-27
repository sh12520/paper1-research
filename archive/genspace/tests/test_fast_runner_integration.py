"""Engineering-only integration checks; no research namespace is sampled."""
import importlib.util
from dataclasses import replace
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.instances import generate_instance, PrivatePreferences


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy runtime not available')
class FastRunnerIntegrationTests(unittest.TestCase):
    def test_availability_manifest_and_unsupported_patterns_fail_closed(self):
        from src.availability_index import AvailabilityBundle
        from src.execution_snapshot import build_snapshot
        snapshot = build_snapshot()
        with patch('src.availability_index.sha256_file', return_value='0' * 64):
            with self.assertRaises(ValueError):
                AvailabilityBundle.load(snapshot)
        reference = SimpleNamespace(roles=('observe_motion_state', 'apply_conditional_policy',
                                          'set_validity_interval'),
                                    available=(True, True, False))
        with self.assertRaises(ValueError):
            AvailabilityBundle.pattern(SimpleNamespace(reference=reference))

    def test_depth_one_fast_dispatch_matches_reference(self):
        from src.execution_snapshot import build_snapshot
        from src.fast_exact import FastLibrary
        from src.runner import run_paired
        cfg = {'resource_pressure': 'medium', 'preference_conflict': 'medium',
               'capability_richness': 'rich', 'composition_depth': 1}
        instance = generate_instance('F1', cfg, 'fast-runner-unit',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        instance = replace(instance, private=PrivatePreferences(
            {**instance.private.application, 'reservation': 0.0},
            {**instance.private.network, 'reservation': 0.0}))
        with patch('src.execution_snapshot.verify_snapshot', side_effect=build_snapshot):
            library = FastLibrary.from_graph()
        expected = run_paired(instance.serialize())
        with patch.object(library, 'witness', wraps=library.witness) as render:
            actual, timings = run_paired(instance.serialize(), fast_library=library,
                                         include_timings=True)
        self.assertEqual([r['instance_hash'] for r in actual], [instance.instance_hash] * 4)
        for reference, fast in zip(expected, actual):
            self.assertEqual(reference['method'], fast['method'])
            self.assertEqual(reference['agreement'], fast['agreement'])
            self.assertEqual(reference['representative'], fast['representative'])
            for name in ('application_utility', 'network_utility', 'nash_welfare'):
                if reference[name] is None:
                    self.assertIsNone(fast[name])
                else:
                    self.assertAlmostEqual(reference[name], fast[name], places=12)
        self.assertEqual(render.call_count, int(actual[-1]['agreement']))
        self.assertTrue(actual[-1]['agreement'])
        # A selected witness whose semantic key does not match its class must
        # fail closed; no invalid action schedule may be reported as verified.
        with patch('src.fast_runner._encode_selected', return_value=b'bad'):
            with self.assertRaises(ValueError):
                run_paired(instance.serialize(), fast_library=library)
        self.assertIn('complete_run_paired_s', timings)

    def test_sparse_conditioned_witness_counts_and_layer_artifact(self):
        import numpy as np
        from src.execution_snapshot import build_snapshot
        from src.fast_exact import FastLibrary
        from src.runner import run_paired
        from src.stage_report import CODES
        cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
               'capability_richness': 'sparse', 'composition_depth': 1}
        instance = generate_instance('F1', cfg, 'availability-witness-27',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        public = replace(instance.public, capabilities=tuple(
            role for role in instance.public.capabilities
            if role not in ('apply_conditional_policy', 'observe_motion_state')))
        instance = replace(instance, public=public)
        with patch('src.execution_snapshot.verify_snapshot', side_effect=build_snapshot):
            library = FastLibrary.from_graph()
        reference = run_paired(instance.serialize())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'layers.npz'
            with patch.object(library, 'witness', wraps=library.witness) as render:
                actual, _ = run_paired(instance.serialize(), fast_library=library,
                                       include_timings=True, candidate_layers_path=path)
            self.assertEqual(render.call_count, int(actual[-1]['agreement']))
            for expected, got in zip(reference, actual):
                for field in ('agreement', 'candidate_count', 'verified_count',
                              'any_verified_structural', 'representative',
                              'ast_depth', 'capability_count', 'family', 'configuration'):
                    self.assertEqual(expected[field], got[field], (got['method'], field))
                for layer in ('V1', 'V2', 'V3', 'V4', 'V5'):
                    self.assertEqual(expected['validator_rejections'].get(layer, 0),
                                     got['validator_rejections'].get(layer, 0))
                if got['agreement']:
                    self.assertTrue(got['compiled_actions'])
            with np.load(path, allow_pickle=False) as saved:
                layers = saved['layers']
                metadata = json.loads(str(saved['metadata_json']))
                self.assertEqual(metadata['instance_hash'], instance.instance_hash)
                self.assertEqual(set(metadata['baseline_candidate_layers']), {'B0', 'B1', 'B2'})
                for row in actual[:3]:
                    records = metadata['baseline_candidate_layers'][row['method']]
                    self.assertEqual(len(records), row['candidate_count'])
                    self.assertEqual(len({r['candidate'] for r in records}), len(records))
                    self.assertEqual(sum(r['first_failure_layer'] == 'VERIFIED' for r in records),
                                     row['verified_count'])
                    for layer in ('V1', 'V2', 'V3', 'V4', 'V5'):
                        self.assertEqual(sum(r['first_failure_layer'] == layer for r in records),
                                         row['validator_rejections'].get(layer, 0))
                self.assertEqual(int(np.count_nonzero(layers == CODES['VERIFIED'])),
                                 actual[-1]['verified_count'])
                self.assertEqual(int(np.count_nonzero(layers == CODES['NOT_GENERATED'])),
                                 actual[-1]['not_generated_count'])
                self.assertEqual(int(np.count_nonzero(layers == CODES['V2_FAILED'])),
                                 actual[-1]['validator_rejections']['V2'])

    def test_fast_o1_binding_and_evaluation_construct_no_ast(self):
        from src.execution_snapshot import build_snapshot
        from src.fast_exact import FastEvaluator, FastLibrary
        cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
               'capability_richness': 'rich', 'composition_depth': 2}
        instance = generate_instance('F1', cfg, 'no-o1-ast-unit',
                                     namespace='GENSPACE-FAIL-01-ENGINEERING')
        # Baselines are separate; the O1 binding/evaluation path must not
        # instantiate even a dummy AST. Its selected witness is not decoded here.
        with patch('src.execution_snapshot.verify_snapshot', side_effect=build_snapshot):
            library = FastLibrary.from_graph()
        with patch('src.models.Static', side_effect=AssertionError('unexpected AST construction')):
            result = FastEvaluator(instance, library).evaluate()
        self.assertEqual(len(result.in_domain), 1_394_064)


if __name__ == '__main__':
    unittest.main()

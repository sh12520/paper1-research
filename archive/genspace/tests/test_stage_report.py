import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy runtime not available')
class CandidateLayerReportTests(unittest.TestCase):
    def fixture(self):
        import numpy as np
        # Class 1 is excluded by generation even though it resides in the rich
        # graph; classes 2–5 fail V2–V5 respectively; classes 6–7 pass.
        domain = np.array([0, 1, 1, 1, 1, 1, 1, 1], dtype=bool)
        generated = np.array([0, 0, 1, 1, 1, 1, 1, 1], dtype=bool)
        v2 = np.array([0, 0, 0, 1, 1, 1, 1, 1], dtype=bool)
        v3 = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=bool)
        physical = np.array([0, 0, 0, 0, 0, 1, 1, 1], dtype=bool)
        accepted = np.array([0, 0, 0, 0, 0, 0, 1, 1], dtype=bool)
        return SimpleNamespace(in_domain=domain, v2_pass=v2, v3_pass=v3,
                               physical_ok=physical, accepted=accepted), generated

    def test_codes_separate_absent_generation_from_validator_failure(self):
        import numpy as np
        from src.stage_report import CODES, derive_candidate_layers
        value, generated = self.fixture()
        actual = derive_candidate_layers(value, generated)
        expected = [CODES[x] for x in ('OUT_OF_DEPTH', 'NOT_GENERATED',
                    'V2_FAILED', 'V3_FAILED', 'V4_FAILED', 'V5_FAILED',
                    'VERIFIED', 'VERIFIED')]
        self.assertEqual(actual.dtype, np.uint8)
        self.assertEqual(actual.tolist(), expected)

    def test_rejects_inconsistent_stage_or_generation_masks(self):
        from src.stage_report import derive_candidate_layers
        value, generated = self.fixture()
        generated[0] = True
        with self.assertRaises(ValueError):
            derive_candidate_layers(value, generated)
        generated[0] = False
        value.accepted[4] = True
        with self.assertRaises(ValueError):
            derive_candidate_layers(value, generated)

    def test_artifact_roundtrip_and_no_overwrite(self):
        import numpy as np
        from src.stage_report import derive_candidate_layers, write_candidate_layers
        value, generated = self.fixture()
        layer = derive_candidate_layers(value, generated)
        identity = {'graph_sha256': 'a' * 64, 'snapshot_sha256': 'b' * 64,
                    'instance_hash': 'c' * 64}
        baseline = {'B0': [{'candidate': 'a', 'first_failure_layer': 'V2', 'reason': 'missing'}],
                    'B1': [{'candidate': 'b', 'first_failure_layer': 'VERIFIED', 'reason': 'verified'}],
                    'B2': [{'candidate': 'c', 'first_failure_layer': 'V5', 'reason': 'rejected'}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'class-layers.npz'
            write_candidate_layers(path, layer, baseline_layers=baseline, **identity)
            with np.load(path, allow_pickle=False) as saved:
                self.assertEqual(saved['layers'].tolist(), layer.tolist())
                meta = json.loads(str(saved['metadata_json']))
                self.assertEqual(meta['instance_id'], 'class-layers')
                self.assertEqual(meta['graph_sha256'], identity['graph_sha256'])
                self.assertEqual(meta['instance_hash'], identity['instance_hash'])
                self.assertEqual(meta['baseline_candidate_layers'], baseline)
            with self.assertRaises(FileExistsError):
                write_candidate_layers(path, layer, **identity)

    def test_invalid_baseline_layer_records_are_rejected(self):
        from src.stage_report import derive_candidate_layers, write_candidate_layers
        value, generated = self.fixture()
        layer = derive_candidate_layers(value, generated)
        identity = {'graph_sha256': 'a' * 64, 'snapshot_sha256': 'b' * 64,
                    'instance_hash': 'c' * 64}
        valid = {'candidate': 'a', 'first_failure_layer': 'V2', 'reason': 'missing'}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'class-layers.npz'
            for data in ({'B0': []},
                         {'B0': [valid, valid], 'B1': [], 'B2': []},
                         {'B0': [{**valid, 'first_failure_layer': 'WRONG'}], 'B1': [], 'B2': []}):
                with self.assertRaises(ValueError):
                    write_candidate_layers(path, layer, baseline_layers=data, **identity)


if __name__ == '__main__':
    unittest.main()

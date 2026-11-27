"""Seed-free, synthetic corruption tests for the SMOKE NPZ verifier."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.stage_report import CODES
from tools.smoke_01 import check_audit_artifacts


class SmokeArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.ids = [f'synthetic_{i}' for i in range(4)]
        self.graph, self.snapshot, self.instance = 'a' * 64, 'b' * 64, 'c' * 64
        self.layers = np.zeros(1394064, dtype=np.uint8)
        self.layers[:3] = [CODES['V5_FAILED'], CODES['VERIFIED'], CODES['NOT_GENERATED']]
        base = [{'candidate': 'static-a', 'first_failure_layer': 'VERIFIED', 'reason': ''}]
        self.meta = {'format': 'GENSPACE-CLASS-LAYERS-v1', 'graph_sha256': self.graph,
                     'snapshot_sha256': self.snapshot, 'instance_hash': self.instance,
                     'codes': CODES, 'baseline_candidate_layers': {m: base for m in ('B0', 'B1', 'B2')}}
        self.rows = []
        for iid in self.ids:
            for method in ('B0', 'B1', 'B2'):
                self.rows.append({'instance_id': iid, 'method': method, 'candidate_count': 1,
                                  'verified_count': 1, 'validator_rejections': {}})
            self.rows.append({'instance_id': iid, 'method': 'O1', 'instance_hash': self.instance,
                              'validator_rejections': {'V5': 1}, 'verified_count': 1,
                              'not_generated_count': 1, 'rich_graph_in_domain_count': 3})
            self.write(iid, self.layers, self.meta)
        checksum = hashlib.sha256(self.layers.tobytes()).hexdigest()
        self.validations = {iid: {'counts': {'first_failure_layer_sha256': checksum}} for iid in self.ids}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, iid, layers, meta):
        meta = {**meta, 'instance_id': iid}
        np.savez_compressed(self.directory / (iid + '.npz'), layers=layers,
                            metadata_json=np.array(json.dumps(meta, sort_keys=True)))

    def check(self):
        return check_audit_artifacts(self.directory, self.ids, self.rows, self.graph,
                                     self.snapshot, self.validations)

    def test_valid_exact_four_and_missing_or_extra(self):
        self.assertTrue(self.check()['ok'])
        (self.directory / (self.ids[0] + '.npz')).unlink()
        self.assertFalse(self.check()['ok'])
        self.write(self.ids[0], self.layers, self.meta)
        (self.directory / 'unexpected.txt').write_text('extra')
        self.assertFalse(self.check()['ok'])

    def test_corruption_and_layer_swap_fail(self):
        bad = self.layers.copy()
        bad[0] = 99
        self.write(self.ids[0], bad, self.meta)
        self.assertFalse(self.check()['ok'])
        swapped = self.layers.copy()
        swapped[0], swapped[1] = swapped[1], swapped[0]
        self.write(self.ids[0], swapped, self.meta)
        self.assertFalse(self.check()['ok'])  # same aggregate counts, different classes

    def test_wrong_hash_and_duplicate_baseline_fail(self):
        bad = json.loads(json.dumps(self.meta))
        bad['snapshot_sha256'] = 'd' * 64
        self.write(self.ids[0], self.layers, bad)
        self.assertFalse(self.check()['ok'])
        bad = json.loads(json.dumps(self.meta))
        bad['baseline_candidate_layers']['B0'].append(bad['baseline_candidate_layers']['B0'][0])
        self.write(self.ids[0], self.layers, bad)
        self.assertFalse(self.check()['ok'])

    def test_wrong_instance_id_fails(self):
        meta = {**self.meta, 'instance_id': 'different_identity'}
        np.savez_compressed(self.directory / (self.ids[0] + '.npz'), layers=self.layers,
                            metadata_json=np.array(json.dumps(meta, sort_keys=True)))
        self.assertFalse(self.check()['ok'])


if __name__ == '__main__':
    unittest.main()

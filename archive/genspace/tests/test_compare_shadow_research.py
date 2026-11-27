import json
import tempfile
import unittest
from pathlib import Path
from tools.compare_shadow_research import compare


class CompareShadowResearchTests(unittest.TestCase):
    def test_only_execution_metadata_may_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            for root, stamp, elapsed in ((a, 'a', 1), (b, 'b', 2)):
                (root / 'x').mkdir(parents=True)
                data = {'rows': [{'method': 'O1', 'runtime_seconds': elapsed,
                                  'snapshot_hash': stamp, 'instance_hash': 'same',
                                  'application_utility': 0.75}],
                        'check': {'ok': True, 'counts': {'digest': 'same'}}}
                (root / 'x' / 'result.json').write_text(json.dumps(data))
            self.assertTrue(compare(a, b, ['x'])['all_equal'])
            path = b / 'x' / 'result.json'
            data = json.loads(path.read_text()); data['rows'][0]['application_utility'] = 0.74
            path.write_text(json.dumps(data))
            self.assertFalse(compare(a, b, ['x'])['all_equal'])


if __name__ == '__main__':
    unittest.main()

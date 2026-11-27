import json,tempfile,unittest
from pathlib import Path
from tools.shadow_integration import previous_segments,run

class ShadowIntegrationUnits(unittest.TestCase):
    def test_excludes_current_segment(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'00.json').write_text(json.dumps({'executed':['a']}));(p/'01.json').write_text(json.dumps({'executed':['b']}))
            self.assertEqual(previous_segments(p,p/'01.json'),[{'executed':['a']}])
    def test_disallowed_namespace_rejected_before_io(self):
        for ns in ('GENSPACE-FAIL-01-SMOKE','GENSPACE-FAIL-01-PILOT','GENSPACE-FAIL-01-CONFIRM'):
            with self.assertRaises(ValueError):run(namespace=ns)

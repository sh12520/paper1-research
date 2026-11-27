"""Guard migration must preserve audited sampler bytes and fail closed."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from src.core_authorization_compat import GUARD,ANCHOR,core_source_matches
from src import instances

class CoreAuthorizationCompatibilityTests(unittest.TestCase):
    def test_exact_strip_and_all_tampering_rejected(self):
        original=Path('src/instances.py').read_bytes()
        old=json.loads(Path('results/engineering/availability_indices/manifest.json').read_text())['source_fingerprint']['sources']['src/instances.py']
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'src').mkdir();path=root/'src'/'instances.py'
            def verify(raw):
                path.write_bytes(raw)
                return core_source_matches('src/instances.py',old,hashlib.sha256(raw).hexdigest(),root)
            self.assertTrue(verify(original))
            self.assertFalse(verify(original.replace(GUARD,b'',1)))
            self.assertFalse(verify(original.replace(GUARD,GUARD+GUARD,1)))
            self.assertFalse(verify(original.replace(GUARD,GUARD.replace(b'authorize(namespace)',b'authorize( namespace)',1),1)))
            self.assertFalse(verify(original+b'# unauthorized extra source\r\n'))
            self.assertFalse(core_source_matches('src/instances.py','0'*64,hashlib.sha256(original).hexdigest(),root))
    def test_denied_smoke_does_not_hash_or_construct_rng(self):
        cfg={'resource_pressure':'medium','preference_conflict':'high','capability_richness':'rich','composition_depth':2}
        with patch('src.smoke_authorization.authorize',side_effect=PermissionError('AUTHORIZATION_DENIED')), \
             patch('src.instances.digest') as hashed, patch('src.instances.random.Random') as rng:
            with self.assertRaises(PermissionError):instances.derive_seed('GENSPACE-FAIL-01-SMOKE','F1',cfg,0)
            with self.assertRaises(PermissionError):instances.generate_instance('F1',cfg,0,namespace='GENSPACE-FAIL-01-SMOKE')
            hashed.assert_not_called();rng.assert_not_called()
        for ns in ('GENSPACE-FAIL-01-PILOT','GENSPACE-FAIL-01-CONFIRM'):
            with patch('src.smoke_authorization.authorize',side_effect=PermissionError('AUTHORIZATION_DENIED')), patch('src.instances.digest') as hashed, patch('src.instances.random.Random') as rng:
                with self.assertRaises(PermissionError):instances.derive_seed(ns,'F1',cfg,0)
                with self.assertRaises(PermissionError):instances.generate_instance('F1',cfg,0,namespace=ns)
                hashed.assert_not_called();rng.assert_not_called()

if __name__=='__main__':unittest.main()

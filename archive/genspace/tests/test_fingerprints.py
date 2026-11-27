import unittest
from src.fingerprints import fingerprint

class FingerprintTest(unittest.TestCase):
    def test_complete_and_deterministic(self):
        a = fingerprint()
        self.assertEqual(a, fingerprint())
        self.assertEqual(len(a['source_hash']), 64)
        self.assertEqual(len(a['config_hash']), 64)
        self.assertEqual(len(a['dependency_hash']), 64)
        self.assertIn('src/fingerprints.py', a['sources'])
        self.assertIn('tests/test_fingerprints.py', a['sources'])

if __name__ == '__main__': unittest.main()

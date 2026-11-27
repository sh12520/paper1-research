import gzip
import tempfile
import unittest
from pathlib import Path
from tools.external_reference import encode_signature, external_unique, compare_sorted

class ExternalReferenceTests(unittest.TestCase):
    def test_merge_dedup_and_exact_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            values=[encode_signature((n, ('slot', n % 2))) for n in (3,2,3,1,4,4,2)]
            result=external_unique(iter(values), root/'first.gz',workspace=d,chunk_size=2,merge_width=2)
            self.assertEqual(result['input_count'],7)
            self.assertEqual(result['unique_count'],4)
            with gzip.open(root/'first.gz','rb') as inp:
                self.assertEqual(list(inp),sorted(set(values)))
            external_unique(reversed(values),root/'second.gz',workspace=d,chunk_size=3)
            self.assertTrue(compare_sorted(root/'first.gz',root/'second.gz'))
            external_unique(values[:-1]+[b'different\n'],root/'third.gz',workspace=d,chunk_size=2)
            self.assertFalse(compare_sorted(root/'first.gz',root/'third.gz'))
            with self.assertRaises(FileExistsError): external_unique(values,root/'first.gz',workspace=d)

if __name__ == '__main__': unittest.main()

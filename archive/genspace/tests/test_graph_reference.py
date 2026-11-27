import unittest
import gzip
import json
import struct
import tempfile
from pathlib import Path
from src.compact_graph import graph_library
from tools.audit_external_reference import fixture
from tools.audit_full_graph_reference import worker, compare

class GraphReferenceTests(unittest.TestCase):
    def test_small_exact_independent_stream(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=fixture(2); graph=graph_library(p)
            header=json.dumps({'format':'GENSPACE-GRAPH-v1','key_bytes':49}).encode('utf8')
            target=root/'graph.gz'
            with gzip.open(target,'wb') as out:
                out.write(b'GSG1'+struct.pack('>I',len(header))+header)
                for key in sorted(graph.entries): out.write(key+b'\0'*7)
            ref=root/'ref.gz'
            r=worker(0,1,ref,2,2)
            self.assertEqual(r['input_count'],562)
            result=compare([ref],target)
            self.assertTrue(result['exact_bytewise_sets_equal'], result)

if __name__ == '__main__': unittest.main()

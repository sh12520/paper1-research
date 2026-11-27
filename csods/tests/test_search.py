"""Compare both graph-free cursors with exhaustive small syntax spaces."""

from struct import pack
import unittest

from csods.compact_semantics import CompactEncoder
from csods.depth_search import DepthCursor
from csods.engine import enumerate_compositions
from csods.enumeration import public_domain
from csods.example import public_example
from csods.generic_search import GenericCursor
from csods.grammar_search import FlatPublicScore, Limits, decode_witness
from csods.state_machine import normalize


class SearchTests(unittest.TestCase):
    def compare_with_reference(self, cursor_type, depth, conditional):
        public = public_example(conditional=conditional)
        encoder = CompactEncoder(public)
        scorer = FlatPublicScore(public)
        ranks = {}
        for node in enumerate_compositions(public_domain(public), depth, public.capabilities):
            key = encoder.encode(normalize(node, public))
            groups = scorer.group_count(key)
            if key[0] == 1 and 1 <= groups <= (2 if depth <= 2 else 4):
                ranks[key] = scorer.score(key, groups)
        expected = sorted((score, key) for key, score in ranks.items())
        self.assertTrue(expected)

        cursor = cursor_type(public, depth, Limits(15, 50000, 50000))
        for score, key in expected:
            observed = cursor.next_contract()
            self.assertIsNotNone(observed)
            self.assertEqual(observed.key, key)
            self.assertEqual(pack(">d", observed.score), pack(">d", score))
            self.assertEqual(encoder.encode(decode_witness(observed.witness)), key)
        self.assertIsNone(cursor.next_contract())
        self.assertTrue(cursor.exhausted)

    def test_csods_depths(self):
        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                self.compare_with_reference(DepthCursor, depth, conditional=depth < 3)

    def test_generic_control(self):
        self.compare_with_reference(GenericCursor, 2, conditional=True)

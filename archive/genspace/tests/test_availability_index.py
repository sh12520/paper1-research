import unittest
from itertools import product
from dataclasses import replace
from src.models import Profile
from src.engine import Domain, enumerate_compositions
from src.enumeration import syntax_key
from src.compact_semantics import CompactEncoder
from src.compact_graph import graph_library
from src.compact_dp import compact_library
from test_semantic_dp import fixture
from tools.build_availability_index import GROUPS, PATTERNS

class AvailabilityIndexTests(unittest.TestCase):
    def test_all_patterns_legacy_semantic_sets_and_lexical_witnesses(self):
        p=fixture((Profile(.4,1.,1.),Profile(.8,1.,1.)))
        domain=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        rich=CompactEncoder(p); roles=tuple(sorted(p.capabilities))
        allkeys={rich.encode(n) for n in enumerate_compositions(domain,2,p.capabilities)}
        for pattern in PATTERNS:
            available=set(p.capabilities)
            for i,group in enumerate(GROUPS):
                if not pattern&(1<<i): available.difference_update(group)
            # fixture is SimpleNamespace; shallow copy public state explicitly.
            from types import SimpleNamespace
            public=SimpleNamespace(**{**p.__dict__,'capabilities':tuple(sorted(available))})
            encoder=CompactEncoder(public)
            for depth in (1,2):
                legacy={}
                for node in enumerate_compositions(domain,depth,available):
                    key=encoder.encode(node); text=syntax_key(node)
                    if key not in legacy or text<legacy[key]: legacy[key]=text
                if depth==1: actual=compact_library(public,1)
                else:
                    graph=graph_library(public)
                    actual={k:graph.render(token) for k,token in graph.entries.items()}
                self.assertEqual(actual,legacy,(pattern,depth))
                if depth==2:
                    filt={key for key in allkeys if all(key[1+2*i]==255 or role in available for i,role in enumerate(roles))}
                    self.assertEqual(set(actual),filt,pattern)

if __name__=='__main__': unittest.main()

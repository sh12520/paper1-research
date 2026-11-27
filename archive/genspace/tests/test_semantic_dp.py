import unittest
from dataclasses import asdict
from types import SimpleNamespace
from time import perf_counter
from src.models import Profile, Static, If
from src.enumeration import syntax_key
from src.registry import default_registry
from src.engine import enumerate_compositions, Domain
from src.semantic_dp import library, streaming_reference
from src.state_machine import semantic_key


def fixture(profiles):
    reg = default_registry()
    return SimpleNamespace(b2_profiles=tuple(profiles), conditions=('moving',),
        durations=(1,), offsets=(1,), intervals=((0,2),), offload_levels=('edge',),
        capabilities=tuple(reg), registry={k:asdict(v) for k,v in reg.items()},
        horizon=3, states=('still','moving'), public_constraints={'reservation_supported':True})


def reference(p, depth):
    d=Domain(p.b2_profiles, p.conditions, p.durations, p.offsets, p.intervals, p.offload_levels)
    return {semantic_key(n, p) for n in enumerate_compositions(d, depth, p.capabilities)}

class SemanticDPTests(unittest.TestCase):
    def test_small_domain_full_equality(self):
        p=fixture((Profile(.4,1,1), Profile(.8,1,1)))
        for depth in (0,1,2):
            self.assertEqual(set(library(p, depth)), reference(p, depth))
            self.assertEqual(streaming_reference(p, depth), reference(p, depth))

    def test_small_domain_global_lexical_witness(self):
        p=fixture((Profile(.4,1,1), Profile(.8,1,1)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        minima={}
        for n in enumerate_compositions(d,2,p.capabilities):
            key=semantic_key(n,p)
            value=syntax_key(n)
            if key not in minima or value < minima[key]: minima[key]=value
        actual=library(p,2)
        self.assertEqual({k:syntax_key(v.witness) for k,v in actual.items()}, minima)

    def test_lexical_witness_with_redundant_if(self):
        p=fixture((Profile(.4,1,1),))
        leaf=Static(p.b2_profiles[0])
        nested=If('moving', If('moving', leaf, leaf), If('moving', leaf, leaf))
        entry=library(p, 2)[semantic_key(leaf,p)]
        self.assertLessEqual(syntax_key(entry.witness), syntax_key(nested))

    def test_full_27_profile_depth_one(self):
        from itertools import product
        p=fixture(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
        self.assertEqual(set(library(p, 1)), reference(p, 1))

if __name__ == '__main__': unittest.main()

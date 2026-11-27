import unittest
from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.models import Profile, If, Sequence, Delay, ValidFor, Offload
from src.state_machine import semantic_key
from test_semantic_dp import fixture

class CompactTests(unittest.TestCase):
    def test_encoding_is_injective_on_all_small_domain_depth2_signatures(self):
        p=fixture((Profile(.4,1,1),Profile(.8,1,1)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        codec=CompactEncoder(p); mapping={}
        for node in enumerate_compositions(d,2,p.capabilities):
            key=semantic_key(node,p); packed=codec.pack(key)
            self.assertEqual(mapping.setdefault(packed,key),key)
        self.assertTrue(mapping)

    def test_compact_transfer_matches_compiler_for_every_small_depth2_pair(self):
        from itertools import product
        p=fixture((Profile(.4,1,1),Profile(.8,1,1)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        c=CompactEncoder(p)
        children=list(enumerate_compositions(d,1,p.capabilities))
        for left,right in product(children,repeat=2):
            l,r=c.encode(left),c.encode(right)
            for name,value,ast in (('If','moving',If('moving',left,right)),('Sequence',1,Sequence(1,left,right))):
                self.assertEqual(c.combine(name,value,l,r),c.encode(ast))
        for child in children:
            l=c.encode(child)
            for name,value,ast in (('Delay',1,Delay(1,child)),('ValidFor',(0,2),ValidFor((0,2),child)),('Offload','edge',Offload('edge',child))):
                self.assertEqual(c.combine(name,value,l),c.encode(ast))

    def test_compact_library_matches_independent_full_small_reference_and_witnesses(self):
        from src.compact_dp import compact_library
        from src.enumeration import syntax_key
        p=fixture((Profile(.4,1,1),Profile(.8,1,1)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        c=CompactEncoder(p)
        for depth in (1,2):
            ref={}
            for node in enumerate_compositions(d,depth,p.capabilities):
                k=c.encode(node); v=syntax_key(node)
                if k not in ref or v<ref[k]: ref[k]=v
            self.assertEqual(compact_library(p,depth),ref)

    def test_full_27_profile_depth1(self):
        from itertools import product
        from src.compact_dp import compact_library
        p=fixture(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        c=CompactEncoder(p)
        self.assertEqual(set(compact_library(p,1)),{c.encode(n) for n in enumerate_compositions(d,1,p.capabilities)})

    def test_compressed_witness_graph_matches_full_small_reference(self):
        from src.compact_graph import graph_library
        from src.enumeration import syntax_key
        p=fixture((Profile(.4,1,1),Profile(.8,1,1)))
        d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
        c=CompactEncoder(p); ref={}
        for node in enumerate_compositions(d,2,p.capabilities):
            k=c.encode(node); v=syntax_key(node)
            if k not in ref or v<ref[k]: ref[k]=v
        g=graph_library(p)
        self.assertEqual({k:g.render(v) for k,v in g.entries.items()},ref)

    def test_all_full27_depth1_transfer_operators(self):
        from itertools import product
        from src.models import Static
        p=fixture(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
        c=CompactEncoder(p); children=[Static(x) for x in p.b2_profiles]
        signatures=[c.encode(x) for x in children]
        for i,left in enumerate(children):
            self.assertEqual(c.apply_delay(1,signatures[i]), c.encode(Delay(1,left)))
            self.assertEqual(c.apply_valid_for((0,2),signatures[i]), c.encode(ValidFor((0,2),left)))
            self.assertEqual(c.apply_offload('edge',signatures[i]), c.encode(Offload('edge',left)))
            for j,right in enumerate(children):
                self.assertEqual(c.apply_if('moving',signatures[i],signatures[j]),c.encode(If('moving',left,right)))
                self.assertEqual(c.apply_sequence(1,signatures[i],signatures[j]),c.encode(Sequence(1,left,right)))

if __name__=='__main__': unittest.main()

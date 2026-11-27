import unittest
from dataclasses import replace
from src.engineering_depth2 import PackedEvaluator, make_fixtures
from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.registry import default_registry
from src.state_machine import verify_instance

class PackedTimingTests(unittest.TestCase):
    def test_packed_public_and_private_match_interpreter(self):
        for inst in (make_fixtures()[0], make_fixtures()[1]):
            profiles = (inst.public.b2_profiles[0], inst.public.b2_profiles[-1])
            p = replace(inst.public, b2_profiles=profiles, mr_profiles=profiles, m0_profiles=profiles[:1])
            inst = replace(inst, public=p)
            e = PackedEvaluator(inst); enc = CompactEncoder(p)
            domain=Domain(profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
            for node in enumerate_compositions(domain,2,default_registry()):
                key=enc.encode(node); actual=verify_instance(node,inst,2)
                if not e.public_filter(key):
                    self.assertEqual(actual.failed_layer,'V2'); continue
                physical=e.physical(key)
                if physical is None:
                    self.assertEqual(actual.failed_layer,'V4'); continue
                accepted,a,n=e.acceptance(physical)
                self.assertEqual(accepted,actual.verified)
                self.assertAlmostEqual(a,actual.application_utility)
                self.assertAlmostEqual(n,actual.network_utility)

if __name__=='__main__': unittest.main()

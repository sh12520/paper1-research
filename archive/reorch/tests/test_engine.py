import json
import unittest
from dataclasses import replace

from config import generate_instance
from models import Instance, Profile
from negotiation_engine import simulate
from policies import POLICIES


class EngineTests(unittest.TestCase):
    def test_ledger_and_common_instance(self):
        for seed in range(10):
            for family in ('COUPLING_SHIFT', 'STATIC_COUPLING'):
                instance = generate_instance(seed, family, 'strong', 'medium')
                original = repr(instance)
                for policy in POLICIES:
                    result = simulate(instance, policy, .3)
                    ledger = json.loads(result['final_ledger'])
                    portfolio = json.loads(result['committed_portfolio'])
                    self.assertTrue(all(x <= c + 1e-8 for x, c in zip(ledger, instance.capacity)))
                    for j in range(3):
                        self.assertAlmostEqual(ledger[j], sum(instance.profiles[s][k].demand[j] for s, k in portfolio.items()))
                    self.assertEqual(repr(instance), original)
                self.assertEqual(instance, generate_instance(seed, family, 'strong', 'medium'))

    def test_symmetric_permutation(self):
        names = ('A','B','C','D')
        profiles = {s: (Profile((30,30,30),0), Profile((20,20,20),1), Profile((10,10,10),2)) for s in names}
        ins = Instance(1,'STATIC_COUPLING','weak','medium',(65,65,65),profiles,
                       {s:(1.,.9,.8) for s in names}, {s:8. for s in names},
                       {s:.75 for s in names}, {s:1.1 for s in names})
        perm = dict(zip(names, reversed(names)))
        other = replace(ins, profiles={perm[s]:v for s,v in ins.profiles.items()},
                        utilities={perm[s]:v for s,v in ins.utilities.items()},
                        deadlines={perm[s]:v for s,v in ins.deadlines.items()},
                        reservation={perm[s]:v for s,v in ins.reservation.items()},
                        aspiration_start={perm[s]:v for s,v in ins.aspiration_start.items()})
        for policy in POLICIES:
            a, b = simulate(ins, policy, 0), simulate(other, policy, 0)
            for metric in ('welfare','completion_rate','deadline_miss_rate','wall_time'):
                self.assertAlmostEqual(a[metric], b[metric])

    def test_no_shift_no_overhead_ample_capacity(self):
        ins = replace(generate_instance(4,'STATIC_COUPLING','weak','loose'), capacity=(1000.,1000.,1000.))
        static = simulate(ins, 'B3', 0)
        oracle = simulate(ins, 'O1', 0)
        self.assertAlmostEqual(static['welfare'], oracle['welfare'])
        self.assertEqual(static['completion_rate'], oracle['completion_rate'])


if __name__ == '__main__':
    unittest.main()

"""Deterministic public-only unit fixtures; no instances or seeds are generated."""
import unittest
from types import SimpleNamespace
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from unittest.mock import patch
import numpy as np
import public_search
from public_search import PublicView,make_plan,complementarity
from src.registry import default_registry

def fixture():
    registry=default_registry();roles=tuple(sorted(registry));keys=np.zeros((6,49),dtype=np.uint8);keys[:,1:25]=255
    for i,names in enumerate([(),('apply_conditional_policy',),('schedule_start',),('set_validity_interval',),('enable_edge_offload',),('apply_conditional_policy','enable_edge_offload')]):
        for name in names:keys[i,1+2*roles.index(name)]=1
    library=SimpleNamespace(keys=keys,profiles=np.zeros((6,6),dtype=np.uint8),level=np.zeros((6,6),dtype=np.uint8),role_masks=np.zeros((6,6),dtype=np.uint16),role_costs=np.zeros((4096,3)),execution_costs=np.zeros(4096))
    library.level[4:]=1
    availability=SimpleNamespace(mask=lambda depth:np.ones(6,dtype=bool))
    caps=tuple(n for n in registry if n!='apply_phased_policy')
    view=PublicView(2,('still','moving'),3,tuple((t,s,.8,.8,.8) for t in range(3) for s in ('still','moving')),((.9,1.,1.),),caps,(('fh_rate_factor',.4),('offload_edge_factor',.5),('offload_fh_factor',.7),('offload_ran_factor',.5)),(),tuple((n,c.execution_cost,tuple(c.resource_cost.items())) for n,c in registry.items()))
    return view,library,availability

class Tests(unittest.TestCase):
    def test_disjoint_deficit_relief_is_complementary(self):
        x=np.array([1.,0.,0.,0.]);y=np.array([0.,1.,0.,0.])
        self.assertEqual(complementarity(x,x),0.)
        self.assertGreater(complementarity(x,y),0.)
    def test_phase_validity_alone_is_admitted(self):
        view,library,availability=fixture();plan=make_plan(view,library,availability,1,'DG-PCE')
        self.assertIn('P',plan.mechanism_order);self.assertIn(3,plan.order)
    def test_strategy_universe_and_independent_probe_accounting(self):
        view,library,availability=fixture()
        plans={n:make_plan(view,library,availability,1,n) for n in ('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY')}
        self.assertEqual(set(plans['DG-PCE'].order),set(plans['RANDOM-BUDGET'].order))
        self.assertEqual(set(plans['DG-PCE'].order),set(plans['FLAT-FEASIBILITY'].order))
        self.assertNotIn(5,plans['SINGLETON-ONLY'].order)
        self.assertEqual(plans['RANDOM-BUDGET'].probe_count,0)
        self.assertEqual(plans['FLAT-FEASIBILITY'].probe_count,0)
        self.assertEqual(plans['GLOBAL-FREQUENCY'].probe_count,0)
        self.assertGreater(plans['DG-PCE'].probe_count,0)
        self.assertEqual(plans['RANDOM-BUDGET'].public_ranked_count,0)
        self.assertEqual(plans['GLOBAL-FREQUENCY'].mechanism_order,('O','P','C','D'))
    def test_b2_proxy_reused_exactly_once(self):
        view,library,availability=fixture()
        with patch('public_search._static_deficits',wraps=public_search._static_deficits) as scan:
            plan=make_plan(view,library,availability,1,'DG-PCE')
        self.assertEqual(scan.call_count,1)
        self.assertEqual(plan.b2_proxy_count,len(view.profiles))

if __name__=='__main__':unittest.main()

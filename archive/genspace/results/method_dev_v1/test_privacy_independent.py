"""Independent public-search noninterference tests; no instance generation."""
import sys, unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from src.instances import deserialize_instance
from src.registry import default_registry
from src.fast_exact import FastLibrary
from public_search import sanitize_public,make_plan,deadlock_signature
from private_protocol import Evidence,PrivateAgent,PublicVerifier,BudgetExhausted,negotiate
from runtime import verification_public,choose_variant

class Mask:
    def __init__(self,n):self.n=n
    def mask(self,depth):return np.ones(self.n,dtype=bool)

def fake_library():
    roles=tuple(sorted(default_registry()));n=9
    keys=np.zeros((n,49),dtype=np.uint8)
    for i in range(12):keys[:,1+2*i]=255
    for row, names in enumerate(((),('apply_conditional_policy',),('schedule_start',),
          ('apply_phased_policy',),('set_validity_interval',),('enable_edge_offload',),
          ('apply_conditional_policy','enable_edge_offload'),('schedule_start','enable_edge_offload'),
          ('apply_phased_policy','enable_edge_offload'))):
        for name in names:keys[row,1+2*roles.index(name)]=1
    profiles=np.tile(np.arange(n,dtype=np.uint8)[:,None],(1,6))
    level=np.zeros((n,6),dtype=np.uint8);level[5:]=1
    return SimpleNamespace(keys=keys,profiles=profiles,level=level,
       role_masks=np.zeros((n,6),dtype=np.uint16),role_costs=np.zeros((4096,3)),
       execution_costs=np.zeros(4096))

class ConfigGuard(dict):
    def __getitem__(self,key):
        if key!='composition_depth':raise AssertionError('forbidden configuration access: '+str(key))
        return super().__getitem__(key)

class PublicGuard:
    def __init__(self,public):self._public=public
    def __getattr__(self,name):
        if name=='family':raise AssertionError('forbidden family access')
        if name=='configuration':return ConfigGuard(self._public.configuration)
        return getattr(self._public,name)

class IndependentPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=next((ROOT/'results/pilot/instances').glob('F1__medium__high__rich__d2__s0.json'))
        cls.public=deserialize_instance(path.read_text(encoding='utf8')).public
        cls.lib=fake_library();cls.available=Mask(len(cls.lib.keys))

    def test_public_allowlist_never_reads_labels(self):
        guarded=sanitize_public(PublicGuard(self.public))
        self.assertFalse(hasattr(guarded,'family'))
        self.assertFalse(hasattr(guarded,'configuration'))
        self.assertFalse(hasattr(guarded,'private'))
        self.assertFalse(hasattr(guarded,'instance_hash'))
        self.assertEqual(guarded,sanitize_public(self.public))

    def test_forbidden_label_mutation_does_not_change_public_order(self):
        cfg={**self.public.configuration,'resource_pressure':'redacted','preference_conflict':'redacted','capability_richness':'redacted'}
        changed=replace(self.public,family='redacted',configuration=cfg)
        a,b=sanitize_public(self.public),sanitize_public(changed)
        self.assertEqual(a,b);self.assertEqual(deadlock_signature(a,3),deadlock_signature(b,3))
        for strategy in ('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY'):
            left=make_plan(a,self.lib,self.available,3,strategy)
            right=make_plan(b,self.lib,self.available,3,strategy)
            np.testing.assert_array_equal(left.order,right.order)
            self.assertEqual(left.signature,right.signature)
            self.assertEqual(left.mechanism_order,right.mechanism_order)

    def test_private_agent_api_and_protocol_messages(self):
        app={'quality_weight':1.,'latency_weight':1.,'start_delay_weight':1.,'switching_penalty':1.,'reservation':0.}
        net={'ran_cost':1.,'fh_cost':1.,'edge_cost':1.,'policy_complexity_cost':1.,'actuation_switching_cost':1.,'reservation':0.}
        actions=tuple((t,s,self.public.b2_profiles[0],'none') for t in range(self.public.horizon) for s in self.public.states)
        sur={(t,s):{'RAN':0.,'FH':0.,'EDGE':0.} for t,s,_,_ in actions}
        exe={(t,s):0. for t,s,_,_ in actions}
        evidence=Evidence(1,'static',actions,sur,exe)
        application=PrivateAgent('application',self.public,app)
        network=PrivateAgent('network',self.public,net)
        self.assertFalse(hasattr(application,'agreed_utility'))
        pool=[evidence]
        self.assertIsInstance(application.choose(pool,set()),int)
        self.assertIn(application.respond(evidence),('ACCEPT','REJECT'))
        winner,events=negotiate(pool,application,network,max_rounds=2)
        self.assertEqual(winner.class_id,1)
        self.assertTrue(all(e['message'] in ('PROPOSE','ACCEPT','REJECT','COUNTER') for e in events))
        self.assertTrue(all(set(e)<= {'agent','message','candidate_id'} for e in events))

    def test_changing_responder_weights_with_same_response_does_not_change_proposal(self):
        app={'quality_weight':1.,'latency_weight':2.,'start_delay_weight':3.,'switching_penalty':4.,'reservation':0.}
        n1={'ran_cost':1.,'fh_cost':1.,'edge_cost':1.,'policy_complexity_cost':1.,'actuation_switching_cost':1.,'reservation':0.}
        n2={'ran_cost':40.,'fh_cost':2.,'edge_cost':30.,'policy_complexity_cost':2.,'actuation_switching_cost':25.,'reservation':0.}
        actions=tuple((t,s,self.public.b2_profiles[0],'none') for t in range(self.public.horizon) for s in self.public.states)
        sur={(t,s):{'RAN':0.,'FH':0.,'EDGE':0.} for t,s,_,_ in actions}
        exe={(t,s):0. for t,s,_,_ in actions}
        pool=[Evidence(1,'static',actions,sur,exe)]
        def trial(net):
            return negotiate(pool,PrivateAgent('application',self.public,app),
                             PrivateAgent('network',self.public,net),max_rounds=2)[1]
        self.assertEqual(trial(n1),trial(n2))

    def test_verifier_counts_real_candidate_calls_and_stops_at_budget(self):
        public=verification_public(self.public);library=FastLibrary.from_graph(scope='pilot-execution');library.bind_public_basis(public)
        variant=choose_variant(public,library);ids=[int(x) for x in np.flatnonzero(variant.mask(2))[:3]]
        v=PublicVerifier(public,variant,2,2,library)
        with self.assertRaises(ValueError):v.prepare_batch(ids)
        self.assertEqual(v.calls,0);self.assertEqual(v.batch_candidate_checks,0)
        v.prepare_batch(ids[:2]);v.verify(ids[0]);v.verify(ids[1])
        self.assertEqual(v.calls,2);self.assertEqual(v.batch_candidate_checks,2)
        with self.assertRaises(BudgetExhausted):v.verify(ids[2])
        self.assertEqual(v.state_machine_calls,0)

if __name__=='__main__':unittest.main()

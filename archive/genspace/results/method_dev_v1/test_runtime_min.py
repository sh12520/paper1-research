"""Small execution tests on already serialized PILOT files only."""
import json,sys,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary
import src.instances as instances
from runtime import verification_public,choose_variant,run
from public_search import sanitize_public
from private_protocol import PrivateAgent

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))
        cls.iid=plan['instances'][0]['instance_id']
        cls.instance=deserialize_instance((ROOT/'results/pilot/instances'/f'{cls.iid}.json').read_text(encoding='utf8'))
        cls.old=json.loads((ROOT/'results/pilot/main'/cls.iid/'result.json').read_text(encoding='utf8'))
        cls.library=FastLibrary.from_graph(scope='pilot-execution')
        cls.library.bind_public_basis(verification_public(cls.instance.public))

    def test_public_adapter_hides_labels(self):
        public=verification_public(self.instance.public)
        for attr in ('family','configuration','resource_pressure','preference_conflict'):
            self.assertFalse(hasattr(public,attr))

    def test_b2_exact_agreement_without_seed_generation(self):
        def forbidden(*a,**k):raise AssertionError('new random instance or seed forbidden')
        old_seed,old_gen=instances.derive_seed,instances.generate_instance
        instances.derive_seed=instances.generate_instance=forbidden
        public=verification_public(self.instance.public);view=sanitize_public(self.instance.public)
        variant=choose_variant(public,self.library)
        app=PrivateAgent('application',public,self.instance.private.application)
        net=PrivateAgent('network',public,self.instance.private.network)
        try:out,history=run(view,public,variant,app,net,self.library,'B2')
        finally:instances.derive_seed,instances.generate_instance=old_seed,old_gen
        expected=next(r['agreement'] for r in self.old['rows'] if r['method']=='B2')
        self.assertTrue(all(x['agreement']==expected and x['verification_calls']==27 for x in out.values()))
        self.assertTrue(all(x['message'] in ('PROPOSE','ACCEPT','REJECT') for x in history))

    def test_budget_prefix_equivalence(self):
        plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))
        iid=plan['instances'][10]['instance_id']
        instance=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        def once(stop):
            public=verification_public(instance.public);view=sanitize_public(instance.public)
            return run(view,public,choose_variant(public,self.library),
                       PrivateAgent('application',public,instance.private.application),
                       PrivateAgent('network',public,instance.private.network),self.library,'DG-PCE',stop_budget=stop)
        a,ha=once(100);b,hb=once(500)
        ignore={'elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
        self.assertEqual({k:v for k,v in a[100].items() if k not in ignore},
                         {k:v for k,v in b[100].items() if k not in ignore})
        self.assertEqual(ha,hb[:len(ha)])
        self.assertLessEqual(b[500]['verification_calls'],500)

    def test_round_limit_stops_before_next_candidate(self):
        public=verification_public(self.instance.public);view=sanitize_public(self.instance.public)
        fake_history=[{'message':'PROPOSE','candidate_id':0,'agent':0}]
        with patch('runtime.ROUND_LIMIT',1),patch('runtime.negotiate',return_value=(None,fake_history)):
            out,_=run(view,public,choose_variant(public,self.library),
                PrivateAgent('application',public,self.instance.private.application),
                PrivateAgent('network',public,self.instance.private.network),self.library,'DG-PCE',stop_budget=100)
        self.assertEqual(out[100]['verification_calls'],27)
        self.assertEqual(out[100]['termination_reason'],'round_limit')

if __name__=='__main__':unittest.main()

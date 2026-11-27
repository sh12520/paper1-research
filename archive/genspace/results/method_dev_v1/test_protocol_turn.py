"""Alternation across incremental verified pools, no random instances."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from private_protocol import negotiate

class StubAgent:
    def __init__(self,eligible):self.eligible=tuple(eligible)
    def choose(self,pool,prohibited):
        ids={e.class_id for e in pool}
        return next((x for x in self.eligible if x in ids and x not in prohibited),None)
    def respond(self,evidence):return 'REJECT'

class TurnTests(unittest.TestCase):
    def test_consecutive_same_agent_then_opponent_gets_next_turn(self):
        app,net=StubAgent((1,2,3)),StubAgent((4,))
        pool=[SimpleNamespace(class_id=x) for x in (1,2)]
        winner,h=negotiate(pool,app,net,max_rounds=10)
        self.assertIsNone(winner)
        self.assertEqual([(x['agent'],x['candidate_id']) for x in h if x['message']=='PROPOSE'],[(0,1),(0,2)])
        pool.extend(SimpleNamespace(class_id=x) for x in (3,4))
        winner,h=negotiate(pool,app,net,max_rounds=1,history=h)
        self.assertIsNone(winner)
        self.assertEqual([(x['agent'],x['candidate_id']) for x in h if x['message']=='PROPOSE'],[(0,1),(0,2),(1,4)])
        self.assertTrue(all(x['message'] in ('PROPOSE','ACCEPT','REJECT') for x in h))

    def test_empty_pool_does_not_change_initial_turn(self):
        app,net=StubAgent((1,)),StubAgent((2,));pool=[]
        _,h=negotiate(pool,app,net,max_rounds=10);self.assertEqual(h,[])
        pool.extend(SimpleNamespace(class_id=x) for x in (1,2))
        _,h=negotiate(pool,app,net,max_rounds=1,history=h)
        self.assertEqual(h[0],{'agent':0,'message':'PROPOSE','candidate_id':1})

    def test_zero_remaining_rounds_never_proposes(self):
        pool=[SimpleNamespace(class_id=1)]
        result,h=negotiate(pool,StubAgent((1,)),StubAgent((1,)),max_rounds=0)
        self.assertIsNone(result);self.assertEqual(h,[])

if __name__=='__main__':unittest.main()

"""Deterministic protocol unit tests; no generated benchmark instances."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from private_protocol import negotiate

class Agent:
    def __init__(self,ids):self.ids=set(ids)
    def choose(self,pool,prohibited):
        return next((x.class_id for x in pool if x.class_id in self.ids and x.class_id not in prohibited),None)
    def respond(self,evidence):return 'REJECT'

class AlternatingTests(unittest.TestCase):
    def test_last_proposer_not_proposal_count_controls_new_batch_turn(self):
        app,net=Agent([1,2,3]),Agent([4]);pool=[SimpleNamespace(class_id=1),SimpleNamespace(class_id=2)]
        winner,history=negotiate(pool,app,net,max_rounds=100)
        self.assertIsNone(winner)
        self.assertEqual([e['agent'] for e in history if e['message']=='PROPOSE'],[0,0])
        start=len(history);pool.extend([SimpleNamespace(class_id=3),SimpleNamespace(class_id=4)])
        _,history=negotiate(pool,app,net,max_rounds=100,history=history)
        self.assertEqual(history[start],{'agent':1,'message':'PROPOSE','candidate_id':4})
        self.assertTrue(all(e['message'] in ('PROPOSE','ACCEPT','REJECT','COUNTER') for e in history))

    def test_round_limit_and_continuation(self):
        app,net=Agent([1,2,3]),Agent([1,2,3]);pool=[SimpleNamespace(class_id=i) for i in (1,2,3)]
        _,history=negotiate(pool,app,net,max_rounds=1)
        self.assertEqual(sum(e['message']=='PROPOSE' for e in history),1)
        self.assertEqual(history[0]['agent'],0)
        start=len(history);_,history=negotiate(pool,app,net,max_rounds=1,history=history)
        self.assertEqual(sum(e['message']=='PROPOSE' for e in history),2)
        self.assertEqual(history[start]['agent'],1)
        self.assertEqual(len(history),4)

if __name__=='__main__':unittest.main()

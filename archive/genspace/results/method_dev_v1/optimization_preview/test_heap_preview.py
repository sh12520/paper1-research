"""Deterministic heap/scan equivalence; no experimental instance generation."""
from pathlib import Path
import sys,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent));sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[2]))
from private_protocol import PrivateAgent,Evidence,negotiate
from preview_protocol import HeapPrivateAgent

class HeapTests(unittest.TestCase):
    def test_incremental_choice_and_protocol(self):
        def fake_utility(public,preferences,actions,**kwargs):
            x=actions[0];return (float(x%4)/4.,float((x*3)%5)/5.)
        pool=[];banned=set();p1={'reservation':0.25};p2={'reservation':0.4}
        with patch('private_protocol.utilities',side_effect=fake_utility):
            scan=(PrivateAgent('application',None,p1),PrivateAgent('network',None,p2))
            heap=(HeapPrivateAgent('application',None,p1),HeapPrivateAgent('network',None,p2))
            for cid in (5,2,3,9,1,4,8,7,6,0):
                pool.append(Evidence(cid,'[]',(cid,),{},{}))
                for a,b in zip(scan,heap):self.assertEqual(a.choose(pool,banned),b.choose(pool,banned))
                if cid%2:banned.add(cid)
            h1=[];h2=[]
            scan=(PrivateAgent('application',None,p1),PrivateAgent('network',None,p2))
            heap=(HeapPrivateAgent('application',None,p1),HeapPrivateAgent('network',None,p2))
            w1,h1=negotiate(pool,*scan,max_rounds=20,history=h1)
            w2,h2=negotiate(pool,*heap,max_rounds=20,history=h2)
            self.assertEqual(None if w1 is None else w1.class_id,None if w2 is None else w2.class_id)
            self.assertEqual(h1,h2)

if __name__=='__main__':unittest.main()

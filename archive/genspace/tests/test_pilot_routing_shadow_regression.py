"""Seed-free unit tests for strict routing regression comparison."""
import unittest
from tools.pilot_routing_shadow_regression import REQUIRED,FIELDS,compare_research,check_events

class RoutingRegressionTests(unittest.TestCase):
    def test_compare_excludes_only_execution_timing_and_snapshot(self):
        a={'rows':[{'method':'B0','agreement':True,'runtime_seconds':1,'snapshot_hash':'a'}],'check':{'ok':True}}
        b={'rows':[{'method':'B0','agreement':True,'runtime_seconds':7,'snapshot_hash':'b'}],'check':{'ok':True}}
        self.assertTrue(compare_research(a,b));b['rows'][0]['agreement']=False;self.assertFalse(compare_research(a,b))
    def test_complete_and_missing_events(self):
        ids=[str(i) for i in range(16)];events=[]
        for iid in ids:
            for name in REQUIRED:
                e={k:1 for k in FIELDS};e.update(event=name,instance_id=iid,process_identity={'pid':1,'creation_time':1},execution_snapshot_hash='x');events.append(e)
        self.assertTrue(check_events(ids,events,'x')['pass'])
        self.assertFalse(check_events(ids,events[:-1],'x')['pass'])
        events[0]['execution_snapshot_hash']='y';self.assertFalse(check_events(ids,events,'x')['pass'])
if __name__=='__main__':unittest.main()

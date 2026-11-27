"""Only Owner-authorized A-B01/A-B02 local faults and boundary coverage."""
import copy
import json
import sqlite3
import time
import unittest
from contracts import Contract, example_contract, jcs, sha
from events import ClockError
import test_candidate as fixtures
from test_candidate import Manual


class OnceFault(Manual):
    def __init__(self,real=False):
        super().__init__();self.armed=False;self.real=real;self.failures=0
    def __call__(self):
        if self.armed:
            self.armed=False;self.failures+=1;raise ClockError("one local post-store sample fault")
        return time.monotonic_ns() if self.real else self.value


class MinimalFixTests(unittest.TestCase):
    # Reuse fixture lifecycle, NOT the 39 original test methods.
    setUp=fixtures.CandidateTests.setUp
    h=fixtures.CandidateTests.h
    tearDown=fixtures.CandidateTests.tearDown
    client_crash=fixtures.CandidateTests.client_crash

    def saved(self,h,path="client.sqlite"):
        db=sqlite3.connect(h.root/path)
        try:return json.loads(db.execute("SELECT state FROM client WHERE id=1").fetchone()[0])
        finally:db.close()

    def clock_case(self,phase,preempt=False,real=False):
        clock=OnceFault(real);holder={}
        def fault(m,candidate):
            if m["phase"]!=phase:return
            h=holder["h"]
            self.assertNotIn(phase,h.client.winners)
            self.assertNotIn(phase,h.client.state["winners"])
            if preempt:clock.set(4000000000)
            clock.armed=True
        policy=(lambda m,k,b:{"delay":0.09} if m["phase"]==phase else {}) if real else None
        h=self.h(client_source=clock,after_latch_store=fault,policy=policy);holder["h"]=h
        result=h.client.run(h.server.host,h.server.port,"fault-case","intent-fault",10)
        h.client.drain();state=self.saved(h)
        self.assertEqual(clock.failures,1)
        self.assertEqual(state["controllerFault"],"CLOCK")
        self.assertNotIn(phase,h.client.winners);self.assertNotIn(phase,state["winners"])
        self.assertFalse(result["confirmationComplete"])
        next_phase={"INTENT_INITIAL":"INTENT_REPLAY","COMMIT_INITIAL":"COMMIT_REPLAY"}.get(phase)
        if next_phase:self.assertFalse(any(e["event"]=="SEND_ACTUAL" and e.get("phase")==next_phase for e in h.ct.events))
        self.assertFalse(any(e["event"]=="PHASE_WINNER_LATCH" and e.get("phase")==phase for e in h.ct.events))
        self.assertTrue(any(e["event"]=="CONTROLLER_FAULT" for e in h.ct.events))
        expected="COMMITTED" if phase.startswith("COMMIT") else "NO_COMMIT_SENT"
        self.assertEqual((state["effectKnowledge"],result["effectKnowledge"]),(expected,expected))
        self.assertEqual(result["status"],"RECOVERY_REQUIRED" if phase.startswith("COMMIT") else "ASSUMPTION_FAILURE")
        return h

    def test_b01_intent_single_post_store_clock_error_then_recovers(self):
        self.clock_case("INTENT_INITIAL")
    def test_b01_commit_single_post_store_clock_error_keeps_receipt(self):
        self.clock_case("COMMIT_INITIAL")
    def test_b01_confirm_clock_error_keeps_previous_success(self):
        h=self.clock_case("COMMIT_REPLAY")
        self.assertIn("COMMIT_INITIAL",self.saved(h)["winners"])
    def test_b01_preempted_draft_and_transient_error_no_ghost(self):
        self.clock_case("INTENT_INITIAL",preempt=True)
    def test_b01_competing_attempts_cannot_rescue_failed_controller(self):
        h=self.clock_case("INTENT_INITIAL",real=True)
        self.assertGreaterEqual(sum(e["event"]=="SEND_ACTUAL" and e.get("phase")=="INTENT_INITIAL" for e in h.ct.events),2)
    def test_b01_winner_persist_exception_before_and_after_commit(self):
        for ambiguous in (False,True):
            h=self.h();original=h.client.persist;failed=[]
            def persist():
                if "COMMIT_INITIAL" in h.client.state["winners"] and not failed:
                    failed.append(True)
                    if ambiguous:original()
                    raise RuntimeError("local winner persistence fault")
                original()
            h.client.persist=persist
            r=h.client.run(h.server.host,h.server.port,"persist-fault","intent-persist-fault",10);h.client.drain()
            s=self.saved(h)
            self.assertEqual(len(failed),1);self.assertEqual(s["controllerFault"],"WINNER_PERSIST_ERROR")
            self.assertNotIn("COMMIT_INITIAL",s["winners"]);self.assertNotIn("COMMIT_INITIAL",h.client.winners)
            self.assertEqual((r["status"],r["effectKnowledge"]),("RECOVERY_REQUIRED","COMMITTED"))
            self.assertFalse(any(e["event"]=="SEND_ACTUAL" and e.get("phase")=="COMMIT_REPLAY" for e in h.ct.events))
    def test_b01_process_exit_during_provisional_commit(self):
        h,r=self.client_crash("PROVISIONAL_COMMIT",25)
        state=self.saved(h,"crash-client.sqlite")
        self.assertNotIn("COMMIT_INITIAL",state["winners"])
        self.assertEqual((r["status"],r["effectKnowledge"]),("RECOVERY_REQUIRED","COMMITTED"))
        self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"CONFIRMED")

    def initial_case(self,elapsed,accepted):
        clock=Manual();start=clock.value
        h=self.h(client_source=clock,after_initial_persist=lambda:clock.set(start+elapsed))
        result=h.client.run(h.server.host,h.server.port,"initial","intent-initial",10);h.client.drain()
        state=self.saved(h)
        self.assertEqual(state["startNs"],start)
        self.assertEqual(state["initialReadyNs"]-start,elapsed)
        self.assertEqual(h.contract.plan["terminalDeadlineMs"],5000)
        if accepted:
            self.assertEqual(result["status"],"COMMITTED");self.assertTrue(result["beforeDeadline"])
        else:
            self.assertEqual((result["status"],result["effectKnowledge"]),("ASSUMPTION_FAILURE","NO_COMMIT_SENT"))
            self.assertFalse(result["confirmationComplete"])
            self.assertFalse(state["winners"])
            self.assertFalse(any(e["event"]=="SEND_ACTUAL" for e in h.ct.events))
            self.assertFalse(h.authority.snapshot()["negotiations"])
        return h
    def test_b02_initial_budget_sufficient(self):
        self.initial_case(99999999,True)
    def test_b02_initial_budget_equality_with_global_strict_slack(self):
        self.initial_case(100000000,True)
    def test_b02_initial_budget_exceeded_by_one(self):
        self.initial_case(100000001,False)
    def test_b02_finite_900ms_initial_persistence_no_sliding_deadline(self):
        self.initial_case(900000000,False)
    def test_b02_cumulative_budget_and_first_cutoff_strict_equality(self):
        c=example_contract()
        for i in (0,1,2,3):
            plan=copy.deepcopy(c.plan)
            prefix=plan["initialBudgetMs"]+sum(c.H[:i+1])+sum(p["transitionMs"] for p in plan["phases"][:i])
            plan["phases"][i]["cutoffMs"]=prefix
            t=copy.deepcopy(c.timing);t["phasePlanRawSha256"]=sha(jcs(plan))
            with self.assertRaisesRegex(ValueError,"budget infeasible"):Contract(jcs(plan),c.policy,t)
    def test_b02_initial_budget_closed_schema_and_bound_digest(self):
        c=example_contract();plan=copy.deepcopy(c.plan);plan.pop("initialBudgetMs")
        t=copy.deepcopy(c.timing);t["phasePlanRawSha256"]=sha(jcs(plan))
        with self.assertRaises(Exception):Contract(jcs(plan),c.policy,t)
        plan=copy.deepcopy(c.plan);plan["initialBudgetMs"]+=1;t["phasePlanRawSha256"]=sha(jcs(plan))
        c2=Contract(jcs(plan),c.policy,t)
        self.assertNotEqual(c.digest,c2.digest)
        self.assertGreater(c2.guard_bound,c.guard_bound)


if __name__=="__main__":unittest.main()

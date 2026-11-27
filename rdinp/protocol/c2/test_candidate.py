"""A-only conformance and bounded negative witnesses; never B qualification."""
import concurrent.futures
import copy
import itertools
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
import uuid
from cryptography.hazmat.primitives import serialization
from authority import Authority
from contracts import Contract, ROOT, MAX, PHASES, example_contract, jcs, parse, sha, digest
from crypto import Identity, Trust, base_message, outcome_digest, response
from endpoint import Responder, post
from events import Clock, ClockError, Trace
from initiator import Initiator


class Manual:
    def __init__(self,value=1000000000):self.value=value
    def __call__(self):return self.value
    def set(self,n):self.value=n


class Harness:
    def __init__(self,root,manual=None,policy=None,tail_hook=None,client_source=None,before_latch=None,after_latch_store=None,after_initial_persist=None,capacity=100,contract=None):
        self.root=root;root.mkdir(parents=True,exist_ok=False);self.contract=contract or example_contract();self.manual=manual
        self.i=Identity("initiator","initiator");self.r=Identity("authority","responder");self.pins=[self.i.pin(),self.r.pin()];self.trust=Trust(self.pins)
        self.clock=Clock("LOCAL-NONPRODUCTION-BOOT","server-monotonic",manual or time.monotonic_ns)
        self.trace=Trace("responder",self.clock,root/"server.events.jsonl")
        self.authority=Authority(root/"authority.sqlite",self.contract,self.clock,self.trace,capacity=capacity,tail_hook=tail_hook)
        self.server=Responder(self.authority,self.r,self.trust,self.trace,policy).start()
        self.cc=Clock("LOCAL-NONPRODUCTION-BOOT","client-monotonic",client_source or time.monotonic_ns);self.ct=Trace("initiator",self.cc,root/"client.events.jsonl")
        self.client=Initiator(root/"client.sqlite",self.contract,self.i,self.trust,self.cc,self.ct,before_latch=before_latch,after_latch_store=after_latch_store,after_initial_persist=after_initial_persist)
        (root/"inputs.json").write_bytes(jcs({"plan":self.contract.plan,"policy":self.contract.policy,"timing":self.contract.timing,"trust":self.pins,"scope":"NONPRODUCTION_LOCAL_MECHANISMS_ONLY"}))
    def make(self,phase="INTENT_INITIAL",attempt=0,neg="n1",units=10,decision=None,**changes):
        b={"units":units,"decisionDigest":decision["decisionDigest"] if decision else "","epoch":decision["epoch"] if decision else 0,"token":decision["token"] if decision else ""}
        m=base_message(self.contract,"INTENT" if phase.startswith("INTENT") else "COMMIT",neg,"intent-"+neg,phase,attempt,"initiator","authority",b);m.update(changes);return self.i.sign(m)
    def call(self,raw):
        m=parse(raw);status,answer=post(self.server.host,self.server.port,"/rdinp/intent" if m["kind"]=="INTENT" else "/rdinp/commit",raw)
        verified=self.trust.verify(answer,self.contract,"authority","responder")
        self.assert_correlated(m,raw,verified);return status,verified
    def assert_correlated(self,m,raw,a):
        assert all(a[k]==m[k] for k in ("negotiationId","intentId","phase","attempt"))
        assert a["requestRawSha256"]==sha(raw) and a["requestJcsSha256"]==sha(jcs(m))
    def reserve(self,neg="n1",units=10):
        return self.call(self.make(neg=neg,units=units))[1]["body"]
    def prepared(self,neg="n1",units=10):
        d=self.reserve(neg,units);self.call(self.make("INTENT_REPLAY",neg=neg,units=units));return d
    def close(self):
        self.client.close();self.server.close()
        (self.root/"observations.json").write_bytes(jcs(self.authority.snapshot()))


class CandidateTests(unittest.TestCase):
    def setUp(self):
        root=Path(os.environ.get("RDINP_EVIDENCE_DIR",str(ROOT/"manual-evidence")))
        self.root=root/(self._testMethodName+"-"+uuid.uuid4().hex[:8]);self.root.mkdir(parents=True,exist_ok=False);self.hs=[]
    def h(self,**kw):
        h=Harness(self.root/("fixture-"+str(len(self.hs))),**kw);self.hs.append(h);return h
    def tearDown(self):
        for h in reversed(self.hs):h.close()

    def test_v1_closed_contract_and_preimages(self):
        c=example_contract();self.assertLess(c.guard_bound,c.plan["leaseNs"])
        for field,value in (("leaseNs",c.guard_bound),("terminalDeadlineMs",1),("sendJitterNs",MAX)):
            plan=copy.deepcopy(c.plan);plan[field]=value;t=copy.deepcopy(c.timing);t["phasePlanRawSha256"]=sha(jcs(plan))
            with self.assertRaises(Exception):Contract(jcs(plan),c.policy,t)
        t=copy.deepcopy(c.timing);t["extra"]=1
        with self.assertRaises(Exception):Contract(c.plan_raw,c.policy,t)
        self.assertNotEqual(digest("POLICY",c.policy),digest("TIMING",c.policy))
    def test_v1_strict_json_and_unicode(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":1.0}',b'{"x":NaN}',b'{"x":9007199254740992}',b'{"x":"\\ud800"}'):
            with self.assertRaises(Exception):parse(raw)
        self.assertEqual(jcs({"\U00010000":1,"\ue000":2}),'{"\U00010000":1,"\ue000":2}'.encode())
    def test_v1_signature_authorization_and_mutation(self):
        h=self.h();raw=h.make();h.trust.verify(raw,h.contract,"initiator","initiator")
        m=parse(raw);m["body"]["units"]=11
        with self.assertRaises(Exception):h.trust.verify(jcs(m),h.contract,"initiator","initiator")
        attacker=Identity("initiator","initiator");m.pop("signature")
        status,_=post(h.server.host,h.server.port,"/rdinp/intent",attacker.sign(m));self.assertEqual(status,403);self.assertFalse(h.authority.snapshot()["negotiations"])
        m=parse(raw);m["extra"]=1
        with self.assertRaises(Exception):h.contract.message(m)
    def test_v2_actual_four_phase_chain(self):
        h=self.h();result=h.client.run(h.server.host,h.server.port,"normal","intent-normal",10)
        self.assertEqual((result["status"],result["effectKnowledge"],result["confirmationComplete"]),("COMMITTED","COMMITTED",True));self.assertTrue(result["beforeDeadline"])
        snap=h.authority.snapshot();self.assertEqual(snap["negotiations"][0]["state"],"CONFIRMED");self.assertEqual(sum(x["event"]=="COMMIT" for x in snap["effects"]),1)
        self.assertEqual(set(h.client.state["winners"]),set(PHASES));self.assertTrue(any(e["event"]=="DURABLE_COMMIT_RETURN" and e["effectTx"] for e in h.trace.events))
    def test_v2_standalone_cli_real_dual_endpoint(self):
        result=subprocess.run([sys.executable,str(ROOT/"local_demo.py"),str(self.root/"standalone")],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        (self.root/"cli-execution.json").write_bytes(jcs({"exitCode":result.returncode,"stdout":result.stdout.decode(),"stderr":result.stderr.decode()}))
        self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)["status"],"COMMITTED")
    def test_v1_outcome_schema_semantics_and_timestamp_admission(self):
        h=self.h();_,reply=h.call(h.make());reply["body"]["token"]=""
        with self.assertRaises(Exception):h.contract.message(reply)
        with self.assertRaises(ValueError):Trust([h.i.pin(),h.i.pin()])
        h2=self.h(client_source=Manual(MAX-1))
        with self.assertRaises(ValueError):h2.client.run(h2.server.host,h2.server.port,"overflow","intent-overflow",10)
        self.assertIsNone(h2.client.state);self.assertFalse(h2.authority.snapshot()["negotiations"])
    def test_v2_actual_rejection_two_matching_decisions(self):
        h=self.h(capacity=5);r=h.client.run(h.server.host,h.server.port,"reject","intent-reject",10)
        self.assertEqual((r["status"],r["effectKnowledge"]),("REJECTED","NO_COMMIT_SENT"));self.assertEqual(len(h.client.state["winners"]),2);self.assertFalse(r["commitPossible"])
    def test_v3_illegal_first_replay_and_skipped_commit(self):
        h=self.h();s,a=h.call(h.make("INTENT_REPLAY"));self.assertEqual(a["body"]["code"],"ORDER");self.assertFalse(h.authority.snapshot()["negotiations"])
        d=h.reserve();s,a=h.call(h.make("COMMIT_INITIAL",decision=d));self.assertEqual(a["body"]["code"],"ORDER")
        h.call(h.make("INTENT_REPLAY",1));s,a=h.call(h.make("COMMIT_REPLAY",decision=d));self.assertEqual(a["body"]["code"],"ORDER");self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"RESERVED")
    def test_v3_stable_history_replay(self):
        h=self.h();d=h.prepared();_,a=h.call(h.make("COMMIT_INITIAL",decision=d));_,b=h.call(h.make("COMMIT_REPLAY",decision=d));self.assertEqual(a["body"],b["body"])
        _,old=h.call(h.make("INTENT_INITIAL",1));self.assertEqual(old["body"],d)
        _,again=h.call(h.make("COMMIT_INITIAL",1,decision=d));self.assertEqual(again["body"],a["body"])
    def test_v4_identical_attempt_replies_and_raw_conflict(self):
        h=self.h();raw=h.make();_,a=h.call(raw);_,b=h.call(raw);self.assertEqual(a["body"],b["body"])
        wire=json.dumps(parse(raw),indent=2).encode();self.assertEqual(sha(jcs(parse(wire))),sha(jcs(parse(raw))))
        _,bad=h.call(wire);self.assertEqual(bad["body"]["code"],"ATTEMPT_CONFLICT");self.assertEqual(len(h.authority.snapshot()["effects"]),1)
    def test_v4_nonce_and_business_identity(self):
        h=self.h();raw=h.make();h.call(raw);m=parse(raw);m.pop("signature");m["attempt"]=1;m["messageId"]=uuid.uuid4().hex
        _,a=h.call(h.i.sign(m));self.assertEqual(a["body"]["code"],"NONCE_CONFLICT")
        _,b=h.call(h.make(attempt=2,units=11));self.assertEqual(b["body"]["code"],"IDENTITY");self.assertEqual(h.authority.snapshot()["negotiations"][0]["units"],10)
    def test_v5_expired_intent_is_not_reject_no_renewal(self):
        clock=Manual();h=self.h(manual=clock);d=h.prepared();clock.set(d["leaseUntilNs"]-1);_,a=h.call(h.make("INTENT_REPLAY",1));self.assertEqual(a["body"],d)
        clock.set(d["leaseUntilNs"]);status,a=h.call(h.make("INTENT_REPLAY",2));self.assertEqual(status,410);self.assertFalse(a["body"]["authoritative"])
        _,receipt=h.call(h.make("COMMIT_INITIAL",decision=d));self.assertEqual(receipt["body"]["status"],"NOT_APPLIED")
    def test_v5_boot_change_and_same_boot_restart(self):
        clock=Manual();h=self.h(manual=clock);d=h.prepared();h.call(h.make("COMMIT_INITIAL",decision=d));h.reserve("tentative")
        h.authority.close()
        a=Authority(h.root/"authority.sqlite",h.contract,Clock("LOCAL-NONPRODUCTION-BOOT","server-monotonic",clock),Trace("responder",Clock("LOCAL-NONPRODUCTION-BOOT","server-monotonic",clock)))
        self.assertEqual({r["neg"]:r["state"] for r in a.snapshot()["negotiations"]},{"n1":"CONFIRMED","tentative":"RESERVED"});a.close()
        clock.set(1)
        with self.assertRaises(ClockError):Authority(h.root/"authority.sqlite",h.contract,Clock("LOCAL-NONPRODUCTION-BOOT","server-monotonic",clock),h.trace)
        a=Authority(h.root/"authority.sqlite",h.contract,Clock("NEW-BOOT","server-monotonic",clock),Trace("responder",Clock("NEW-BOOT","server-monotonic",clock)))
        self.assertEqual({r["neg"]:r["state"] for r in a.snapshot()["negotiations"]},{"n1":"CONFIRMED","tentative":"EXPIRED"});self.assertEqual(a.snapshot()["metadata"]["epoch"],1);a.close()
    def test_v5_clock_regression_stops_new_effects(self):
        clock=Manual();h=self.h(manual=clock);h.reserve();clock.set(0)
        _,a=h.call(h.make(neg="n2"));self.assertEqual(a["body"]["code"],"CLOCK");self.assertEqual(len(h.authority.snapshot()["negotiations"]),1)
    def test_v6_tail_guard_equality_and_safe_infeasible(self):
        clock=Manual();h=self.h(manual=clock);d=h.prepared();r=h.contract.policy["resourceRules"]
        clock.set(d["leaseUntilNs"]-r["commitTailBudgetNs"]-r["commitTailMarginNs"])
        _,a=h.call(h.make("COMMIT_INITIAL",decision=d));self.assertEqual(a["body"]["code"],"TAIL_GUARD");self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"RESERVED")
        c=example_contract();policy=copy.deepcopy(c.policy);policy["resourceRules"]["commitTailBudgetNs"]=c.plan["leaseNs"];t=copy.deepcopy(c.timing);t["policyProfileDigest"]=digest("POLICY",policy)
        with self.assertRaisesRegex(ValueError,"guardability"):Contract(c.plan_raw,policy,t)
    def test_v6_tail_overrun_preserves_effect_and_negative_evidence(self):
        clock=Manual();h=self.h(manual=clock,tail_hook=lambda:clock.set(20000000000));d=h.prepared();_,a=h.call(h.make("COMMIT_INITIAL",decision=d))
        self.assertEqual(a["body"]["status"],"COMMITTED");self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"CONFIRMED")
        self.assertTrue(any(e["event"]=="PREMISE_VIOLATION" and e["claim"]=="STRICT_TAIL" for e in h.trace.events))
    def test_v7_concurrent_capacity_and_admission_shrink(self):
        h=self.h(capacity=10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:decisions=list(pool.map(lambda i:h.reserve("race"+str(i),3),range(8)))
        self.assertEqual(sum(d["status"]=="RESERVED" for d in decisions),3)
        h.authority.set_admission(1);snap=h.authority.snapshot();u=sum(r["units"] for r in snap["negotiations"] if r["state"] in ("RESERVED","CONFIRMED"));self.assertEqual(u,9);self.assertLessEqual(u,snap["metadata"]["capacity"]);self.assertGreater(u,snap["metadata"]["admission"])
    def test_v7_concurrent_commit_at_most_once(self):
        h=self.h();d=h.prepared()
        raws=[h.make("COMMIT_INITIAL",i,decision=d) for i in range(4)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:replies=list(pool.map(h.call,raws))
        self.assertTrue(all(a[1]["body"]==replies[0][1]["body"] for a in replies));self.assertEqual(sum(e["event"]=="COMMIT" for e in h.authority.snapshot()["effects"]),1)
    def test_v8_old_attempt_wins_after_rto(self):
        def policy(m,k,b):return {"delay":0.09 if m["attempt"]==0 else 0.18} if m["phase"]=="INTENT_INITIAL" else {}
        h=self.h(policy=policy);r=h.client.run(h.server.host,h.server.port,"rto","intent-rto",10);h.client.drain();self.assertEqual(r["status"],"COMMITTED")
        sent=[e for e in h.ct.events if e["event"]=="SEND_ACTUAL" and e["phase"]=="INTENT_INITIAL"]
        self.assertGreaterEqual(len(sent),2);self.assertEqual(h.client.state["winners"]["INTENT_INITIAL"]["attempt"],0)
        for phase in PHASES:self.assertEqual(sum(e["event"]=="PHASE_WINNER_LATCH" and e["phase"]==phase for e in h.ct.events),1)
    def test_v8_latch_deadline_equality_fails_after_valid_verify(self):
        clock=Manual()
        h=self.h(client_source=clock,before_latch=lambda m,c:clock.set(2000000000))
        r=h.client.run(h.server.host,h.server.port,"equal","intent-equal",10)
        self.assertEqual(r["status"],"ASSUMPTION_FAILURE");self.assertFalse(h.client.state["winners"]);self.assertTrue(any(e["event"]=="VERIFY_DONE" for e in h.ct.events));self.assertTrue(any(e["event"]=="LATE_NO_LATCH" for e in h.ct.events))
    def test_v9_committed_response_loss_is_unknown_not_rejected(self):
        h=self.h(policy=lambda m,k,b:{"drop":m["phase"]=="COMMIT_INITIAL"})
        r=h.client.run(h.server.host,h.server.port,"lost","intent-lost",10);self.assertEqual((r["status"],r["effectKnowledge"]),("RECOVERY_REQUIRED","UNKNOWN"));self.assertTrue(r["commitPossible"])
        self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"CONFIRMED")
    def test_v9_first_success_receipt_survives_second_confirmation_loss(self):
        h=self.h(policy=lambda m,k,b:{"drop":m["phase"]=="COMMIT_REPLAY"})
        r=h.client.run(h.server.host,h.server.port,"known","intent-known",10);self.assertEqual((r["status"],r["effectKnowledge"],r["confirmationComplete"]),("RECOVERY_REQUIRED","COMMITTED",False))
    def test_v10_active_cleanup_without_followup_request(self):
        clock=Manual();h=self.h(manual=clock);d=h.reserve();clock.set(d["leaseUntilNs"])
        end=time.monotonic()+1
        while time.monotonic()<end and h.authority.snapshot()["negotiations"][0]["state"]=="RESERVED":time.sleep(0.01)
        self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"EXPIRED");self.assertTrue(any(e["event"]=="RELEASE_DONE" for e in h.trace.events))
    def test_v11_subprocess_durable_commit_crash_before_response(self):
        c=example_contract();i=Identity("initiator","initiator");r=Identity("authority","responder");pins=[i.pin(),r.pin()];trust=Trust(pins)
        private=r.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode("ascii")
        data={"plan":c.plan,"policy":c.policy,"timing":c.timing,"pins":pins,"privateKeyPem":private,"boot":"LOCAL-NONPRODUCTION-BOOT"}
        (self.root/"inputs.json").write_bytes(jcs({k:v for k,v in data.items() if k!="privateKeyPem"}))
        child=subprocess.Popen([sys.executable,str(ROOT/"crash_responder.py"),str(self.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            child.stdin.write(jcs(data)+b"\n");child.stdin.flush();child.stdin.close();ready=json.loads(child.stdout.readline())
            def send(phase,body):
                m=base_message(c,"INTENT" if phase.startswith("INTENT") else "COMMIT","crash","intent-crash",phase,0,"initiator","authority",body);raw=i.sign(m)
                return post(ready["host"],ready["port"],"/rdinp/intent" if m["kind"]=="INTENT" else "/rdinp/commit",raw)
            b={"units":10,"decisionDigest":"","epoch":0,"token":""};_,a=send("INTENT_INITIAL",b);d=trust.verify(a,c,"authority","responder")["body"];send("INTENT_REPLAY",b)
            with self.assertRaises(Exception):send("COMMIT_INITIAL",{"units":10,"decisionDigest":d["decisionDigest"],"epoch":d["epoch"],"token":d["token"]})
            self.assertEqual(child.wait(timeout=5),17)
            clock=Clock("LOCAL-NONPRODUCTION-BOOT","server-monotonic");trace=Trace("responder",clock,self.root/"restart.events.jsonl");a=Authority(self.root/"crash-authority.sqlite",c,clock,trace)
            snap=a.snapshot();self.assertEqual(snap["negotiations"][0]["state"],"CONFIRMED");self.assertEqual(json.loads(snap["negotiations"][0]["receipt"])["status"],"COMMITTED");a.close();(self.root/"restart-observation.json").write_bytes(jcs(snap))
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=5)
            (self.root/"child-exit.json").write_bytes(jcs({"exitCode":child.returncode,"stderr":child.stderr.read().decode("utf-8",errors="replace")}));child.stdout.close();child.stderr.close()
    def test_v12_client_recovery_no_new_timers_or_negotiation(self):
        h=self.h(policy=lambda m,k,b:{"drop":m["phase"]=="COMMIT_REPLAY"});r=h.client.run(h.server.host,h.server.port,"recover","intent-recover",10);h.client.drain()
        h.client.db.close();again=Initiator(h.root/"client.sqlite",h.contract,h.i,h.trust,h.cc,h.ct)
        self.assertEqual(again.recover_offline()["effectKnowledge"],"COMMITTED")
        with self.assertRaises(ValueError):again.run(h.server.host,h.server.port,"new-key","new-intent",10)
        again.db.close();h.client.db=sqlite3.connect(h.root/"client.sqlite")
    def client_crash(self,mode,code):
        h=self.h();private=h.i.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode("ascii")
        data={"plan":h.contract.plan,"policy":h.contract.policy,"timing":h.contract.timing,"pins":h.pins,"privateKeyPem":private,"mode":mode,"port":h.server.port}
        child=subprocess.run([sys.executable,str(ROOT/"crash_initiator.py"),str(h.root)],input=jcs(data)+b"\n",stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        (h.root/"child-client-exit.json").write_bytes(jcs({"mode":mode,"exitCode":child.returncode,"stdout":child.stdout.decode(),"stderr":child.stderr.decode()}));self.assertEqual(child.returncode,code)
        recovered=Initiator(h.root/"crash-client.sqlite",h.contract,h.i,h.trust,h.cc,h.ct)
        old_start=recovered.state["startNs"];result=recovered.recover_offline();self.assertEqual(recovered.state["startNs"],old_start);recovered.close()
        return h,result
    def test_v12_process_crash_writeahead_before_egress(self):
        h,r=self.client_crash("BEFORE_COMMIT_SEND",23)
        self.assertEqual((r["status"],r["effectKnowledge"],r["commitPossible"]),("RECOVERY_REQUIRED","UNKNOWN",True))
        self.assertFalse(any(e["event"]=="COMMIT" for e in h.authority.snapshot()["effects"]))
    def test_v12_process_crash_preserves_first_receipt_knowledge(self):
        h,r=self.client_crash("AFTER_FIRST_RECEIPT",24)
        self.assertEqual((r["status"],r["effectKnowledge"]),("RECOVERY_REQUIRED","COMMITTED"));self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"CONFIRMED")
    def test_v4_request_identity_and_response_digest_cannot_transplant(self):
        h=self.h();raw=h.make();_,reply=h.call(raw);m=parse(raw)
        reply.pop("signature");reply["negotiationId"]="foreign"
        forged=h.r.sign(reply)
        h.client.state={"decision":None}
        with self.assertRaisesRegex(ValueError,"correlation"):h.client.verify_response(forged,m,raw)
        h.client.state=None
    def test_v5_stale_boot_instance_is_fenced(self):
        clock=Manual();h=self.h(manual=clock);h.reserve();h.authority.close()
        newer=Clock("NEW-BOOT","server-monotonic",clock);a=Authority(h.root/"authority.sqlite",h.contract,newer,Trace("responder",newer));a.close()
        _,reply=h.call(h.make(neg="n2"));self.assertEqual(reply["body"]["code"],"CLOCK");self.assertEqual(len(h.authority.snapshot()["negotiations"]),1)
    def test_v6_invalid_commit_does_not_release_expired_reservation(self):
        clock=Manual();h=self.h(manual=clock);d=h.prepared();h.authority.close();clock.set(d["leaseUntilNs"])
        bad=copy.deepcopy(d);bad["token"]="wrong";_,reply=h.call(h.make("COMMIT_INITIAL",decision=bad));self.assertEqual(reply["body"]["code"],"IDENTITY")
        self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"RESERVED")
    def test_v4_maximum_units_capacity_reject_not_arithmetic_failure(self):
        h=self.h();h.reserve();d=h.reserve("huge",MAX);self.assertEqual(d["status"],"REJECTED")
    def test_v8_publication_overrun_reported_not_hidden(self):
        clock=Manual();h=self.h(client_source=clock);h.client.state={"negotiationId":"publication","terminal":None,"effectKnowledge":"COMMITTED","commitPossible":True}
        result=h.client.terminal("COMMITTED",True,clock.value)
        self.assertFalse(result["beforeDeadline"]);self.assertEqual(result["status"],"RECOVERY_REQUIRED")
        self.assertEqual(h.client.publications.get_nowait()["effectKnowledge"],"COMMITTED");self.assertTrue(any(e["event"]=="PREMISE_VIOLATION" for e in h.ct.events))
    def test_v8_preempted_store_cannot_latch_after_deadline(self):
        clock=Manual();h=self.h(client_source=clock,after_latch_store=lambda m,c:clock.set(2000000000))
        r=h.client.run(h.server.host,h.server.port,"post-check","intent-post-check",10)
        self.assertEqual(r["status"],"ASSUMPTION_FAILURE");self.assertFalse(h.client.state["winners"]);self.assertTrue(any(e["event"]=="LATCH_ROLLED_BACK_CUTOFF" for e in h.ct.events))
    def test_v9_verified_receipt_keeps_knowledge_even_if_latch_late(self):
        clock=Manual()
        def delay(m,c):
            if m["phase"]=="COMMIT_INITIAL":clock.set(4000000000)
        h=self.h(client_source=clock,after_latch_store=delay);r=h.client.run(h.server.host,h.server.port,"late-receipt","intent-late-receipt",10)
        self.assertEqual((r["status"],r["effectKnowledge"]),("RECOVERY_REQUIRED","COMMITTED"));self.assertNotIn("COMMIT_INITIAL",h.client.state["winners"])
    def test_v9_commit_exception_after_persistence_is_not_not_applied(self):
        h=self.h();d=h.prepared();connect=h.authority.connect
        class Ambiguous:
            def __init__(self,db):self.db=db
            def __getattr__(self,name):return getattr(self.db,name)
            def commit(self):self.db.commit();raise RuntimeError("test commit return failure after durable success")
        h.authority.connect=lambda:Ambiguous(connect())
        status,reply=h.call(h.make("COMMIT_INITIAL",decision=d));self.assertEqual(status,503);self.assertEqual(reply["body"],{"code":"INTERNAL_UNKNOWN","authoritative":False});self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"CONFIRMED")
    def test_v5_client_clock_failure_publishes_without_fake_time(self):
        clock=Manual();h=self.h(client_source=clock,before_latch=lambda m,c:clock.set(0))
        r=h.client.run(h.server.host,h.server.port,"clock-failure","intent-clock-failure",10)
        self.assertEqual(r["status"],"ASSUMPTION_FAILURE");self.assertIsNone(r["publishedNs"]);self.assertFalse(r["beforeDeadline"])
    def test_v10_cleanup_delay_is_explicit_premise_failure(self):
        clock=Manual();h=self.h(manual=clock);d=h.reserve();h.authority.close();clock.set(d["leaseUntilNs"]+100000001);h.authority.cleanup()
        self.assertEqual(h.authority.snapshot()["negotiations"][0]["state"],"EXPIRED")
        self.assertTrue({"CLEANUP","CLEANUP_DISPATCH"}.issubset({e.get("claim") for e in h.trace.events if e["event"]=="PREMISE_VIOLATION"}))
    def test_v9_both_direction_loss_local_transport_sink(self):
        h=self.h(policy=lambda m,k,b:{"drop":m["phase"]=="INTENT_INITIAL" and m["attempt"]==1})
        def transport(host,port,path,raw,timeout=2):
            m=parse(raw)
            if m["phase"]=="INTENT_INITIAL" and m["attempt"] in (0,2):
                h.ct.emit("TEST_REQUEST_SUPPRESSED",m,rawSha256=sha(raw));raise OSError("local test sink, no packet fault injection")
            return post(host,port,path,raw,timeout)
        with patch("initiator.post",side_effect=transport):
            r=h.client.run(h.server.host,h.server.port,"two-way","intent-two-way",10);h.client.drain()
        self.assertEqual(r["status"],"COMMITTED");self.assertEqual(h.client.state["winners"]["INTENT_INITIAL"]["attempt"],3)
        self.assertEqual(sum(e["event"]=="TEST_REQUEST_SUPPRESSED" for e in h.ct.events),2)
    def test_v13_finite_bidirectional_loss_bound(self):
        def bounded(bits,b):
            run=0
            for bit in bits:
                run=run+1 if bit else 0
                if run>b:return False
            return True
        checked_cases=0
        for bq in range(3):
            for br in range(3):
                k=(bq+1)*(br+1)
                for req in itertools.product((0,1),repeat=k):
                    if not bounded(req,bq):continue
                    arrivals=k-sum(req)
                    for res in itertools.product((0,1),repeat=arrivals):
                        if not bounded(res,br):continue
                        self.assertTrue(any(x==0 for x in res));checked_cases+=1
        (self.root/"finite-model.json").write_bytes(jcs({"cases":checked_cases,"scope":"Bq,Br<=2; no duplication; response bits indexed only on delivered requests","result":"PASS","proof":False}))


if __name__=="__main__":unittest.main()

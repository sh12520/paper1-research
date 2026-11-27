"""Persistent local initiator with non-retiring retry, verified unique phase latch."""
import copy
import json
import queue
import re
import sqlite3
import threading
from contracts import PHASES, checked, jcs, sha
from crypto import base_message, outcome_digest, b64
from endpoint import post
from events import ClockError


class Initiator:
    def __init__(self,path,contract,identity,trust,clock,trace,authority="authority",before_latch=None,after_latch_store=None,after_initial_persist=None):
        if identity.role!="initiator" or trust.pins.get(identity.kid,(None,None))[0]!=identity.pin():raise ValueError("initiator identity/pin")
        self.path=str(path);self.contract=contract;self.identity=identity;self.trust=trust;self.clock=clock;self.trace=trace;self.authority=authority;self.before_latch=before_latch
        self.after_latch_store=after_latch_store
        self.after_initial_persist=after_initial_persist
        self.cv=threading.Condition(threading.RLock());self.active_phase=None;self.winners={};self.workers=[];self.conflict=False
        self.controller_fault=None
        self.publications=queue.Queue(maxsize=1)
        self.db=sqlite3.connect(self.path,check_same_thread=False,isolation_level=None);self.db.execute("PRAGMA synchronous=FULL");self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("CREATE TABLE IF NOT EXISTS client(id INTEGER PRIMARY KEY CHECK(id=1), state TEXT)")
        saved=self.db.execute("SELECT state FROM client WHERE id=1").fetchone();self.state=json.loads(saved[0]) if saved else None
        if self.state and (self.state["contract"],self.state["principal"],self.state["authority"],self.state["trust"])!=(contract.digest,identity.principal,authority,trust.digest):raise ValueError("client config mismatch")
    def persist(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:self.db.execute("INSERT OR REPLACE INTO client VALUES(1,?)",(jcs(self.state).decode(),));self.db.commit()
        except Exception:self.db.rollback();raise
    def request(self,phase,attempt,body):
        m=base_message(self.contract,"INTENT" if phase.startswith("INTENT") else "COMMIT",self.state["negotiationId"],self.state["intentId"],phase,attempt,self.identity.principal,self.authority,body)
        return self.identity.sign(m)
    def fail_controller(self,code,request=None):
        """Sticky local control failure; caller may already hold the serializer."""
        with self.cv:
            if self.state is not None and self.state["terminal"] is None:
                self.controller_fault=self.controller_fault or code
                self.state["controllerFault"]=self.controller_fault
                # No provisional winner is ever installed in shared/persistent state.
                try:self.persist()
                finally:self.cv.notify_all()
                self.trace.emit("CONTROLLER_FAULT",request,code=self.controller_fault)
    def verify_response(self,raw,request,request_raw):
        m=self.trust.verify(raw,self.contract,self.authority,"responder")
        for k in ("negotiationId","intentId","phase","attempt","timingContractDigest"):
            if m[k]!=request[k]:raise ValueError("response correlation")
        if m["recipient"]!=self.identity.principal or m["requestRawSha256"]!=sha(request_raw) or m["requestJcsSha256"]!=sha(jcs(request)):raise ValueError("request hash/recipient")
        if m["kind"]=="PROBLEM":return m
        b=m["body"]
        if b["units"]!=request["body"]["units"]:raise ValueError("units mismatch")
        if m["kind"]=="DECISION":
            if outcome_digest("DECISION",request,b)!=b["decisionDigest"]:raise ValueError("decision digest")
        else:
            d=self.state["decision"]
            if not d or any(b[k]!=d[k] for k in ("decisionDigest","decisionId","units","epoch","token","leaseUntilNs")):raise ValueError("receipt decision binding")
            if outcome_digest("RECEIPT",request,b)!=b["receiptDigest"]:raise ValueError("receipt digest")
        return m

    def worker(self,host,port,raw,cutoff):
        from contracts import parse
        request=parse(raw);phase=request["phase"]
        try:
            with self.cv:
                if self.controller_fault or self.state["terminal"] is not None:return
                now=self.clock.now()
                if now>=cutoff:
                    self.trace.emit("SEND_SKIPPED_CUTOFF",request,ns=now);return
                self.trace.emit("SEND_ACTUAL",request,ns=now,rawSha256=sha(raw),rawBase64=b64(raw))
            status,answer=post(host,port,"/rdinp/intent" if request["kind"]=="INTENT" else "/rdinp/commit",raw,max(0.05,(cutoff-now)/1000000000))
            received=self.clock.now();self.trace.emit("RECEIVE",request,ns=received,rawSha256=sha(answer),requestRawSha256=sha(raw),rawBase64=b64(answer),httpStatus=status)
            candidate=self.verify_response(answer,request,raw)
            self.trace.emit("VERIFY_DONE",request,rawSha256=sha(answer),requestRawSha256=sha(raw))
            if candidate["kind"]=="PROBLEM":
                self.trace.emit("NON_AUTHORITATIVE_PROBLEM",request,code=candidate["body"]["code"]);return
            if status!=200:raise ValueError("business reply on error status")
            if self.before_latch:self.before_latch(request,candidate)
            with self.cv:
                now=self.clock.now()
                if self.state["terminal"] is not None:
                    self.trace.emit("LATE_NO_LATCH",request,ns=now,rawSha256=sha(answer));return
                prior=self.state["decision"] if candidate["kind"]=="DECISION" else self.state["receipt"]
                if prior is not None and prior!=candidate["body"]:
                    self.conflict=True;self.trace.emit("CONFLICTING_EVIDENCE",request,ns=now,rawSha256=sha(answer));self.cv.notify_all();return
                # Effect evidence is independent of whether this response can win a phase.
                if candidate["kind"]=="RECEIPT":
                    self.state["receipt"]=candidate["body"]
                    self.state["effectKnowledge"]="COMMITTED" if candidate["body"]["status"]=="COMMITTED" else "NOT_APPLIED"
                    # Retain authenticated effect knowledge BEFORE any latch failure.
                    self.persist()
                if self.controller_fault:return
                if phase!=self.active_phase or now>=cutoff:
                    if candidate["kind"]=="RECEIPT":self.persist()
                    self.trace.emit("LATE_NO_LATCH",request,ns=now,rawSha256=sha(answer));return
                if phase in self.winners:
                    self.trace.emit("LOSING_VALID_REPLY",request,ns=now,rawSha256=sha(answer));return
                before=copy.deepcopy(self.state)
                draft=copy.deepcopy(before)
                if candidate["kind"]=="DECISION":draft["decision"]=candidate["body"]
                draft["winners"][phase]={"responseRawSha256":sha(answer),"requestRawSha256":sha(raw),"attempt":request["attempt"],"latchNs":now}
                try:
                    if self.after_latch_store:self.after_latch_store(request,candidate)
                    upper=self.clock.now()
                except ClockError:
                    self.trace.emit("PROVISIONAL_DISCARDED",request,reason="CLOCK")
                    self.fail_controller("CLOCK",request);return
                except Exception:
                    self.fail_controller("PROVISIONAL_ERROR",request);raise
                if upper>=cutoff:
                    self.trace.emit("LATCH_ROLLED_BACK_CUTOFF",request,ns=upper,rawSha256=sha(answer),cutoffNs=cutoff);self.cv.notify_all();return
                draft["winners"][phase]["latchNs"]=upper
                self.trace.emit("PHASE_WINNER_LATCH",request,ns=upper,rawSha256=sha(answer),requestRawSha256=sha(raw),cutoffNs=cutoff)
                self.state=draft
                try:self.persist()
                except Exception:
                    self.state=before
                    self.fail_controller("WINNER_PERSIST_ERROR",request);raise
                # Main loop can consume only a successfully validated, durable winner.
                self.winners[phase]=candidate
                self.trace.emit("PHASE_WINNER_PERSISTED",request)
                self.cv.notify_all()
        except ClockError:
            self.fail_controller("CLOCK",request)
        except Exception as e:
            self.trace.emit("REQUEST_FAILED",request,detail=type(e).__name__)
            with self.cv:self.cv.notify_all()

    def terminal(self,status,complete=False,deadline=None):
        with self.cv:
            if self.state["terminal"] is not None:return copy.deepcopy(self.state["terminal"])
            try:now=self.clock.now()
            except ClockError:now=None
            if complete and (now is None or deadline is not None and now>=deadline):
                status="RECOVERY_REQUIRED" if self.state["commitPossible"] else "ASSUMPTION_FAILURE";complete=False
            result={"status":status,"effectKnowledge":self.state["effectKnowledge"],"confirmationComplete":complete,"commitPossible":self.state["commitPossible"],"conflictingEvidence":self.conflict,"publicationDeadlineNs":deadline}
            self.state["terminal"]=result;self.active_phase=None;self.persist();self.trace.emit("TERMINAL_PERSISTED",negotiationId=self.state["negotiationId"],result=result)
            # Publication is the observable local queue insertion, not a pre-write trace sample.
            self.publications.put_nowait(copy.deepcopy(result))
            try:published=self.clock.now()
            except ClockError:published=None
            self.trace.emit("TERMINAL_PUBLISHED",ns=published,negotiationId=self.state["negotiationId"],result=result)
            result=copy.deepcopy(result);result["publishedNs"]=published;result["beforeDeadline"]=deadline is not None and published is not None and published<deadline
            if deadline is not None and not result["beforeDeadline"]:self.trace.emit("PREMISE_VIOLATION",claim="TERMINAL_PUBLICATION",negotiationId=self.state["negotiationId"])
            self.cv.notify_all();return result

    def run(self,host,port,negotiation,intent,units):
        try:return self._run(host,port,negotiation,intent,units)
        except ClockError:
            if self.state is None:raise
            return self.terminal("RECOVERY_REQUIRED" if self.state["commitPossible"] else "ASSUMPTION_FAILURE",False,None)

    def _run(self,host,port,negotiation,intent,units):
        if self.state is not None:raise ValueError("existing client state: offline recovery only")
        if any(type(v) is not str or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}",v) is None for v in (negotiation,intent)):raise ValueError("identity grammar")
        if checked(units)==0:raise ValueError("units must be positive")
        start=self.clock.now();p=self.contract.plan
        final=checked(start+p["terminalDeadlineMs"]*1000000)
        checked(start+p["rejectDeadlineMs"]*1000000)
        self.state={"contract":self.contract.digest,"trust":self.trust.digest,"principal":self.identity.principal,"authority":self.authority,"negotiationId":negotiation,"intentId":intent,"units":units,"startNs":start,"boot":self.clock.boot,"clockId":self.clock.clock_id,"commitPossible":False,"effectKnowledge":"NO_COMMIT_SENT","decision":None,"receipt":None,"winners":{},"terminal":None,"controllerFault":None,"initialReadyNs":None}
        self.persist()
        if self.after_initial_persist:self.after_initial_persist()
        self.trace.emit("NEGOTIATION_START",ns=start,negotiationId=negotiation,contractDigest=self.contract.digest)
        for i,phase in enumerate(PHASES):
            cutoff=checked(start+self.contract.cutoff_ms(i)*1000000);spec=p["phases"][i]
            with self.cv:
                if self.controller_fault:raise ClockError("sticky controller failure: "+self.controller_fault)
                self.active_phase=phase
                if i==2:
                    self.state["commitPossible"]=True;self.state["effectKnowledge"]="UNKNOWN";self.persist();self.trace.emit("COMMIT_POSSIBLE_PERSISTED",negotiationId=negotiation)
                phase_start=self.clock.now()
                if i==0:
                    self.state["initialReadyNs"]=phase_start
                    elapsed=phase_start-start;budget=p["initialBudgetMs"]*1000000
                    self.trace.emit("INITIAL_READY",ns=phase_start,negotiationId=negotiation,startNs=start,initialBudgetNs=budget,initialElapsedNs=elapsed)
                    if elapsed>budget:
                        self.trace.emit("PREMISE_VIOLATION",claim="INITIAL_BUDGET",negotiationId=negotiation)
                        return self.terminal("ASSUMPTION_FAILURE",False,final)
                decision=self.state["decision"]
                body={"units":units,"decisionDigest":"" if i<2 else decision["decisionDigest"],"epoch":0 if i<2 else decision["epoch"],"token":"" if i<2 else decision["token"]}
                sent=0
                while phase not in self.winners and not self.conflict and not self.controller_fault:
                    now=self.clock.now()
                    if now>=cutoff:
                        self.trace.emit("TIMEOUT_DUE",negotiationId=negotiation,phase=phase,ns=now,dueNs=cutoff)
                        self.trace.emit("TIMEOUT_DISPATCH",negotiationId=negotiation,phase=phase,ns=now);break
                    due=checked(phase_start+sent*spec["retryMs"]*1000000)
                    if sent<spec["attempts"] and now>=due:
                        raw=self.request(phase,sent,body)
                        self.trace.emit("SEND_SCHEDULED",negotiationId=negotiation,phase=phase,attempt=sent,scheduledNs=due,rawSha256=sha(raw))
                        thread=threading.Thread(target=self.worker,args=(host,port,raw,cutoff),daemon=True);self.workers.append(thread);thread.start();sent+=1
                    wait_ns=cutoff-self.clock.now()
                    if sent<spec["attempts"]:wait_ns=min(wait_ns,phase_start+sent*spec["retryMs"]*1000000-self.clock.now())
                    self.cv.wait(max(0,min(wait_ns/1000000000,0.05)))
                if self.controller_fault:raise ClockError("sticky controller failure: "+self.controller_fault)
                if phase not in self.winners or self.conflict:
                    status="RECOVERY_REQUIRED" if self.state["commitPossible"] or self.conflict else "ASSUMPTION_FAILURE"
                    return self.terminal(status,False,final)
            if i==1 and self.state["decision"]["status"]=="REJECTED":return self.terminal("REJECTED",True,checked(start+p["rejectDeadlineMs"]*1000000))
        status="COMMITTED" if self.state["receipt"]["status"]=="COMMITTED" else "NOT_APPLIED"
        return self.terminal(status,True,final)

    def recover_offline(self):
        if self.state is None:raise ValueError("no state")
        if self.state["terminal"] is not None:
            result=copy.deepcopy(self.state["terminal"]);result["publicationObservationAvailable"]=False;return result
        return self.terminal("RECOVERY_REQUIRED" if self.state["commitPossible"] else "ASSUMPTION_FAILURE",False,None)
    def drain(self):
        for t in self.workers:t.join(2)
    def close(self):self.drain();self.db.close()

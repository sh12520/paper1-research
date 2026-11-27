"""Single SQLite logical quota authority. No physical controller or online recovery."""
import copy
import json
import sqlite3
import threading
import uuid
from contracts import checked, jcs, sha
from crypto import outcome_digest
from events import ClockError


class Problem(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)
class CommitUnknown(Exception):pass


class Authority:
    def __init__(self,path,contract,clock,trace,capacity=100,admission=None,authority_id="authority",initiator_id="initiator",tail_hook=None):
        self.path=str(path);self.contract=contract;self.clock=clock;self.trace=trace;self.authority_id=authority_id;self.initiator_id=initiator_id
        self.lock=threading.RLock();self.tail_hook=tail_hook;self.stop=threading.Event();self.cleaner=None
        self.current_tx=uuid.uuid4().hex
        admission=capacity if admission is None else admission
        if type(capacity) is not int or type(admission) is not int or not 0<=admission<=capacity:raise ValueError("quota")
        checked(capacity)
        with self.lock:
            db=self.connect()
            db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(id INTEGER PRIMARY KEY CHECK(id=1), revision TEXT, config TEXT, authority TEXT, initiator TEXT, boot TEXT, clock TEXT, capacity INTEGER, admission INTEGER, epoch INTEGER, last_ns INTEGER);
            CREATE TABLE IF NOT EXISTS negotiations(neg TEXT PRIMARY KEY,intent TEXT,principal TEXT,units INTEGER,state TEXT,lease INTEGER,epoch INTEGER,token TEXT,decision TEXT,receipt TEXT,intent_replayed INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS attempts(neg TEXT,phase TEXT,attempt INTEGER,raw TEXT,jcs TEXT,message TEXT UNIQUE,nonce TEXT UNIQUE,PRIMARY KEY(neg,phase,attempt));
            CREATE TABLE IF NOT EXISTS effects(tx TEXT PRIMARY KEY,neg TEXT,event TEXT,units INTEGER,sample_ns INTEGER,boot TEXT,transaction_id TEXT);
            CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,neg TEXT,phase TEXT,attempt INTEGER,request_raw TEXT,request_jcs TEXT,reply_kind TEXT,body_jcs TEXT,boot TEXT,arrival TEXT);
            """)
            db.execute("BEGIN IMMEDIATE")
            m=db.execute("SELECT * FROM metadata").fetchone()
            now=self.clock.now()
            if m is None:
                db.execute("INSERT INTO metadata VALUES(1,?,?,?,?,?,?,?,?,?,?)",(contract.plan["revision"],contract.digest,authority_id,initiator_id,clock.boot,clock.clock_id,capacity,admission,0,now))
            else:
                if (m["revision"],m["config"],m["authority"],m["initiator"],m["capacity"],m["clock"])!=(contract.plan["revision"],contract.digest,authority_id,initiator_id,capacity,clock.clock_id):
                    db.rollback();db.close();raise ValueError("no implicit DB/config migration")
                if m["boot"]==clock.boot and now<m["last_ns"]:
                    db.rollback();db.close();raise ClockError("persisted same-boot clock fence")
                if m["boot"]!=clock.boot:
                    for row in db.execute("SELECT * FROM negotiations WHERE state='RESERVED'").fetchall():
                        db.execute("UPDATE negotiations SET state='EXPIRED' WHERE neg=?",(row["neg"],))
                        self.journal(db,row["neg"],"BOOT_EXPIRE",row["units"],now)
                    db.execute("UPDATE metadata SET boot=?,epoch=? WHERE id=1",(clock.boot,checked(m["epoch"]+1)))
                db.execute("UPDATE metadata SET last_ns=? WHERE id=1",(now,))
            db.commit();done=self.clock.now();db.close()
            self.trace.emit("BOOT_READY",ns=done,transactionId=self.current_tx)

    def connect(self):
        db=sqlite3.connect(self.path,timeout=1.0,isolation_level=None);db.row_factory=sqlite3.Row
        db.execute("PRAGMA synchronous=FULL");db.execute("PRAGMA journal_mode=DELETE")
        return db
    def journal(self,db,neg,event,units,now):
        tx=uuid.uuid4().hex
        db.execute("INSERT INTO effects VALUES(?,?,?,?,?,?,?)",(tx,neg,event,units,now,self.clock.boot,self.current_tx));return tx
    def snapshot(self):
        with self.lock:
            db=self.connect()
            out={"metadata":dict(db.execute("SELECT * FROM metadata").fetchone()),"negotiations":[dict(r) for r in db.execute("SELECT * FROM negotiations ORDER BY neg")],"effects":[dict(r) for r in db.execute("SELECT * FROM effects ORDER BY rowid")],"attempts":[dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY rowid")],"transactions":[dict(r) for r in db.execute("SELECT * FROM transactions ORDER BY rowid")]}
            db.close();return out
    def set_admission(self,q):
        with self.lock:
            db=self.connect();db.execute("BEGIN IMMEDIATE");p=db.execute("SELECT capacity FROM metadata").fetchone()[0]
            if type(q) is not int or not 0<=q<=p:db.rollback();db.close();raise ValueError("quota")
            db.execute("UPDATE metadata SET admission=?",(q,));db.commit();db.close()
    def register(self,db,m,raw):
        key=(m["negotiationId"],m["phase"],m["attempt"])
        old=db.execute("SELECT * FROM attempts WHERE neg=? AND phase=? AND attempt=?",key).fetchone()
        if old:
            if (old["raw"],old["jcs"],old["message"],old["nonce"])!=(sha(raw),sha(jcs(m)),m["messageId"],m["nonce"]):raise Problem("ATTEMPT_CONFLICT")
        else:
            try:db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?,?)",(*key,sha(raw),sha(jcs(m)),m["messageId"],m["nonce"]))
            except sqlite3.IntegrityError:raise Problem("NONCE_CONFLICT")
    def process(self,m,raw,arrival_id=None):
        with self.lock:
            db=self.connect();commit_info=None;self.current_tx=uuid.uuid4().hex
            try:
                db.execute("BEGIN IMMEDIATE");now=self.clock.now()
                fence=db.execute("SELECT last_ns,boot,clock FROM metadata").fetchone()
                if now<fence["last_ns"] or (fence["boot"],fence["clock"])!=(self.clock.boot,self.clock.clock_id):raise ClockError("persistent clock/boot fence")
                if m["sender"]!=self.initiator_id or m["recipient"]!=self.authority_id:raise Problem("IDENTITY")
                self.register(db,m,raw)
                try:kind,body,commit_info=self.business(db,m,now)
                except Problem as e:kind,body="PROBLEM",{"code":e.code,"authoritative":False}
                db.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?)",(self.current_tx,m["negotiationId"],m["phase"],m["attempt"],sha(raw),sha(jcs(m)),kind,jcs(body).decode(),self.clock.boot,arrival_id))
                db.execute("UPDATE metadata SET last_ns=? WHERE id=1",(self.clock.now(),))
                try:db.commit()
                except Exception as e:raise CommitUnknown(str(e)) from e
                try:done=self.clock.now()
                except ClockError:done=None
                self.trace.emit("DURABLE_COMMIT_RETURN",m,ns=done,rawSha256=sha(raw),effectTx=commit_info[2] if commit_info else None,transactionId=self.current_tx,arrivalId=arrival_id)
                if commit_info:
                    check,expiry,tx=commit_info;budget=self.contract.policy["resourceRules"]["commitTailBudgetNs"]
                    if done is None or done>=expiry or done-check>budget:
                        self.trace.emit("PREMISE_VIOLATION",m,ns=done,claim="STRICT_TAIL",finalCheckNs=check,leaseUntilNs=expiry,tailBudgetNs=budget,effectTx=tx)
                return kind,body
            except Problem as e:
                db.rollback();return "PROBLEM",{"code":e.code,"authoritative":False}
            except ClockError:
                db.rollback();return "PROBLEM",{"code":"CLOCK","authoritative":False}
            finally:db.close()

    def business(self,db,m,now):
        neg=m["negotiationId"];b=m["body"];phase=m["phase"]
        row=db.execute("SELECT * FROM negotiations WHERE neg=?",(neg,)).fetchone()
        if row and (row["intent"],row["principal"],row["units"])!=(m["intentId"],m["sender"],b["units"]):raise Problem("IDENTITY")
        if m["kind"]=="COMMIT":
            if row is None:raise Problem("ORDER")
            decision=json.loads(row["decision"])
            if (b["decisionDigest"],b["epoch"],b["token"])!=(decision["decisionDigest"],decision["epoch"],decision["token"]):raise Problem("IDENTITY")
            if row["receipt"]:return "RECEIPT",json.loads(row["receipt"]),None
            if phase!="COMMIT_INITIAL" or not row["intent_replayed"] or row["state"] not in ("RESERVED","EXPIRED"):raise Problem("ORDER")
        if row and row["state"]=="RESERVED" and now>=row["lease"]:
            db.execute("UPDATE negotiations SET state='EXPIRED' WHERE neg=?",(neg,));self.journal(db,neg,"EXPIRE",row["units"],now)
            row=db.execute("SELECT * FROM negotiations WHERE neg=?",(neg,)).fetchone()
        if m["kind"]=="INTENT":
            if row is None:
                if phase!="INTENT_INITIAL":raise Problem("ORDER")
                meta=db.execute("SELECT * FROM metadata").fetchone();u=db.execute("SELECT COALESCE(SUM(units),0) FROM negotiations WHERE state IN ('RESERVED','CONFIRMED')").fetchone()[0]
                admitted=b["units"]<=max(0,meta["admission"]-u)
                state="RESERVED" if admitted else "REJECTED";lease=checked(now+self.contract.plan["leaseNs"]) if admitted else 0
                d={"status":state,"decisionId":uuid.uuid4().hex,"units":b["units"],"epoch":meta["epoch"],"token":uuid.uuid4().hex if admitted else "","leaseUntilNs":lease,"reason":"ADMITTED" if admitted else "CAPACITY","decisionDigest":"","receiptDigest":""}
                d["decisionDigest"]=outcome_digest("DECISION",m,d)
                db.execute("INSERT INTO negotiations VALUES(?,?,?,?,?,?,?,?,?,?,0)",(neg,m["intentId"],m["sender"],b["units"],state,lease,meta["epoch"],d["token"],jcs(d).decode(),None))
                self.journal(db,neg,"RESERVE" if admitted else "REJECT",b["units"],now)
                self.trace.emit("LEASE_ANCHOR",m,ns=now,leaseUntilNs=lease)
                return "DECISION",d,None
            if row["state"]=="EXPIRED":raise Problem("EXPIRED")
            if phase=="INTENT_REPLAY":db.execute("UPDATE negotiations SET intent_replayed=1 WHERE neg=?",(neg,))
            return "DECISION",json.loads(row["decision"]),None
        decision=json.loads(row["decision"])
        d=copy.deepcopy(decision);d["status"]="NOT_APPLIED" if row["state"]=="EXPIRED" else "COMMITTED";d["reason"]="EXPIRED" if row["state"]=="EXPIRED" else "APPLIED"
        commit_info=None
        if row["state"]=="RESERVED":
            check=self.clock.now();r=self.contract.policy["resourceRules"]
            self.trace.emit("FINAL_COMMIT_CHECK",m,ns=check,leaseUntilNs=row["lease"],tailBudgetNs=r["commitTailBudgetNs"],tailMarginNs=r["commitTailMarginNs"])
            if checked(check+r["commitTailBudgetNs"]+r["commitTailMarginNs"])>=row["lease"]:raise Problem("TAIL_GUARD")
        d["receiptDigest"]=outcome_digest("RECEIPT",m,d)
        db.execute("UPDATE negotiations SET state=?,receipt=? WHERE neg=?",("CONFIRMED" if d["status"]=="COMMITTED" else "EXPIRED",jcs(d).decode(),neg))
        tx=self.journal(db,neg,"COMMIT" if d["status"]=="COMMITTED" else "NOT_APPLIED",row["units"],self.clock.now())
        if d["status"]=="COMMITTED":
            commit_info=(check,row["lease"],tx)
            if self.tail_hook:self.tail_hook()
        return "RECEIPT",d,commit_info

    def cleanup(self):
        with self.lock:
            db=self.connect();self.current_tx=uuid.uuid4().hex
            try:
                db.execute("BEGIN IMMEDIATE");now=self.clock.now()
                fence=db.execute("SELECT last_ns,boot,clock FROM metadata").fetchone()
                if now<fence["last_ns"] or (fence["boot"],fence["clock"])!=(self.clock.boot,self.clock.clock_id):raise ClockError("persistent clock/boot fence")
                rows=db.execute("SELECT * FROM negotiations WHERE state='RESERVED' AND lease<=?",(now,)).fetchall()
                effects=[]
                for r in rows:
                    db.execute("UPDATE negotiations SET state='EXPIRED' WHERE neg=?",(r["neg"],));effects.append(self.journal(db,r["neg"],"CLEANUP",r["units"],now))
                db.execute("UPDATE metadata SET last_ns=? WHERE id=1",(self.clock.now(),));db.commit();done=self.clock.now()
                for r,effect in zip(rows,effects):
                    self.trace.emit("RELEASE_DONE",ns=done,negotiationId=r["neg"],dispatchNs=now,leaseUntilNs=r["lease"],effectTx=effect,transactionId=self.current_tx)
                    rules=self.contract.policy["resourceRules"]
                    if now-r["lease"]>rules["cleanupDispatchBudgetMs"]*1000000:self.trace.emit("PREMISE_VIOLATION",ns=done,claim="CLEANUP_DISPATCH",negotiationId=r["neg"])
                    if done-now>rules["cleanupCompletionBudgetMs"]*1000000:self.trace.emit("PREMISE_VIOLATION",ns=done,claim="CLEANUP_COMPLETION",negotiationId=r["neg"])
                    if done-r["lease"]>self.contract.plan["cleanupBudgetMs"]*1000000:self.trace.emit("PREMISE_VIOLATION",ns=done,claim="CLEANUP",negotiationId=r["neg"])
                return len(rows)
            finally:db.close()
    def start_cleanup(self):
        if self.cleaner:return
        period=self.contract.policy["resourceRules"]["cleanupDispatchBudgetMs"]/2000
        def run():
            while not self.stop.wait(period):
                try:self.cleanup()
                except Exception as e:self.trace.emit("CLEANUP_ERROR",detail=type(e).__name__)
        self.cleaner=threading.Thread(target=run,name="rdinp-local-cleanup",daemon=True);self.cleaner.start()
    def close(self):
        self.stop.set()
        if self.cleaner:self.cleaner.join(2)

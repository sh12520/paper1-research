"""One isolated bilateral loopback fixture; all evidence in a fresh directory."""
import argparse
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
import traceback

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=['B2','B3','B4'],required=True)
parser.add_argument('--case',required=True)
parser.add_argument('--seed',type=int,default=0)
parser.add_argument('--out',required=True)
parser.add_argument('--source-root',required=True)
ARGS=parser.parse_args()
SOURCE=Path(ARGS.source_root).resolve()
if not SOURCE.is_relative_to(ROOT/'runs'):raise ValueError('captured run source required')
sys.path.insert(0,str(SOURCE))
from contracts import REVISION, PHASES, example_contract, jcs, parse, sha
from crypto import Identity, Trust, base_message, b64
import endpoint
from endpoint import Responder
from authority import Authority
from events import Clock, ClockError, Trace
import initiator
from initiator import Initiator
from profile import check as check_profile

def write(path,obj):
    with path.open('xb') as f:f.write(jcs(obj))

class Source:
    def __init__(self):self.lock=threading.Lock();self.fixed=None;self.fault=False
    def __call__(self):
        with self.lock:
            if self.fault:self.fault=False;raise ClockError('one-shot scoped D5 clock fault')
            return self.fixed if self.fixed is not None else time.monotonic_ns()
    def set(self,n):
        with self.lock:self.fixed=n
    def arm(self):
        with self.lock:self.fault=True

class Fixture:
    def __init__(self,path):
        self.path=path;self.case=ARGS.case;self.client_source=Source();self.server_source=Source()
        self.contract=example_contract();c=self.contract
        self.i=Identity('initiator','initiator');self.r=Identity('authority','responder')
        self.pins=[self.i.pin(),self.r.pin()];self.trust=Trust(self.pins)
        self.cc=Clock('D5-UNQUALIFIED-LOCAL-BOOT','client-monotonic',self.client_source)
        self.sc=Clock('D5-UNQUALIFIED-LOCAL-BOOT','server-monotonic',self.server_source)
        self.ct=Trace('initiator',self.cc,path/'client.events.jsonl')
        self.st=Trace('responder',self.sc,path/'server.events.jsonl')
        self.actions=[];self.lock=threading.RLock();self.response_counts={};self.request_counts={};self.jumped=False
        capacity=10 if self.case=='capacity_race' else 100
        self.authority=Authority(path/'authority.sqlite',c,self.sc,self.st,capacity=capacity,
                                 admission=0 if self.case=='capacity_reject' else capacity,
                                 tail_hook=(lambda:time.sleep(0.065)) if self.case=='tail_overrun' else None)
        self.server=Responder(self.authority,self.r,self.trust,self.st,self.response_policy).start()
        self.client=Initiator(path/'client.sqlite',c,self.i,self.trust,self.cc,self.ct,
                              after_latch_store=self.latch_hook,
                              after_initial_persist=(lambda:time.sleep(0.12)) if self.case=='initial_over_budget' else None)
        self.original_post=endpoint.post
        initiator.post=self.post
        write(path/'inputs.json',dict(mode=ARGS.mode,revision=REVISION,case=self.case,seed=ARGS.seed,
              phases=list(PHASES),plan=c.plan,policy=c.policy,timing=c.timing,trust=self.pins,
              profile=check_profile(c.plan,c.policy,c.timing),scope='LOCAL_MECHANISMS_NOT_QUALIFIED'))
        assert check_profile(c.plan,c.policy,c.timing)['eligible']

    def record(self,kind,m,**fields):
        with self.lock:self.actions.append(dict(ordinal=len(self.actions),kind=kind,phase=m['phase'],attempt=m['attempt'],**fields))

    def post(self,host,port,path,raw,timeout=2):
        m=parse(raw)
        with self.lock:
            number=self.request_counts.get(m['phase'],0);self.request_counts[m['phase']]=number+1
        suppress=(self.case=='bounded_loss' and number==0) or (self.case=='all_commit_requests_lost' and m['kind']=='COMMIT')
        if suppress:
            self.record('REQUEST_SUPPRESSED_BEFORE_HTTP',m,rawSha256=sha(raw))
            raise ConnectionError('declared local request suppression, not real network injection')
        if self.case in ('lease_tail_guard','expired_before_commit') and m['phase']=='COMMIT_INITIAL':
            with self.lock:
                if not self.jumped:
                    snap=self.authority.snapshot();lease=snap['negotiations'][0]['lease']
                    r=self.contract.policy['resourceRules']
                    value=lease+1 if self.case=='expired_before_commit' else lease-r['commitTailBudgetNs']-r['commitTailMarginNs']
                    self.server_source.set(value);self.jumped=True
                    self.record('SYNTHETIC_SERVER_TIME_BOUNDARY',m,value=value,qualifiedRate=False)
        return self.original_post(host,port,path,raw,timeout)

    def response_policy(self,m,kind,body):
        with self.lock:
            number=self.response_counts.get(m['phase'],0);self.response_counts[m['phase']]=number+1
        drop=(self.case=='bounded_loss' and number==0)
        drop=drop or (self.case=='all_commit_responses_lost' and m['kind']=='COMMIT')
        drop=drop or (self.case=='post_commit_read_loss' and m['phase']=='COMMIT_REPLAY')
        delay=0.06 if self.case=='late_response' and number==0 else 0
        if drop or delay:self.record('RESPONSE_ACTION',m,drop=drop,delayMs=round(delay*1000))
        return dict(drop=drop,delay=delay)

    def latch_hook(self,m,response):
        if self.case=='intent_clock_error' and m['phase']=='INTENT_INITIAL':self.client_source.arm()
        if self.case=='commit_clock_error' and m['phase']=='COMMIT_INITIAL':self.client_source.arm()
        if self.case=='cutoff_equality' and m['phase']=='INTENT_INITIAL':
            self.client_source.set(self.client.state['startNs']+self.contract.cutoff_ms(0)*1000000)
            self.record('SYNTHETIC_PRIVATE_UPPER_EQUALS_CUTOFF',m,qualifiedRate=False)

    def make(self,phase='INTENT_INITIAL',neg='manual',units=10,decision=None,attempt=0):
        body=dict(units=units,decisionDigest='' if decision is None else decision['decisionDigest'],
                  epoch=0 if decision is None else decision['epoch'],token='' if decision is None else decision['token'])
        return self.i.sign(base_message(self.contract,'INTENT' if phase.startswith('INTENT') else 'COMMIT',neg,'intent-'+neg,phase,attempt,'initiator','authority',body))

    def call(self,raw):
        m=parse(raw);self.ct.emit('MANUAL_SEND',m,rawSha256=sha(raw),rawBase64=b64(raw))
        status,answer=self.original_post(self.server.host,self.server.port,'/rdinp/intent' if m['kind']=='INTENT' else '/rdinp/commit',raw)
        self.ct.emit('MANUAL_RECEIVE',m,rawSha256=sha(answer),requestRawSha256=sha(raw),rawBase64=b64(answer),httpStatus=status)
        obj=parse(answer)
        if 'signature' in obj:
            obj=self.trust.verify(answer,self.contract,'authority','responder')
            assert obj['requestRawSha256']==sha(raw)
        else:assert status!=200
        return status,obj

    def prepare(self,neg='manual',units=10):
        _,obj=self.call(self.make(neg=neg,units=units));decision=obj['body']
        if 'INTENT_REPLAY' in PHASES:self.call(self.make('INTENT_REPLAY',neg,units))
        return decision

    def manual(self):
        checks=[]
        if self.case=='illegal_first_effect':
            d=dict(decisionDigest='0'*64,epoch=0,token='a'*32)
            _,obj=self.call(self.make('COMMIT_INITIAL',decision=d));assert obj['kind']=='PROBLEM'
            _,obj=self.call(self.make('COMMIT_REPLAY',neg='query-first',decision=d))
            assert not self.authority.snapshot()['negotiations'];checks.append('NO_FIRST_COMMIT_OR_QUERY_EFFECT')
        elif self.case=='capacity_race':
            raws=[self.make(neg='race-'+str(i),units=7) for i in range(2)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                replies=list(pool.map(self.call,raws))
            assert sorted(o['body']['status'] for _,o in replies)==['REJECTED','RESERVED']
            admitted=next(i for i,(_,o) in enumerate(replies) if o['body']['status']=='RESERVED')
            neg='race-'+str(admitted);decision=replies[admitted][1]['body']
            if 'INTENT_REPLAY' in PHASES:self.call(self.make('INTENT_REPLAY',neg,7))
            _,receipt=self.call(self.make('COMMIT_INITIAL',neg,7,decision))
            assert receipt['body']['status']=='COMMITTED';checks.append('RACE_ONE_ADMITTED_NO_OVERSUBSCRIPTION')
        else:
            d=self.prepare();raw=self.make('COMMIT_INITIAL',decision=d)
            _,first=self.call(raw);assert first['body']['status']=='COMMITTED'
            if self.case=='restart_history':
                self.server.close()
                self.authority=Authority(self.path/'authority.sqlite',self.contract,self.sc,self.st)
                self.server=Responder(self.authority,self.r,self.trust,self.st).start()
                self.server_source.set(d['leaseUntilNs']+1)
                _,again=self.call(raw);assert again['body']==first['body']
                checks.append('DURABLE_HISTORY_AFTER_SERVER_RESTART_AND_LEASE')
            elif self.case=='duplicate_and_conflict':
                _,again=self.call(raw);assert again['body']==first['body']
                changed=parse(raw);changed.pop('signature');changed['body']['units']=11
                _,bad=self.call(self.i.sign(changed));assert bad['body']['code']=='ATTEMPT_CONFLICT'
                checks.append('EXACT_REPLAY_STABLE_CONFLICT_NO_EFFECT')
            else:raise ValueError(self.case)
        return dict(manual=True,checks=checks,confirmationPolicyApplicable=False)

    def execute(self):
        if self.case in ('restart_history','duplicate_and_conflict','illegal_first_effect','capacity_race'):
            return self.manual()
        result=self.client.run(self.server.host,self.server.port,'negotiation','intent-negotiation',10)
        self.client.drain()
        snap=self.authority.snapshot();commits=sum(x['event']=='COMMIT' for x in snap['effects'])
        if self.case in ('clean','bounded_loss','late_response','tail_overrun'):
            assert result['effectKnowledge']=='COMMITTED' and commits==1
            assert result['confirmationComplete']
        elif self.case=='capacity_reject':assert result['status']=='REJECTED' and commits==0
        elif self.case=='all_commit_requests_lost':assert result['effectKnowledge']=='UNKNOWN' and commits==0
        elif self.case=='all_commit_responses_lost':assert result['effectKnowledge']=='UNKNOWN' and commits==1
        elif self.case=='post_commit_read_loss':
            assert result['effectKnowledge']=='COMMITTED' and commits==1
            assert result['confirmationComplete']==(ARGS.mode=='B2')
        elif self.case in ('initial_over_budget','intent_clock_error','cutoff_equality'):
            assert commits==0 and result['effectKnowledge']=='NO_COMMIT_SENT'
            assert not result['confirmationComplete']
            assert 'INTENT_INITIAL' not in self.client.state['winners']
        elif self.case=='commit_clock_error':
            assert commits==1 and result['effectKnowledge']=='COMMITTED'
            assert not result['confirmationComplete'] and 'COMMIT_INITIAL' not in self.client.state['winners']
        elif self.case=='lease_tail_guard':assert commits==0 and not result['confirmationComplete']
        elif self.case=='expired_before_commit':assert commits==0 and result['effectKnowledge']=='NOT_APPLIED'
        else:raise ValueError(self.case)
        if self.case=='tail_overrun':assert any(e.get('claim')=='STRICT_TAIL' for e in self.st.events)
        if self.case=='initial_over_budget':assert not any(e['event']=='SEND_ACTUAL' for e in self.ct.events)
        return result

    def save_close(self):
        self.client.close();self.server.close()
        write(self.path/'observations.json',self.authority.snapshot())
        db=sqlite3.connect('file:'+str(self.path/'client.sqlite').replace('\\','/')+'?mode=ro',uri=True)
        try:
            row=db.execute('SELECT state FROM client WHERE id=1').fetchone()
            write(self.path/'client-state.json',json.loads(row[0]) if row else None)
        finally:db.close()
        write(self.path/'fault-actions.json',self.actions)

def main():
    dest=Path(ARGS.out).resolve()
    if not dest.is_relative_to(ROOT/'runs'):raise ValueError('fresh evaluation run descendant required')
    dest.mkdir(parents=True,exist_ok=False)
    h=None;error=None;result=None
    try:
        h=Fixture(dest);result=h.execute()
    except BaseException:error=traceback.format_exc()
    finally:
        if h:
            try:h.save_close()
            except BaseException:error=(error or '')+'\nCLOSE_ERROR\n'+traceback.format_exc()
        write(dest/'execution.json',dict(mode=ARGS.mode,case=ARGS.case,seed=ARGS.seed,exitCode=1 if error else 0,
               result=result,error=error,scope='NEW_LOCAL_D5_NOT_B',qualification=False))
    print(json.dumps(dict(mode=ARGS.mode,case=ARGS.case,exitCode=1 if error else 0,error=error),ensure_ascii=False))
    return 1 if error else 0

if __name__=='__main__':sys.exit(main())

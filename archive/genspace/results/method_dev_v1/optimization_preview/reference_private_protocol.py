"""Fixed bilateral protocol and charged benchmark candidate verification.

This is a development adapter, not a proposal-generation algorithm.  The
verifier sees only public inputs and fixed dummy preferences.  Each agent owns
only its own private preferences and exposes only proposals and decisions.
"""
from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
from src.fast_runner import _decode_witness
from src.instances import utilities, registry_from_public
from src.state_machine import normalize, verify_instance, _active_roles, _role_costs
from src.compact_semantics import CompactEncoder
from src.enumeration import syntax_key
from src.fast_exact import FastPublicCompatibility
import json
import math

_A0={'quality_weight':1.,'latency_weight':1.,'start_delay_weight':1.,'switching_penalty':1.,'reservation':0.}
_N0={'ran_cost':1.,'fh_cost':1.,'edge_cost':1.,'policy_complexity_cost':1.,'actuation_switching_cost':1.,'reservation':0.}

@dataclass(frozen=True)
class Evidence:
    class_id:int
    witness:str
    actions:tuple
    cell_surcharges:dict
    cell_execution_costs:dict

class BudgetExhausted(Exception):
    pass

class PublicVerifier:
    """One charged exact call per class; dummy private inputs are fixed."""
    def __init__(self, public, variant, depth, limit, library):
        self.public=public; self.variant=variant; self.depth=depth; self.library=library
        self.limit=limit; self.calls=0; self.failures={}
        self._registry=registry_from_public(public)
        self._encoder=CompactEncoder(public)
        self._reference=FastPublicCompatibility(public)
        self._prechecked={};self.batch_calls=0;self.batch_candidate_checks=0;self.state_machine_calls=0

    def prepare_batch(self, class_ids):
        """Exact V1–V4 for just this already-selected, budgeted candidate batch.

        Uses the independently audited signature and fixed model arithmetic.
        The user-visible verifier is still called/charged for each candidate.
        Actual reference interpreter calls are recorded separately.
        """
        ids=[int(i) for i in class_ids]
        if len(ids)>16 or len(ids)>self.limit-self.calls or len(ids)!=len(set(ids)) or self._prechecked:
            raise ValueError('invalid, oversized or unconsumed verification batch')
        p=self.public;lib=self.library;ref=self._reference
        available_mask=sum(1<<i for i,ok in enumerate(ref.available) if ok)
        capacities={(t,s):(a,b,c) for t,s,a,b,c in p.capacity}
        self.batch_calls+=1;self.batch_candidate_checks+=len(ids)
        for cid in ids:
            if cid<0 or cid>=len(lib.keys) or not self.variant.mask(self.depth)[cid]:
                self._prechecked[cid]='V1';continue
            if int(lib.required_role_masks[cid]) & ((~available_mask)&0xfff):
                self._prechecked[cid]='V2';continue
            bad=False
            for i in range(len(ref.roles)):
                scope=int(lib.keys[cid,1+2*i]); predicate=int(lib.keys[cid,2+2*i])
                if scope!=255 and (not ref.available[i] or (scope & (~ref.supported[i]&255))!=0 or predicate!=ref.expected[i]):
                    bad=True;break
            if bad:self._prechecked[cid]='V2';continue
            if int(lib.keys[cid,0])!=1:self._prechecked[cid]='V3';continue
            count=0;bad=False
            for j,(t,s) in enumerate((t,s) for t in range(p.horizon) for s in p.states):
                profile=int(lib.profiles[cid,j])
                cap=capacities.get((t,s))
                if cap is None or any(not math.isfinite(x) or x<0 for x in cap):bad=True;break
                if profile==255:continue
                count+=1;lev=int(lib.level[cid,j]);mask=int(lib.role_masks[cid,j]);node=p.b2_profiles[profile]
                loads=lib.base_demand[profile,lev]+lib.role_costs[mask]
                if any(not math.isfinite(float(x)) or float(x)<0 or float(x)>cap[k] for k,x in enumerate(loads)):
                    bad=True;break
                if node.deadline>p.public_constraints['max_deadline'] or node.quality<p.public_constraints['min_quality']:
                    bad=True;break
                if loads[2]!=0 and not (mask & (1<<ref.role_index['reserve_edge_compute'])):bad=True;break
            if count<p.public_constraints['min_active_slots']:bad=True
            self._prechecked[cid]='V4' if bad else 'PASS'

    def verify(self, class_id):
        if self.calls>=self.limit: raise BudgetExhausted()
        self.calls+=1
        if self._prechecked:
            if int(class_id) not in self._prechecked:raise ValueError('candidate not in selected verification batch')
            outcome=self._prechecked.pop(int(class_id))
            if outcome!='PASS':
                self.failures[outcome]=self.failures.get(outcome,0)+1
                return None
        raw=self.variant.witness(int(class_id),self.depth)
        node=normalize(_decode_witness(json.loads(raw)),self.public)
        witness=syntax_key(node)
        if self._encoder.encode(node)!=self.library.keys[int(class_id)].tobytes():
            raise ValueError('normalized witness differs from semantic class')
        dummy=SimpleNamespace(public=self.public,private=SimpleNamespace(application=_A0.copy(),network=_N0.copy()))
        self.state_machine_calls+=1
        result=verify_instance(node,dummy,self.depth)
        if result.failed_layer=='V5': raise RuntimeError('fixed dummy V5 unexpectedly failed')
        if not result.verified:
            self.failures[result.failed_layer]=self.failures.get(result.failed_layer,0)+1
            return None
        norm=node; sur={}; exe={}
        for t in range(self.public.horizon):
            for s in self.public.states:
                active=_active_roles(norm,t,s)
                if active is None: continue
                costs,execution=_role_costs(active[2],self._registry)
                sur[(t,s)]=dict(zip(('RAN','FH','EDGE'),costs));exe[(t,s)]=execution
        return Evidence(int(class_id),witness,result.actions,sur,exe)

class PrivateAgent:
    """Agent API never returns a utility or reservation to its counterparty."""
    def __init__(self, kind, public, own_preferences):
        if kind not in ('application','network'): raise ValueError('agent kind')
        self.__kind=kind; self.__public=public; self.__own=dict(own_preferences)
        self.__cache={}; self.__used=set()

    def __value(self, evidence):
        if evidence.class_id not in self.__cache:
            private=SimpleNamespace(application=self.__own if self.__kind=='application' else _A0,
                                    network=self.__own if self.__kind=='network' else _N0)
            a,n=utilities(self.__public,private,evidence.actions,cell_surcharges=evidence.cell_surcharges,
                          cell_execution_costs=evidence.cell_execution_costs)
            self.__cache[evidence.class_id]=a if self.__kind=='application' else n
        return self.__cache[evidence.class_id]

    def choose(self, pool, prohibited):
        options=[e for e in pool if e.class_id not in prohibited and self.__value(e)>=self.__own['reservation']]
        if not options:return None
        selected=min(options,key=lambda e:(-self.__value(e),e.class_id))
        self.__used.add(selected.class_id)
        return selected.class_id

    def respond(self, evidence):
        return 'ACCEPT' if self.__value(evidence)>=self.__own['reservation'] else 'REJECT'

def negotiate(pool, application, network, *, max_rounds, history=None):
    """Alternate proposals and counterproposals over a public verified pool."""
    events=[] if history is None else history
    prohibited={e['candidate_id'] for e in events if e.get('message')=='PROPOSE'}
    by_id={e.class_id:e for e in pool};agents=(application,network)
    turn=sum(e.get('message')=='PROPOSE' for e in events)%2
    rounds=0
    while rounds<max_rounds:
        proposer,responder=agents[turn],agents[1-turn]
        cid=proposer.choose(pool,prohibited)
        if cid is None:
            turn=1-turn
            if agents[turn].choose(pool,prohibited) is None:return None,events
            continue
        prohibited.add(cid);events.append({'agent':turn,'message':'PROPOSE','candidate_id':cid})
        rounds+=1
        decision=responder.respond(by_id[cid]);events.append({'agent':1-turn,'message':decision,'candidate_id':cid})
        if decision=='ACCEPT':return by_id[cid],events
        turn=1-turn
    return None,events

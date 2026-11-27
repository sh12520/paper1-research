"""Fixed bilateral protocol and charged benchmark candidate verification.

This is a development adapter, not a proposal-generation algorithm.  The
verifier sees only public inputs. Each agent owns
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
import heapq

_A0={'quality_weight':1.,'latency_weight':1.,'start_delay_weight':1.,'switching_penalty':1.,'reservation':0.}
_N0={'ran_cost':1.,'fh_cost':1.,'edge_cost':1.,'policy_complexity_cost':1.,'actuation_switching_cost':1.,'reservation':0.}

@dataclass(frozen=True)
class Evidence:
    class_id:int
    witness:str
    actions:tuple
    cell_surcharges:dict
    cell_execution_costs:dict

class PackedEvidence:
    """Public class evidence; AST is reconstructed only if agreement occurs."""
    def __init__(self,verifier,class_id,actions,cell_surcharges,cell_execution_costs):
        self.class_id=class_id;self.actions=actions;self.cell_surcharges=cell_surcharges
        self.cell_execution_costs=cell_execution_costs;self.__verifier=verifier;self.__witness=None
    @property
    def witness(self):
        if self.__witness is None:self.__witness=self.__verifier._agreement_witness(self)
        return self.__witness

class BudgetExhausted(Exception):
    pass

class PublicVerifier:
    """One charged exact public V1–V4 call per already-selected class."""
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
        cid=int(class_id)
        if cid not in self._prechecked:raise ValueError('candidate not in selected verification batch')
        outcome=self._prechecked.pop(cid)
        if outcome!='PASS':
            self.failures[outcome]=self.failures.get(outcome,0)+1
            return None
        lib=self.library;p=self.public;actions=[];sur={};exe={}
        for j,(t,s) in enumerate((t,s) for t in range(p.horizon) for s in p.states):
            profile=int(lib.profiles[cid,j])
            if profile==255:continue
            mask=int(lib.role_masks[cid,j]);level='edge' if int(lib.level[cid,j]) else 'none'
            actions.append((t,s,p.b2_profiles[profile],level))
            sur[(t,s)]={k:float(lib.role_costs[mask,i]) for i,k in enumerate(('RAN','FH','EDGE'))}
            exe[(t,s)]=float(lib.execution_costs[mask])
        return PackedEvidence(self,cid,tuple(actions),sur,exe)

    def _agreement_witness(self,evidence):
        """Materialize agreed AST; harness performs reference check offline."""
        raw=self.variant.witness(evidence.class_id,self.depth)
        node=normalize(_decode_witness(json.loads(raw)),self.public)
        witness=syntax_key(node)
        if self._encoder.encode(node)!=self.library.keys[evidence.class_id].tobytes():
            raise ValueError('normalized witness differs from semantic class')
        actions=[];sur={};exe={}
        for t in range(self.public.horizon):
            for s in self.public.states:
                active=_active_roles(node,t,s)
                if active is None: continue
                actions.append((t,s,active[0],active[1]))
                costs,execution=_role_costs(active[2],self._registry)
                sur[(t,s)]=dict(zip(('RAN','FH','EDGE'),costs));exe[(t,s)]=execution
        if tuple(actions)!=evidence.actions or sur!=evidence.cell_surcharges or exe!=evidence.cell_execution_costs:
            raise ValueError('agreement witness schedule/resource costs mismatch')
        return witness

class PrivateAgent:
    """Agent API never returns a utility or reservation to its counterparty."""
    def __init__(self, kind, public, own_preferences):
        if kind not in ('application','network'): raise ValueError('agent kind')
        self.__kind=kind; self.__public=public; self.__own=dict(own_preferences)
        self.__cache={}; self.__heap=[];self.__seen=0;self.__pool_id=None

    def __value(self, evidence):
        if evidence.class_id not in self.__cache:
            private=SimpleNamespace(application=self.__own if self.__kind=='application' else _A0,
                                    network=self.__own if self.__kind=='network' else _N0)
            a,n=utilities(self.__public,private,evidence.actions,cell_surcharges=evidence.cell_surcharges,
                          cell_execution_costs=evidence.cell_execution_costs)
            self.__cache[evidence.class_id]=a if self.__kind=='application' else n
        return self.__cache[evidence.class_id]

    def choose(self, pool, prohibited):
        if self.__pool_id is None:self.__pool_id=id(pool)
        if id(pool)!=self.__pool_id or len(pool)<self.__seen:raise ValueError('pool must be append-only')
        for evidence in pool[self.__seen:]:
            value=self.__value(evidence)
            if value>=self.__own['reservation']:heapq.heappush(self.__heap,(-value,evidence.class_id))
        self.__seen=len(pool)
        while self.__heap and self.__heap[0][1] in prohibited:heapq.heappop(self.__heap)
        return None if not self.__heap else self.__heap[0][1]

    def respond(self, evidence):
        return 'ACCEPT' if self.__value(evidence)>=self.__own['reservation'] else 'REJECT'

def negotiate(pool, application, network, *, max_rounds, history=None):
    """Alternate proposals and counterproposals over a public verified pool."""
    events=[] if history is None else history
    prohibited={e['candidate_id'] for e in events if e.get('message')=='PROPOSE'}
    by_id={e.class_id:e for e in pool};agents=(application,network)
    proposals=[e for e in events if e.get('message')=='PROPOSE']
    # A party without an acceptable counter can be skipped, so consecutive
    # proposals can come from the same party. Resume with the actual last
    # proposer's counterparty, not the parity of the number of proposals.
    turn=1-proposals[-1]['agent'] if proposals else 0
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

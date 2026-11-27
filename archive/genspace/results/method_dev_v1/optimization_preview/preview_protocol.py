"""Performance-only preview: selected classes, private heaps, deferred witness.

Not the frozen execution path.  Public batch checks and each charged verify API
call are unchanged; no private utility is exposed and no random instance is made.
"""
import heapq,json
from src.fast_runner import _decode_witness
from src.state_machine import normalize,_active_roles,_role_costs
from src.enumeration import syntax_key
from private_protocol import PrivateAgent,PublicVerifier,BudgetExhausted

class HeapPrivateAgent(PrivateAgent):
    """Exact incremental version of original own-utility/class-ID selection."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.__heap=[];self.__seen=0;self.__pool_id=None
    def choose(self,pool,prohibited):
        if self.__pool_id is None:self.__pool_id=id(pool)
        if id(pool)!=self.__pool_id or len(pool)<self.__seen:
            raise ValueError('pool must be the same append-only list')
        for evidence in pool[self.__seen:]:
            value=self._PrivateAgent__value(evidence)
            if value>=self._PrivateAgent__own['reservation']:
                heapq.heappush(self.__heap,(-value,evidence.class_id))
        self.__seen=len(pool)
        while self.__heap and self.__heap[0][1] in prohibited:heapq.heappop(self.__heap)
        return None if not self.__heap else self.__heap[0][1]

class LazyEvidence:
    def __init__(self,verifier,cid,actions,surcharges,execution):
        self.class_id=cid;self.actions=actions;self.cell_surcharges=surcharges
        self.cell_execution_costs=execution;self.__verifier=verifier;self.__witness=None
    @property
    def witness(self):
        if self.__witness is None:self.__witness=self.__verifier.certify_agreement(self)
        return self.__witness

class PreviewPublicVerifier(PublicVerifier):
    """Use exact cells as public evidence; reconstruct agreed AST lazily.

    The trusted harness invokes the original interpreter once, offline after
    the method run, to validate each distinct agreement on the real instance.
    """
    def verify(self,class_id):
        cid=int(class_id)
        if self.calls>=self.limit:raise BudgetExhausted()
        self.calls+=1
        if cid not in self._prechecked:raise ValueError('candidate not in selected batch')
        outcome=self._prechecked.pop(cid)
        if outcome!='PASS':
            self.failures[outcome]=self.failures.get(outcome,0)+1
            return None
        lib=self.library;p=self.public;actions=[];surcharges={};execution={}
        for j,(t,s) in enumerate((t,s) for t in range(p.horizon) for s in p.states):
            profile=int(lib.profiles[cid,j])
            if profile==255:continue
            mask=int(lib.role_masks[cid,j]);level='edge' if int(lib.level[cid,j]) else 'none'
            actions.append((t,s,p.b2_profiles[profile],level))
            surcharges[(t,s)]={k:float(lib.role_costs[mask,i]) for i,k in enumerate(('RAN','FH','EDGE'))}
            execution[(t,s)]=float(lib.execution_costs[mask])
        return LazyEvidence(self,cid,tuple(actions),surcharges,execution)
    def certify_agreement(self,evidence):
        raw=self.variant.witness(evidence.class_id,self.depth)
        node=normalize(_decode_witness(json.loads(raw)),self.public)
        witness=syntax_key(node)
        if self._encoder.encode(node)!=self.library.keys[evidence.class_id].tobytes():
            raise ValueError('agreement witness differs from semantic class')
        actions=[];sur={};exe={}
        for t in range(self.public.horizon):
            for s in self.public.states:
                active=_active_roles(node,t,s)
                if active is None:continue
                actions.append((t,s,active[0],active[1]))
                costs,ex=_role_costs(active[2],self._registry)
                sur[(t,s)]=dict(zip(('RAN','FH','EDGE'),costs));exe[(t,s)]=ex
        if tuple(actions)!=evidence.actions or sur!=evidence.cell_surcharges or exe!=evidence.cell_execution_costs:
            raise ValueError('agreement witness schedule/resource costs mismatch')
        return witness

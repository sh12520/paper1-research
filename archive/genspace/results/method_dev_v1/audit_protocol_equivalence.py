"""Compare selected-only batch and sequential reference on existing PILOT.

No oracle or attribution outcome is read, and full-graph private evaluation,
benchmark seed derivation and instance generation are guarded against.
"""
import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
import src.instances as instances
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary,FastEvaluator
import runtime
from private_protocol import PublicVerifier,PrivateAgent
from public_search import sanitize_public

def blocked(*a,**k):raise AssertionError('forbidden full private evaluation or new instance seed')
instances.derive_seed=instances.generate_instance=blocked
class SequentialReference(PublicVerifier):
    def prepare_batch(self,ids):
        ids=list(ids)
        if len(ids)>16 or len(ids)>self.limit-self.calls or len(ids)!=len(set(ids)) or self._prechecked:
            raise ValueError('invalid batch')
        self.batch_calls+=1;self.batch_candidate_checks+=len(ids)
        # No precheck: verify() invokes the original full public interpreter.

def comparable(row):
    ignore={'state_machine_calls','elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
    return {k:v for k,v in row.items() if k not in ignore}

def main():
    t=time.perf_counter();plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[s for s in plan if s['configuration']['resource_pressure']=='medium' and s['configuration']['preference_conflict']=='high' and s['seed_index']==0]
    if len(slots)!=16:raise AssertionError('fixture coverage')
    lib=FastLibrary.from_graph(scope='pilot-execution');initialized=False;checks=[]
    methods=('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY')
    with patch.object(FastEvaluator,'evaluate',side_effect=blocked):
      for slot in slots:
        iid=slot['instance_id'];ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        pub=runtime.verification_public(ins.public);view=sanitize_public(ins.public)
        if not initialized:lib.bind_public_basis(pub);initialized=True
        variant=runtime.choose_variant(pub,lib)
        def execute(method,verifier):
            app=PrivateAgent('application',pub,ins.private.application);net=PrivateAgent('network',pub,ins.private.network)
            with patch.object(runtime,'PublicVerifier',verifier):
                return runtime.run(view,pub,variant,app,net,lib,method,stop_budget=500)
        for method in methods:
            batch,bh=execute(method,PublicVerifier);reference,rh=execute(method,SequentialReference)
            if bh!=rh:raise AssertionError(('protocol history differs',iid,method))
            for b in (100,500):
                if comparable(batch[b])!=comparable(reference[b]):raise AssertionError(('budget outcome differs',iid,method,b))
                if batch[b]['verification_calls']>b or batch[b]['batch_candidate_checks']!=batch[b]['verification_calls']:
                    raise AssertionError(('invalid budget accounting',iid,method,b))
            checks.append({'instance_id':iid,'method':method,'pass':True})
    result={'pass':True,'fixture_count':len(slots),'method_count':len(methods),'comparisons':len(checks),
            'budgets':[100,500],'results':checks,'no_full_private_fast_evaluation':True,'no_new_seed_or_instance':True,
            'scope':'same implementation in batch mode versus sequential original interpreter; not an independent optimizer',
            'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('private_protocol.py','runtime.py','public_search.py')},'seconds':time.perf_counter()-t}
    (Path(__file__).parent/'protocol_equivalence_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('pass','fixture_count','method_count','comparisons','budgets','seconds')}),flush=True)
if __name__=='__main__':main()

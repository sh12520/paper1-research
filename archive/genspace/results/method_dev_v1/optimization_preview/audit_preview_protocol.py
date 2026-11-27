"""Preview packed/heap vs frozen reference on existing serialized PILOT.

Uses the same public ordering and budget units; no oracle, attribution, new
instance/seed or full private FAST evaluation is accessed by the test.
"""
import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/method_dev_v1';HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE));sys.path.insert(0,str(HERE))
import src.instances as instances
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary,FastEvaluator
import runtime
from private_protocol import PublicVerifier,PrivateAgent
from public_search import sanitize_public
from preview_protocol import PreviewPublicVerifier,HeapPrivateAgent

def blocked(*a,**k):raise AssertionError('forbidden full private evaluation or new instance seed')
instances.derive_seed=instances.generate_instance=blocked
def comparable(row):
    ignore={'state_machine_calls','elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
    return {k:v for k,v in row.items() if k not in ignore}
def main():
    start=time.perf_counter();plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[s for s in plan if s['configuration']['resource_pressure']=='medium' and s['configuration']['preference_conflict']=='high' and s['seed_index']==0]
    if len(slots)!=16:raise AssertionError('fixture coverage')
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'preview_protocol.py',BASE/'private_protocol.py',BASE/'runtime.py',BASE/'public_search.py')}
    lib=FastLibrary.from_graph(scope='pilot-execution');initialized=False;checks=[]
    methods=('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY')
    with patch.object(FastEvaluator,'evaluate',side_effect=blocked):
      for slot in slots:
        iid=slot['instance_id'];ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        pub=runtime.verification_public(ins.public);view=sanitize_public(ins.public)
        if not initialized:lib.bind_public_basis(pub);initialized=True
        variant=runtime.choose_variant(pub,lib)
        def execute(method,verifier,agent):
            app=agent('application',pub,ins.private.application);net=agent('network',pub,ins.private.network)
            with patch.object(runtime,'PublicVerifier',verifier):
                return runtime.run(view,pub,variant,app,net,lib,method,stop_budget=500)
        for method in methods:
            old,old_history=execute(method,PublicVerifier,PrivateAgent)
            new,new_history=execute(method,PreviewPublicVerifier,HeapPrivateAgent)
            if old_history!=new_history:raise AssertionError(('protocol history differs',iid,method))
            for budget in (100,500):
                if comparable(old[budget])!=comparable(new[budget]):raise AssertionError(('outcome differs',iid,method,budget))
                if new[budget]['verification_calls']>budget or new[budget]['batch_candidate_checks']!=new[budget]['verification_calls']:
                    raise AssertionError(('budget accounting differs',iid,method,budget))
            checks.append({'instance_id':iid,'method':method,'pass':True})
    if any(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v for k,v in sources.items()):raise AssertionError('source changed during audit')
    out={'pass':True,'fixture_count':len(slots),'method_count':len(methods),'comparisons':len(checks),'budgets':[100,500],
         'results':checks,'no_full_private_fast_evaluation':True,'no_new_seed_or_instance':True,'source_sha256':sources,
         'scope':'same 16 original serialized fixtures; historical reference vs preview packed evidence and private heaps; B100/B500 only',
         'seconds':time.perf_counter()-start}
    (HERE/'preview_protocol_equivalence.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({k:out[k] for k in ('pass','fixture_count','method_count','comparisons','budgets','seconds')}),flush=True)
if __name__=='__main__':main()

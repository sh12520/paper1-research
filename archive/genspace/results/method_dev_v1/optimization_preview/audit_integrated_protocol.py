"""Integrated backend vs retained pre-integration reference, existing PILOT only."""
import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/method_dev_v1';HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE));sys.path.insert(0,str(HERE))
import src.instances as instances
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary,FastEvaluator
import runtime
from private_protocol import PublicVerifier as IntegratedVerifier,PrivateAgent as IntegratedAgent
from reference_private_protocol import PublicVerifier as ReferenceVerifier,PrivateAgent as ReferenceAgent
from public_search import sanitize_public
def forbidden(*a,**k):raise AssertionError('forbidden seed/instance/full-private-fast evaluation')
instances.derive_seed=instances.generate_instance=forbidden
def comparable(row):
    ignore={'state_machine_calls','elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
    return {k:v for k,v in row.items() if k not in ignore}
def main():
    start=time.perf_counter();plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[s for s in plan if s['configuration']['resource_pressure']=='medium' and s['configuration']['preference_conflict']=='high' and s['seed_index']==0]
    if len(slots)!=16:raise AssertionError('fixture coverage')
    paths=(HERE/'reference_private_protocol.py',BASE/'private_protocol.py',BASE/'runtime.py',BASE/'public_search.py')
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if hashes[str(paths[0].relative_to(ROOT))]!='edc4d6bf123cd73e9e74928d48ad36a7e3c4e6a2449754ba6580a26dc176ea5e':raise ValueError('reference SHA mismatch')
    lib=FastLibrary.from_graph(scope='pilot-execution');initialized=False;checks=[]
    methods=('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY')
    with patch.object(FastEvaluator,'evaluate',side_effect=forbidden):
      for slot in slots:
        iid=slot['instance_id'];ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        pub=runtime.verification_public(ins.public);view=sanitize_public(ins.public)
        if not initialized:lib.bind_public_basis(pub);initialized=True
        variant=runtime.choose_variant(pub,lib)
        def execute(method,verifier,agent):
            app=agent('application',pub,ins.private.application);net=agent('network',pub,ins.private.network)
            with patch.object(runtime,'PublicVerifier',verifier):return runtime.run(view,pub,variant,app,net,lib,method,stop_budget=500)
        for method in methods:
            old,old_history=execute(method,ReferenceVerifier,ReferenceAgent)
            new,new_history=execute(method,IntegratedVerifier,IntegratedAgent)
            if old_history!=new_history:raise AssertionError(('protocol history differs',iid,method))
            for budget in (100,500):
                if comparable(old[budget])!=comparable(new[budget]):raise AssertionError(('outcome differs',iid,method,budget))
                if new[budget]['verification_calls']>budget or new[budget]['batch_candidate_checks']!=new[budget]['verification_calls']:raise AssertionError(('budget accounting',iid,method,budget))
            checks.append({'instance_id':iid,'method':method,'pass':True})
    if any(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v for k,v in hashes.items()):raise ValueError('source changed during audit')
    result={'pass':True,'fixture_count':len(slots),'method_count':len(methods),'comparisons':len(checks),'budgets':[100,500],
      'results':checks,'source_sha256':hashes,'no_new_seed_or_instance':True,'no_full_private_fast_evaluation':True,
      'scope':'integrated source vs exact retained old verifier/agent, 16 fixtures, five methods, B100/500 only','seconds':time.perf_counter()-start}
    (HERE/'integrated_protocol_equivalence.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('pass','fixture_count','method_count','comparisons','budgets','seconds')}),flush=True)
if __name__=='__main__':main()

"""Corrected-protocol reference backend vs packed backend through B=10000."""
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
def blocked(*a,**k):raise AssertionError('forbidden full private FAST or new seed/instance')
instances.derive_seed=instances.generate_instance=blocked
def comparable(row):
    ignore={'state_machine_calls','elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
    return {k:v for k,v in row.items() if k not in ignore}
def main():
    started=time.perf_counter();paths=(BASE/'harness.py',BASE/'runtime.py',BASE/'private_protocol.py',BASE/'public_search.py')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    refsha=hashlib.sha256((HERE/'reference_private_protocol.py').read_bytes()).hexdigest()
    if refsha!='edc4d6bf123cd73e9e74928d48ad36a7e3c4e6a2449754ba6580a26dc176ea5e':raise ValueError('reference source mismatch')
    slots=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances'];iid=slots[102]['instance_id']
    ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
    pub=runtime.verification_public(ins.public);view=sanitize_public(ins.public)
    lib=FastLibrary.from_graph(scope='pilot-execution');lib.bind_public_basis(pub);variant=runtime.choose_variant(pub,lib)
    def execute(verifier,agent):
        app=agent('application',pub,ins.private.application);net=agent('network',pub,ins.private.network)
        with patch.object(runtime,'PublicVerifier',verifier):return runtime.run(view,pub,variant,app,net,lib,'DG-PCE',stop_budget=10000)
    with patch.object(FastEvaluator,'evaluate',side_effect=blocked):
        old,old_history=execute(ReferenceVerifier,ReferenceAgent);new,new_history=execute(IntegratedVerifier,IntegratedAgent)
    matches={str(b):comparable(old[b])==comparable(new[b]) for b in (100,500,1000,5000,10000)}
    if hashes!={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:raise ValueError('source changed')
    result={'pass':old_history==new_history and all(matches.values()),'history_equal':old_history==new_history,
      'history_count':len(old_history),'budget_matches':matches,'source_sha256':hashes,'reference_private_protocol_sha256':refsha,
      'fixture_id':iid,'scope':'corrected protocol; reference interpreter/agent vs packed/heap; one existing PILOT instance',
      'no_full_private_fast_evaluation':True,'no_new_seed_or_instance':True,'seconds':time.perf_counter()-started}
    (HERE/'fixed_high_budget_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('pass','history_equal','history_count','budget_matches','seconds')},sort_keys=True),flush=True)
    if not result['pass']:raise SystemExit(1)
if __name__=='__main__':main()

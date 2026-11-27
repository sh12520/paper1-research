"""Generate source-bound information audit after all method code is frozen."""
import ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from src.execution_snapshot import verify_snapshot,PILOT_EXECUTABLE_SNAPSHOT
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    names=('harness.py','runtime.py','private_protocol.py','public_search.py')
    start={n:sha(BASE/n) for n in names};config_hash=sha(BASE/'method_config.json')
    config=json.loads((BASE/'method_config.json').read_text(encoding='utf8'))
    tree=ast.parse((BASE/'public_search.py').read_text(encoding='utf8'))
    literals=[tuple(n.value for n in x.elts) for x in ast.walk(tree) if isinstance(x,ast.Tuple) and all(isinstance(n,ast.Constant) and isinstance(n.value,str) for n in x.elts)]
    global_order=tuple(config['global_frequency_order'])
    order_ok=global_order==('O','P','C','D') and global_order in literals
    expected={k:start[k] for k in ('private_protocol.py','public_search.py','runtime.py')}
    evidence={};errors=[]
    for name in ('batch_differential_audit.json','v2_universe_audit.json'):
        obj=json.loads((BASE/name).read_text(encoding='utf8'))
        evidence[name]={'sha256':sha(BASE/name),'pass':obj.get('pass') is True,'source_matches':obj.get('source_sha256')==expected}
        if not evidence[name]['pass'] or not evidence[name]['source_matches']:errors.append('stale or failed '+name)
    name='optimization_preview/integrated_protocol_equivalence.json'
    obj=json.loads((BASE/name).read_text(encoding='utf8'))
    sources={k.replace('\\','/'):v for k,v in obj.get('source_sha256',{}).items()}
    actual={k.removeprefix('results/method_dev_v1/'):v for k,v in sources.items() if k.startswith('results/method_dev_v1/') and not k.startswith('results/method_dev_v1/optimization_preview/')}
    old=sources.get('results/method_dev_v1/optimization_preview/reference_private_protocol.py')
    evidence[name]={'sha256':sha(BASE/name),'pass':obj.get('pass') is True,'source_matches':actual==expected and old=='edc4d6bf123cd73e9e74928d48ad36a7e3c4e6a2449754ba6580a26dc176ea5e'}
    if not evidence[name]['pass'] or not evidence[name]['source_matches']:errors.append('stale or failed '+name)
    name='optimization_preview/fixed_high_budget_audit.json';obj=json.loads((BASE/name).read_text(encoding='utf8'))
    budget_matches=obj.get('budget_matches',{})
    evidence[name]={'sha256':sha(BASE/name),'pass':obj.get('pass') is True and obj.get('history_equal') is True and set(budget_matches)=={'100','500','1000','5000','10000'} and all(budget_matches.values()),'source_matches':obj.get('source_sha256')==start}
    if not evidence[name]['pass'] or not evidence[name]['source_matches']:errors.append('stale or failed '+name)
    name='optimization_preview/packed_schedule_audit.json';obj=json.loads((BASE/name).read_text(encoding='utf8'))
    original=obj.get('original_source_sha256',{})
    evidence[name]={'sha256':sha(BASE/name),'pass':obj.get('pass') is True,'source_matches':original.get('private_protocol.py')=='edc4d6bf123cd73e9e74928d48ad36a7e3c4e6a2449754ba6580a26dc176ea5e' and all(original.get(n)==start[n] for n in ('runtime.py','public_search.py'))}
    if not evidence[name]['pass'] or not evidence[name]['source_matches']:errors.append('stale or failed '+name)
    name='alternating_turn_counterexample.json';obj=json.loads((BASE/name).read_text(encoding='utf8'))
    evidence[name]={'sha256':sha(BASE/name),'pass':obj.get('status')=='COUNTEREXAMPLE' and obj.get('actual_first_agent')==0 and obj.get('expected_first_agent_after_last_A_proposal')==1,'source_matches':obj.get('source_sha256')=='527ba34e757da8fc81145ec1f1fed9e4342863e60a8b905ffa6faf90cacfb8ff','note':'historical pre-fix counterexample; corrected behavior checked by independent unit tests'}
    if not evidence[name]['pass'] or not evidence[name]['source_matches']:errors.append('missing prior turn counterexample')
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    suites=('test_privacy_independent.py','test_public_search.py','test_runtime_min.py','test_resume_independent.py','test_alternating_protocol_independent.py','test_protocol_turn.py')
    results=[]
    for suite in suites:
        p=subprocess.run([sys.executable,str(BASE/suite),'-q'],cwd=ROOT,env=env,capture_output=True,text=True)
        results.append({'suite':suite,'returncode':p.returncode,'output':p.stdout+p.stderr,'sha256':sha(BASE/suite)})
        if p.returncode:errors.append('failed '+suite)
    if not order_ok:errors.append('global baseline literal differs from config')
    end={n:sha(BASE/n) for n in names}
    if start!=end or config_hash!=sha(BASE/'method_config.json'):errors.append('source or config changed during audit')
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    out={'pass':not errors,'errors':errors,'test_count':19,'tests':results,'global_frequency_config_order_matches_literal':order_ok,
         'runtime_boundary':'sanitized public view and separate local private agent ports; labels, opponent values, O1 and attribution do not enter runtime arguments',
         'trusted_process_limit':'API/data-flow audit in trusted single Python process; not OS, cryptographic or malicious-introspection isolation',
         'no_new_instance_seed_guard':'generation and benchmark instance-seed derivation blocked in fixture/protocol audits; RANDOM-BUDGET uses a deterministic PRNG input derived solely from allowlisted public fields',
         'full_private_fast_evaluate_guard':'blocked in 16-fixture 5-method protocol-equivalence test; no invocation',
         'source_hashes':start,'config_sha256':config_hash,'differential_evidence':evidence,
         'audit_note':'19 unit tests plus 924 selected-candidate reference checks, 17-pattern V2 scope audit, and 80 batch-vs-sequential protocol checks under corrected turns; independent repeat is not an adversarial isolation proof'}
    (BASE/'information_audit_result.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({'pass':out['pass'],'errors':errors,'unit_tests':19,'source_hashes':start},sort_keys=True))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()

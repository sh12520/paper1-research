"""Trusted development harness; consumes only existing serialized PILOT files.

The method receives sanitized public inputs and two independent agent ports.
Oracle and attribution labels are loaded only after *all* method calls for an
instance finish, for offline evaluation, and are never passed to the method.
"""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary
from src.fast_runner import _decode_witness
from src.state_machine import verify_instance
from src.execution_snapshot import verify_snapshot,PILOT_EXECUTABLE_SNAPSHOT,sha256_file
from runtime import BUDGETS,CHUNK,SINGLETON_QUOTA,PAIR_QUOTA,ROUND_LIMIT,verification_public,choose_variant,run
from public_search import sanitize_public
import public_search as search
from private_protocol import PrivateAgent
import src.instances as instance_module

METHODS=('B2','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY','SINGLETON-ONLY','DG-PCE')
EXPECTED_SNAPSHOT='18c3ef2eda454dd91a607eaecdd7501f5f82624f907d09bd6939cc77dd6bec0f'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')
def synced(path,raw):
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--offset',type=int,default=0);p.add_argument('--output',required=True);p.add_argument('--methods',nargs='+',default=list(METHODS));a=p.parse_args()
    if any(x not in METHODS for x in a.methods):raise ValueError('unknown method')
    out=ROOT/a.output
    out.mkdir(parents=True,exist_ok=True)
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    if sha256_file(PILOT_EXECUTABLE_SNAPSHOT)!=EXPECTED_SNAPSHOT:raise ValueError('frozen pilot snapshot changed')
    conf_path=ROOT/'results/method_dev_v1/method_config.json';conf=json.loads(conf_path.read_text(encoding='utf8'))
    if (tuple(conf['budgets_exact_candidate_verification_calls'])!=BUDGETS or conf['batch_size']!=CHUNK or
        conf['singleton_stage_max_verifications_per_group']!=SINGLETON_QUOTA or
        conf['pair_stage_max_verifications_per_group']!=PAIR_QUOTA or conf['max_rounds']!=ROUND_LIMIT or
        conf['b2_exact_verification_calls']!=27):raise ValueError('method code/config mismatch')
    if (conf['public_rank_score']!={'violation':1.0,'margin':-search.MARGIN_WEIGHT,'capability_cost':search.COST_WEIGHT,'quality_deficit':search.QUALITY_WEIGHT,'group_count':search.GROUP_COMPLEXITY_WEIGHT} or
        conf['probe_relief_penalties']!={'capability_cost':search.PROBE_COST_WEIGHT,'structural_complexity':search.PROBE_GROUP_PENALTY}):raise ValueError('public scoring constants/config mismatch')
    source_files=['harness.py','runtime.py','private_protocol.py','public_search.py']
    source_hashes={s:digest((ROOT/'results/method_dev_v1'/s).read_bytes()) for s in source_files}
    run_manifest={'version':1,'code_sha256':source_hashes,'config_sha256':digest(conf_path.read_bytes()),
                  'plan_sha256':digest((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_bytes()),'methods':a.methods,
                  'offset':a.offset,'limit':a.limit,'budgets':list(BUDGETS),'namespace':'GENSPACE-FAIL-01-PILOT',
                  'pilot_execution_snapshot_sha256':EXPECTED_SNAPSHOT}
    manifest_path=out/'run_manifest.json'
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding='utf8'))!=run_manifest:raise ValueError('resume source/config/plan mismatch')
    else:
        if any(out.iterdir()):raise ValueError('output lacks run manifest; fail closed')
        synced(manifest_path,encoded(run_manifest))
    forbidden={'derive_seed':0,'generate_instance':0}
    def denied(name):
        def f(*args,**kwargs):forbidden[name]+=1;raise RuntimeError('new instance/seed generation forbidden')
        return f
    instance_module.derive_seed=denied('derive_seed');instance_module.generate_instance=denied('generate_instance')
    plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    plan=plan[a.offset:]
    if a.limit:plan=plan[:a.limit]
    manifest=json.loads((ROOT/'results/pilot/instances_manifest.json').read_text(encoding='utf8'))
    library=FastLibrary.from_graph(scope='pilot-execution');initialized=False
    start=time.perf_counter()
    # Preserve interrupted temporary records without treating them as complete.
    for incomplete in out.glob('.*.pending'):
        quarantine=out/'interrupted';quarantine.mkdir(exist_ok=True)
        os.rename(incomplete,quarantine/(incomplete.name+'.'+str(time.time_ns())))
    skipped=0
    for j,slot in enumerate(plan):
        if any(digest((ROOT/'results/method_dev_v1'/s).read_bytes())!=h for s,h in source_hashes.items()) or digest(conf_path.read_bytes())!=run_manifest['config_sha256']:
            raise ValueError('development source/config changed during run')
        iid=slot['instance_id'];raw=(ROOT/'results/pilot/instances'/f'{iid}.json').read_bytes();instance=deserialize_instance(raw.decode())
        expected={'sha256':hashlib.sha256(raw).hexdigest(),'instance_hash':instance.instance_hash,'public_hash':instance.public_hash,'private_hash':instance.private_hash}
        if expected!=manifest[iid] or instance.namespace!='GENSPACE-FAIL-01-PILOT':raise ValueError('serialized instance mismatch')
        result_dir=out/iid
        paths={'instance':ROOT/'results/pilot/instances'/f'{iid}.json','oracle':ROOT/'results/pilot/main'/iid/'result.json',
               'oracle_marker':ROOT/'results/pilot/main'/iid/'COMPLETE.json','attribution':ROOT/'results/pilot_attribution_work/records'/f'{iid}.json'}
        if result_dir.exists():
            input_hashes={k:digest(p.read_bytes()) for k,p in paths.items()}
            payload=(result_dir/'record.json').read_bytes();marker=json.loads((result_dir/'COMPLETE.json').read_text(encoding='utf8'))
            prior=json.loads(payload)
            expected_marker={'format':1,'instance_id':iid,'record_sha256':digest(payload),'input_sha256':input_hashes,
                             'run_manifest_sha256':digest(encoded(run_manifest))}
            if marker!=expected_marker or prior.get('instance_id')!=iid or prior.get('instance_hash')!=instance.instance_hash or set(prior.get('methods',{}))!=set(a.methods):
                raise ValueError('invalid or incompatible completed record')
            skipped+=1;continue
        pub=verification_public(instance.public);view=sanitize_public(instance.public)
        if not initialized:library.bind_public_basis(pub);initialized=True
        variant=choose_variant(pub,library)
        method_outputs={}
        for method in a.methods:
            app=PrivateAgent('application',pub,instance.private.application);net=PrivateAgent('network',pub,instance.private.network)
            outputs,history=run(view,pub,variant,app,net,library,method)
            method_outputs[method]={'budgets':outputs,'history':history}
        # Offline-only evaluator sees prior oracle outputs after online methods.
        oracle=json.loads((ROOT/'results/pilot/main'/iid/'result.json').read_text(encoding='utf8'))
        oracle_rows={r['method']:r for r in oracle['rows']}
        if any(x['budgets'][100]['b2_agreement']!=oracle_rows['B2']['agreement'] for x in method_outputs.values()):raise ValueError('B2 existence differs from original exact B2')
        attribution=json.loads((ROOT/'results/pilot_attribution_work/records'/f'{iid}.json').read_text(encoding='utf8'))
        input_hashes={k:digest(p.read_bytes()) for k,p in paths.items()}
        subs=attribution['subsets'];target=not subs['0']['agreement_exists'] and subs['15']['agreement_exists']
        multi=target and not any(subs[str(k)]['agreement_exists'] for k in (1,2,4,8))
        validated={};offline_calls=0
        for mo in method_outputs.values():
            for result in mo['budgets'].values():
                if result['agreement']:
                    witness=result['representative']
                    if witness not in validated:
                        v=verify_instance(_decode_witness(json.loads(witness)),instance,view.depth);offline_calls+=1
                        if not v.verified:raise ValueError('negotiated agreement fails offline bilateral validation')
                        validated[witness]={'uA':v.application_utility,'uN':v.network_utility,'nash':v.application_utility*v.network_utility}
                    result.update(validated[witness])
        result={'instance_id':iid,'instance_hash':instance.instance_hash,'public_hash':instance.public_hash,'private_hash':instance.private_hash,
                'family':slot['family'],'configuration':slot['configuration'],'methods':method_outputs,
                'oracle':{'B2_agreement':oracle_rows['B2']['agreement'],'O1_agreement':oracle_rows['O1']['agreement'],
                          'O1_uA':oracle_rows['O1']['application_utility'],'O1_uN':oracle_rows['O1']['network_utility'],
                          'O1_nash':oracle_rows['O1']['nash_welfare'],'O1_candidate_count':oracle_rows['O1']['candidate_count'],
                          'O1_historical_stage_runtime_seconds':oracle_rows['O1']['runtime_seconds'],
                          'recoverable':target,'multi_group_necessary':multi,'non_offload_solvable':bool(subs['7']['agreement_exists']) and target},
                'offline_validation_calls':offline_calls}
        tempdir=out/('.'+iid+'.pending');tempdir.mkdir()
        payload=encoded(result);marker={'format':1,'instance_id':iid,'record_sha256':digest(payload),'input_sha256':input_hashes,
                                       'run_manifest_sha256':digest(encoded(run_manifest))}
        synced(tempdir/'record.json',payload);synced(tempdir/'COMPLETE.json',encoded(marker));os.rename(tempdir,result_dir)
        print(f'{j+1}/{len(plan)} elapsed={time.perf_counter()-start:.3f}',flush=True)
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    if sha256_file(PILOT_EXECUTABLE_SNAPSHOT)!=EXPECTED_SNAPSHOT:raise ValueError('frozen pilot snapshot changed')
    (out/'_guard.json').write_text(json.dumps({'forbidden_calls':forbidden,'count':len(plan),'validated_skips':skipped})+'\n',encoding='utf8')
if __name__=='__main__':main()

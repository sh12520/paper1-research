"""Single common, authorization-gated orchestration engine."""
import argparse, hashlib, json, os, statistics, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=Path(os.environ.get('GENSPACE_RUN_ROOT',str(ROOT/'results'/'smoke02_common_shadow')))
NAMESPACE=os.environ.get('GENSPACE_RUN_NAMESPACE','GENSPACE-FAIL-01-ENGINEERING-SHADOW')
SHADOW='GENSPACE-FAIL-01-ENGINEERING-SHADOW'
SMOKE='GENSPACE-FAIL-01-SMOKE'
PILOT='GENSPACE-FAIL-01-PILOT'
SCOPES={SHADOW:'shadow',SMOKE:'smoke02',PILOT:'pilot-execution'}
SCOPE=SCOPES.get(NAMESPACE,'denied')
SNAPSHOT_CONTEXT=os.environ.get('GENSPACE_SNAPSHOT_PATH')
AUTH_CONTEXT=os.environ.get('GENSPACE_AUTH_PATH')
ACTIVE_SEGMENT=None

def blob(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def previous_segments(directory,current):
    return [read(f) for f in sorted(Path(directory).glob('*.json')) if f!=Path(current)]
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('wb') as f:f.write(blob(obj));f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def record_memory_pause(state, segment, segment_path, resume_phase):
    """Persist a safety pause while retaining the phase to resume."""
    state['phase']='MAIN_PAUSED';state['resume_phase']=resume_phase
    write(OUT/'state.json',state)
    segment.update(status='PAUSED_MEMORY',resume_phase=resume_phase,end=time.time())
    write(segment_path,segment)

def explained_job(j):
    if j.get('status')=='OK':return j.get('lifecycle',{}).get('pass') is True
    if j.get('status')!='PAUSED_MEMORY':return False
    if j.get('guard',{}).get('pass') is False:return True
    from src.process_lifecycle import EMERGENCY_FLOOR
    life=j.get('lifecycle',{})
    return (any(s.get('available',EMERGENCY_FLOOR)>=0 and s.get('available',EMERGENCY_FLOOR)<EMERGENCY_FLOOR for s in j.get('samples',[]))
            and life.get('assignment_verified') is True
            and life.get('job_accounting',{}).get('active_processes')==0
            and not (life.get('job_limit_flags',0) & (0x800|0x1000)))
def gate():
    from src.smoke_authorization import authorize
    default_auth=ROOT/('PILOT_AUTHORIZATION_STATE.json' if NAMESPACE==PILOT else 'SMOKE02_AUTHORIZATION_STATE.json')
    return authorize(NAMESPACE,snapshot_path=SNAPSHOT_CONTEXT,auth_path=AUTH_CONTEXT or default_auth)['snapshot_sha256']
def getplan():
    from src.shadow_plans import validate_plan
    if NAMESPACE==SHADOW:
        p=read(ROOT/'SMOKE02_SHADOW_PLAN.json');validate_plan(p,'shadow');return p
    if NAMESPACE==PILOT:
        from src.pilot_plan import validate_pilot_template,inherited_engineering_subsets
        p=read(ROOT/'PILOT01_PLAN_TEMPLATE.json');validate_pilot_template(p)
        p.update(inherited_engineering_subsets(p));return p
    if NAMESPACE!=SMOKE:raise PermissionError('AUTHORIZATION_DENIED')
    p=read(ROOT/'SMOKE02_PLAN_TEMPLATE.json');validate_plan(p,'smoke')
    slots=p['instances']
    p['audit4']=[x['instance_id'] for x in slots if x['configuration']=={'resource_pressure':'medium','preference_conflict':'high','capability_richness':'rich','composition_depth':2} and x['seed_index']==0]
    p['rerun8']=[x['instance_id'] for x in slots if x['configuration']=={'resource_pressure':'medium','preference_conflict':'high','capability_richness':'rich','composition_depth':2}]
    p['fresh_repeat16']=[x['instance_id'] for x in slots if x['configuration']['resource_pressure'] in ('low','high') and x['configuration']['preference_conflict']=='medium' and x['configuration']['capability_richness']=='sparse' and x['seed_index']==0]
    return p
def loadinstance(iid):
    from src.instances import deserialize_instance
    raw=(OUT/'instances'/f'{iid}.json').read_bytes();x=deserialize_instance(raw.decode())
    if x.namespace!=NAMESPACE:raise ValueError('wrong instance namespace')
    manifest=read(OUT/'instances_manifest.json');expected=manifest.get(iid)
    if expected!={'sha256':sha(raw),'instance_hash':x.instance_hash,'public_hash':x.public_hash,'private_hash':x.private_hash}:
        raise ValueError('instance differs from immutable generation manifest')
    return raw,x
def inspect(iid,snap):
    if gate()!=snap:raise ValueError('snapshot mismatch')
    raw,x=loadinstance(iid);base=OUT/'main'/iid
    if not base.exists():return None
    if not (base/'COMPLETE.json').is_file():
        from src.smoke02_commit import quarantine_incomplete
        quarantine_incomplete(OUT/'main',iid,snap,gate)
        return None
    from src.smoke02_commit import inspect_complete
    def validate_instance(value):
        from src.instances import deserialize_instance
        v=deserialize_instance(value.decode());return v.instance_hash,v.namespace
    if not inspect_complete(OUT/'main',iid,x.instance_hash,snap,gate,validate_instance,namespace=NAMESPACE):return None
    payload=(base/'result.json').read_bytes(); item=json.loads(payload)
    slot=next(s for s in getplan()['instances'] if s['instance_id']==iid)
    if x.public.family!=slot['family'] or x.public.configuration!=slot['configuration'] or x.seed_label!=str(slot['seed_index']):raise ValueError('instance does not match planned identity')
    if any(r['instance_hash']!=x.instance_hash or r['public_hash']!=x.public_hash or r['private_hash']!=x.private_hash or r['namespace']!=NAMESPACE for r in item['rows']):raise ValueError('invalid paired identity')
    if item['snapshot_hash']!=snap or item['check']['ok'] is not True:raise ValueError('invalid evaluator audit')
    from src.shadow_output_validation import validate
    validate(iid,x,item,namespace=NAMESPACE)
    return item
def task(mode,ids):
    from src.fast_exact import FastLibrary
    from src.fast_runner import run_paired_fast
    from src.smoke_invariants import check_instance
    from src.instances import deserialize_instance
    snap=gate();plan=getplan();slots={s['instance_id']:s for s in plan['instances']}
    telemetry=None
    from src.phase_memory import telemetry_enabled
    if telemetry_enabled(NAMESPACE) and os.environ.get('GENSPACE_TELEMETRY_PATH'):
        from src.phase_memory import ReadOnlyTelemetry
        telemetry=ReadOnlyTelemetry(os.environ['GENSPACE_TELEMETRY_PATH'],
                     int(os.environ['GENSPACE_ORCHESTRATOR_PID']),snap,ids)
        telemetry.emit('CHILD_START',ids[0])
    if mode!='main':
        expected={'audit':'AUDIT_ARTIFACTS','rerun':'RERUN8','fresh':'FRESH_REPEAT16'}[mode]
        if read(OUT/'state.json').get('phase')!=expected:
            raise ValueError('post-main phase not authorized by persisted state')
        if not all((OUT/'main'/i/'COMPLETE.json').is_file() for i in slots):
            raise ValueError('post-main phase requires complete main')
        if mode in ('rerun','fresh') and not all((OUT/'audit'/f'{i}.npz').is_file() for i in plan['audit4']):
            raise ValueError('repeat phase requires all candidate audits')
        if mode=='fresh' and not all((OUT/'rerun'/f'{i}.json').is_file() for i in plan['rerun8']):
            raise ValueError('fresh phase requires rerun8')
        eligible={'audit':plan['audit4'],'rerun':plan['rerun8'],'fresh':plan['fresh_repeat16']}[mode]
        if len(ids)!=1 or ids[0] not in eligible:raise ValueError('invalid fresh child identity')
    lib=FastLibrary.from_graph(scope=SCOPE)
    if telemetry:telemetry.emit('BATCH_LIBRARY_READY',ids[0],metadata={'library_load':'once_per_batch'})
    for iid in ids:
        if gate()!=snap:raise ValueError('snapshot changed')
        raw,x=loadinstance(iid);checks=[]
        def observer(instance,library,evaluator,evaluation,variant):checks.append(check_instance(instance,library,evaluator,evaluation,variant))
        artifact=OUT/'audit'/f'{iid}.npz' if mode=='audit' else None
        def phase(event):
            if telemetry:
                telemetry.emit(event,iid)
                if event=='INSTANCE_START':
                    telemetry.emit('LIBRARY_READY',iid,metadata={'library_state':'already_loaded_once_per_batch'})
            if iid==os.environ.get('GENSPACE_FAULT_ID') and event=='V4_START':
                path=OUT/'hard_interrupt_event.json'
                write(path,{'instance_id':iid,'phase':event,'timestamp':time.time()})
                os._exit(93)
        rows,stages=run_paired_fast(raw.decode(),lib,candidate_layers_path=artifact,evaluation_observer=observer,phase_observer=phase)
        if len(checks)!=1 or not checks[0]['ok']:raise ValueError('independent observer failed')
        for row in rows:
            r=row['validator_rejections'];row.update(instance_id=iid,seed_index=slots[iid]['seed_index'],snapshot_hash=snap,public_eligible_count=row['candidate_count']-sum(r.get(k,0) for k in ('V1','V2','V3')))
            row.update({f'failure_{k}':r.get(k,0) for k in ('V1','V2','V3','V4','V5')})
        if gate()!=snap:raise ValueError('snapshot changed')
        data={'instance_id':iid,'instance_hash':x.instance_hash,'namespace':NAMESPACE,'ok':True,'rows':rows,'stages':stages,'check':checks[0],'snapshot_hash':snap,'snapshot_pre_verified':True,'snapshot_post_verified':True}
        from src.shadow_output_validation import validate
        validate(iid,x,data,namespace=NAMESPACE)
        if mode=='main':
            from src.smoke02_commit import commit_instance
            def validate_instance(value):
                v=deserialize_instance(value.decode());return v.instance_hash,v.namespace
            commit_instance(OUT/'main',iid,x.instance_hash,raw,data,snap,gate,validate_instance,namespace=NAMESPACE)
            if inspect(iid,snap) is None:raise ValueError('failed committed verification')
        else:write(OUT/('audit_metadata' if mode=='audit' else mode)/f'{iid}.json',data)
        if telemetry:telemetry.emit('INSTANCE_COMPLETE',iid)
    if telemetry:telemetry.emit('CHILD_PRE_EXIT',ids[-1])
def launch(mode,ids,fault_id=None):
    from src.process_lifecycle import prelaunch_guard,emergency_guard,memory_sample
    from src.windows_suspended_job import launch as start
    guard=prelaunch_guard()
    if not guard['pass']:return {'status':'PAUSED_MEMORY','guard':guard}
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','GENSPACE_RUN_ROOT':str(OUT),'GENSPACE_RUN_NAMESPACE':NAMESPACE}
    telemetry=None
    from src.phase_memory import telemetry_enabled
    if telemetry_enabled(NAMESPACE,env):
        from src.phase_memory import ReadOnlyTelemetry
        telemetry_path=OUT/'telemetry'/f'{mode}_{ids[0]}_{time.time_ns()}.jsonl'
        env['GENSPACE_TELEMETRY_PATH']=str(telemetry_path)
        env['GENSPACE_ORCHESTRATOR_PID']=str(os.getpid())
        telemetry=ReadOnlyTelemetry(telemetry_path,os.getpid(),read(OUT/'state.json')['snapshot_hash'],ids)
    def lifecycle(event,pid,metadata):
        if telemetry:telemetry.emit(event,ids[0] if event=='JOB_ASSIGNMENT' else ids[-1],worker_pid=pid,metadata=metadata)
    if SNAPSHOT_CONTEXT is not None:env['GENSPACE_SNAPSHOT_PATH']=str(SNAPSHOT_CONTEXT)
    if AUTH_CONTEXT is not None:env['GENSPACE_AUTH_PATH']=str(AUTH_CONTEXT)
    if fault_id:env['GENSPACE_FAULT_ID']=fault_id
    child=start([sys.executable,str(Path(__file__).resolve()),'--child',mode,'--ids',','.join(ids)],cwd=str(ROOT),env=env,stdout_path=str(OUT/'logs'/f'{mode}_{ids[0]}_{time.time_ns()}.log'),lifecycle_observer=lifecycle if telemetry else None)
    samples=[];peak=0;paused=False
    from tools.smoke_01 import process_memory
    while child.poll() is None:
        g=emergency_guard();samples.append(g['sample'])
        try:peak=max(peak,process_memory(child.pid)[1])
        except OSError:pass
        if not g['pass']:child.terminate();paused=True;break
        time.sleep(.2)
    life=child.finish(lifecycle_observer=lifecycle if telemetry else None);return {'status':'PAUSED_MEMORY' if paused else ('OK' if life['pass'] else 'ERROR'),'guard':guard,'samples':samples,'peak_rss':peak,'lifecycle':life,'ids':ids}
def mismatch_test():
    from unittest.mock import patch
    from src.execution_snapshot import SMOKE02_SHADOW_SNAPSHOT,verify_snapshot
    snap=gate(); iid=getplan()['instances'][0]['instance_id']
    if inspect(iid,snap) is None:raise ValueError('test requires a real committed shadow instance')
    altered=read(SMOKE02_SHADOW_SNAPSHOT);altered['source_tree_sha256']='0'*64
    with tempfile.TemporaryDirectory() as td:
        copy=Path(td)/'altered_snapshot.json';write(copy,altered)
        try:
            with patch(__name__+'.gate',side_effect=lambda:(verify_snapshot(path=copy,scope='shadow'),sha(copy.read_bytes()))[1]):
                inspect(iid,snap)
            rejected=False
        except ValueError:rejected=True
    write(OUT/'snapshot_mismatch_test.json',{'rejected':rejected,'field':'source_tree_sha256','instance_id':iid,'snapshot_sha256':snap})
    return rejected
def run(stop_after=None,namespace=SHADOW,inject=None):
    global ACTIVE_SEGMENT
    if namespace!=NAMESPACE:raise ValueError('namespace context mismatch')
    from src.shadow_plans import generate_shadow
    from src.instances import deserialize_instance
    from src.smoke02_aggregation import aggregate
    snap=gate();p=getplan();slots=p['instances'];ids=[x['instance_id'] for x in slots]
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('instances','main','audit','audit_metadata','rerun','fresh','logs','segments'): (OUT/name).mkdir(exist_ok=True)
    if not (OUT/'state.json').exists():
        if any(any((OUT/name).iterdir()) for name in ('instances','main','audit','audit_metadata','rerun','fresh','logs','segments')):
            raise ValueError('output exists without state; fail closed')
        write(OUT/'state.json',{'phase':'PLAN_CREATED','snapshot_hash':snap,'plan_sha256':sha(blob(p))})
    state=read(OUT/'state.json')
    if state['snapshot_hash']!=snap or state['plan_sha256']!=sha(blob(p)):raise ValueError('resume snapshot or plan mismatch')
    manifest_path=OUT/'instances_manifest.json'
    if not manifest_path.exists():
        if any((OUT/'instances').iterdir()):raise ValueError('instance files exist without immutable manifest')
        write(manifest_path,{});state['instances_manifest_sha256']=sha(manifest_path.read_bytes());write(OUT/'state.json',state)
    if state.get('instances_manifest_sha256')!=sha(manifest_path.read_bytes()):raise ValueError('instance manifest changed')
    for slot in slots:
        path=OUT/'instances'/f"{slot['instance_id']}.json"
        if not path.exists():
            if namespace==SHADOW: obj=generate_shadow(slot['family'],slot['configuration'],slot['seed_index'])
            else:
                from src.instances import generate_instance
                obj=generate_instance(slot['family'],slot['configuration'],slot['seed_index'],namespace=namespace)
            if obj.namespace!=NAMESPACE:raise ValueError('instance factory namespace')
            raw=obj.serialize().encode();manifest=read(manifest_path)
            record={'sha256':sha(raw),'instance_hash':obj.instance_hash,'public_hash':obj.public_hash,'private_hash':obj.private_hash}
            old=manifest.get(slot['instance_id'])
            if old is not None and old!=record:raise ValueError('regenerated missing instance differs from manifest')
            manifest[slot['instance_id']]=record;write(manifest_path,manifest);state['instances_manifest_sha256']=sha(manifest_path.read_bytes());write(OUT/'state.json',state)
            tmp=path.with_suffix('.tmp')
            if tmp.exists():
                quarantine=OUT/'interrupted_instances';quarantine.mkdir(exist_ok=True)
                os.rename(tmp,quarantine/f'{slot["instance_id"]}_{time.time_ns()}.tmp')
            with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.rename(tmp,path)
        loadinstance(slot['instance_id'])
    before={i:inspect(i,snap) for i in ids};skipped=[i for i in ids if before[i] is not None]
    for file in sorted((OUT/'segments').glob('*.json')):
        prior=read(file)
        if prior.get('status')=='PLANNED_STOP':
            for i,h in prior.get('completed_hashes',{}).items():
                if i not in skipped or sha((OUT/'main'/i/'COMPLETE.json').read_bytes())!=h['marker'] or sha((OUT/'main'/i/'result.json').read_bytes())!=h['result']:
                    raise ValueError('committed output changed since planned stop')
    segment={'start':time.time(),'snapshot_hash':snap,'validated_skips':skipped,'skip_marker_hashes':{i:sha((OUT/'main'/i/'COMPLETE.json').read_bytes()) for i in skipped},'executed':[],'jobs':[]};seg=OUT/'segments'/f"{len(list((OUT/'segments').glob('*.json'))):02d}.json"
    segment.update(status='RUNNING',planned_ids=ids);ACTIVE_SEGMENT=(seg,segment);write(seg,segment)
    for offset in range(0,len(ids),4):
        todo=[i for i in ids[offset:offset+4] if before[i] is None]
        if not todo:continue
        state['phase']='MAIN_RUNNING';write(OUT/'state.json',state)
        fault_id=None
        if inject and inject.get('hard_interrupt') and offset==inject['hard_interrupt'].get('batch_offset'):
            fault_id=todo[inject['hard_interrupt']['instance_index']]
        if inject and inject.get('pause_after_completed')==len(skipped)+len(segment['executed']):
            from src.process_lifecycle import prelaunch_guard,PRELAUNCH_FLOOR
            actual=prelaunch_guard()
            segment.update(reason='controlled_engineering_injection',simulated=True,
                           virtual_available=PRELAUNCH_FLOOR-1,virtual_policy=PRELAUNCH_FLOOR,
                           actual_prelaunch=actual)
            record_memory_pause(state,segment,seg,'MAIN_RUNNING');return False
        job=launch('main',todo,fault_id);segment['jobs'].append(job)
        write(seg,segment)
        if job['status']!='OK':
            segment['executed'].extend(i for i in todo if inspect(i,snap) is not None)
            if job['status']=='PAUSED_MEMORY':
                record_memory_pause(state,segment,seg,'MAIN_RUNNING');return False
            segment['status']='HARD_INTERRUPTED' if fault_id and (OUT/'hard_interrupt_event.json').exists() else job['status']
            segment['end']=time.time();write(seg,segment);return False
        for i in todo:
            if inspect(i,snap) is None:raise ValueError('missing completed transaction')
        segment['executed'].extend(todo)
        write(seg,segment)
        if stop_after and len(skipped)+len(segment['executed'])==stop_after:
            segment['completed_hashes']={i:{'marker':sha((OUT/'main'/i/'COMPLETE.json').read_bytes()),'result':sha((OUT/'main'/i/'result.json').read_bytes())} for i in skipped+segment['executed']}
            state['phase']='MAIN_PAUSED';write(OUT/'state.json',state);segment.update(status='PLANNED_STOP',end=time.time());write(seg,segment);return True
    main=[inspect(i,snap) for i in ids]
    if any(x is None for x in main):raise ValueError('main incomplete')
    state['phase']='MAIN_COMPLETE';write(OUT/'state.json',state)
    for mode,subset in (('audit',p['audit4']),('rerun',p['rerun8']),('fresh',p['fresh_repeat16'])):
        state['phase']={'audit':'AUDIT_ARTIFACTS','rerun':'RERUN8','fresh':'FRESH_REPEAT16'}[mode];write(OUT/'state.json',state)
        for iid in subset:
            meta=OUT/('audit_metadata' if mode=='audit' else mode)/f'{iid}.json'
            if meta.exists():
                existing=read(meta)
                if existing.get('snapshot_hash')!=snap or existing.get('instance_id')!=iid or existing.get('ok') is not True:raise ValueError('stale post-main result')
                from src.shadow_output_validation import validate
                _,obj=loadinstance(iid);validate(iid,obj,existing,namespace=NAMESPACE)
                reference=next(x for x in main if x['instance_id']==iid)
                canon=lambda rows:blob([{k:v for k,v in r.items() if k!='runtime_seconds'} for r in rows])
                if canon(existing['rows'])!=canon(reference['rows']):raise ValueError('post-main output differs from main')
                if mode=='audit':
                    if not (OUT/'audit'/f'{iid}.npz').is_file():raise ValueError('missing existing candidate audit')
                    from tools.smoke_01 import check_audit_artifacts
                    from src.execution_snapshot import SMOKE02_SHADOW_SNAPSHOT,SMOKE02_SNAPSHOT,PILOT_EXECUTABLE_SNAPSHOT
                    graph=read({'shadow':SMOKE02_SHADOW_SNAPSHOT,'smoke02':SMOKE02_SNAPSHOT,'pilot-execution':PILOT_EXECUTABLE_SNAPSHOT}[SCOPE])['semantic_library_sha256']
                    check=check_audit_artifacts(OUT/'audit',[iid],reference['rows'],graph,snap,{iid:reference['check']})
                    if not check['checks']['decoded_artifacts_match_rows']:raise ValueError('invalid existing candidate audit')
                segment.setdefault('validated_stage_skips',[]).append({'phase':mode,'instance_id':iid,'metadata_sha256':sha(meta.read_bytes())})
                continue
            if mode=='audit' and (OUT/'audit'/f'{iid}.npz').exists():
                stale=OUT/'interrupted_artifacts';stale.mkdir(exist_ok=True)
                os.rename(OUT/'audit'/f'{iid}.npz',stale/f'{iid}_{time.time_ns()}.npz')
            job=launch(mode,[iid]);segment['jobs'].append(job)
            write(seg,segment)
            if job['status']!='OK':
                if job['status']=='PAUSED_MEMORY':
                    record_memory_pause(state,segment,seg,state['phase']);return False
                segment.update(status=job['status'],end=time.time());write(seg,segment);return False
    state['phase']='AGGREGATION';write(OUT/'state.json',state)
    instances={i:deserialize_instance(loadinstance(i)[0].decode()) for i in ids};a=gate()
    from src.execution_snapshot import SMOKE02_SHADOW_SNAPSHOT,SMOKE02_SNAPSHOT,PILOT_EXECUTABLE_SNAPSHOT
    graph=read({'shadow':SMOKE02_SHADOW_SNAPSHOT,'smoke02':SMOKE02_SNAPSHOT,'pilot-execution':PILOT_EXECUTABLE_SNAPSHOT}[SCOPE])['semantic_library_sha256']
    historical=previous_segments(OUT/'segments',seg)
    alljobs=[job for previous in historical for job in previous.get('jobs',[])]+segment['jobs']
    all_exec=[i for previous in historical for i in previous.get('executed',[])]+segment['executed']
    main_done=all(inspect(i,snap) is not None for i in ids)
    job_ok=bool(alljobs) and all(explained_job(j) for j in alljobs)
    artifact_done=all((OUT/'audit'/f'{i}.npz').is_file() for i in p['audit4'])
    ev={'no_unexplained_crash':job_ok,'no_silent_skip':len(all_exec)==len(set(all_exec))==len(ids) and set(all_exec)==set(ids),
        'all_jobs_passed':job_ok,'snapshot_unchanged':gate()==snap,'all_complete_markers_valid':main_done,
        'artifact_after_main':main_done and artifact_done,'repeats_after_audit':artifact_done and all((OUT/'rerun'/f'{i}.json').is_file() for i in p['rerun8'])}
    result=aggregate(namespace=NAMESPACE,planned_ids=ids,instances=instances,main=main,rerun=[read(OUT/'rerun'/f'{i}.json') for i in p['rerun8']],fresh=[read(OUT/'fresh'/f'{i}.json') for i in p['fresh_repeat16']],audit_dir=OUT/'audit',audit_ids=p['audit4'],rerun_ids=p['rerun8'],fresh_ids=p['fresh_repeat16'],graph_hash=graph,snapshot_hash=a,execution_evidence=ev)
    write(OUT/'aggregation.json',result);state['phase']='SMOKE_COMPLETE' if result['ok'] else 'AGGREGATION';write(OUT/'state.json',state)
    segment.update(status='COMPLETE' if result['ok'] else 'FAILED',end=time.time());write(seg,segment);return result['ok']

def run_experiment(plan, namespace, execution_snapshot, authorization_state, *, output_root, stop_after=None, inject=None):
    """Shared entry; authorize before plan, instance, or seed processing."""
    global OUT,NAMESPACE,SCOPE,SNAPSHOT_CONTEXT,AUTH_CONTEXT
    from src.smoke_authorization import authorize
    authorized=authorize(namespace,snapshot_path=execution_snapshot,auth_path=authorization_state)
    if namespace!=SHADOW and inject is not None:raise ValueError('engineering fault injection requires SHADOW namespace')
    NAMESPACE=namespace;SCOPE=SCOPES.get(namespace,'denied');OUT=Path(output_root)
    SNAPSHOT_CONTEXT=str(Path(execution_snapshot).resolve());AUTH_CONTEXT=str(Path(authorization_state).resolve())
    expected=getplan()
    base={k:v for k,v in expected.items() if k not in ('audit4','rerun8','fresh_repeat16')}
    if plan!=expected and not (namespace!=SHADOW and plan==base):raise ValueError('plan mismatch')
    if authorized['snapshot_sha256']!=gate():raise ValueError('authorization context mismatch')
    return run(stop_after,namespace,inject)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--child',choices=('main','audit','rerun','fresh'));p.add_argument('--ids');p.add_argument('--stop-after',type=int);p.add_argument('--execute',action='store_true');p.add_argument('--namespace',default=SHADOW);p.add_argument('--test-mismatch',action='store_true');p.add_argument('--output-root');p.add_argument('--inject-json');a=p.parse_args()
    if a.child:task(a.child,a.ids.split(','))
    elif a.test_mismatch:raise SystemExit(0 if mismatch_test() else 1)
    elif a.execute:
        try:
            from src.smoke_authorization import authorize,AUTHORIZATION
            from src.execution_snapshot import SMOKE02_SHADOW_SNAPSHOT,SMOKE02_SNAPSHOT,PILOT_EXECUTABLE_SNAPSHOT
            NAMESPACE=a.namespace;SCOPE=SCOPES.get(NAMESPACE,'denied')
            if SCOPE=='denied':raise PermissionError('AUTHORIZATION_DENIED')
            snapshot={'shadow':SMOKE02_SHADOW_SNAPSHOT,'smoke02':SMOKE02_SNAPSHOT,'pilot-execution':PILOT_EXECUTABLE_SNAPSHOT}[SCOPE]
            auth_path=ROOT/'PILOT_AUTHORIZATION_STATE.json' if NAMESPACE==PILOT else AUTHORIZATION
            authorize(NAMESPACE,snapshot_path=snapshot,auth_path=auth_path)
            plan=getplan()
            default_out=ROOT/'results'/'pilot01' if NAMESPACE==PILOT else OUT
            completed=run_experiment(plan,NAMESPACE,snapshot,auth_path,output_root=a.output_root or default_out,stop_after=a.stop_after,inject=json.loads(a.inject_json) if a.inject_json else None)
            planned_pause=bool(ACTIVE_SEGMENT and ACTIVE_SEGMENT[1].get('status')=='PAUSED_MEMORY')
            raise SystemExit(0 if completed or planned_pause else 1)
        except Exception as exc:
            if ACTIVE_SEGMENT:
                path,data=ACTIVE_SEGMENT;data.update(status='ERROR',error=repr(exc),end=time.time());write(path,data)
            raise
    else:raise SystemExit('explicit --execute required')

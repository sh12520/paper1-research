"""Frozen-source 16-instance SHADOW-only regression after PILOT routing.

Explicit --execute only, no PILOT/CONFIRM seeds or instances. Historical
results and snapshots are read-only; all new outputs are in a separate tree.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
STAGE=ROOT/'results'/'pilot_routing_regression_staging'
HISTORICAL=ROOT/'results'/'pilot_instrumentation_staging'/'audit_runs'/'on'
SHADOW='GENSPACE-FAIL-01-ENGINEERING-SHADOW'
REQUIRED=('INSTANCE_START','LIBRARY_READY','PUBLIC_FILTER_START','PUBLIC_FILTER_END','V4_START','V4_END','V5_START','V5_END','REPRESENTATIVE_SELECTED','SERIALIZATION_START','SERIALIZATION_END','INSTANCE_COMPLETE')
FIELDS=('timestamp','instance_id','pid','process_identity','worker_rss','worker_peak_working_set','orchestrator_rss','system_used_physical','system_available_physical','execution_snapshot_hash')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')
def command(root,*args):
    env={**os.environ,'PYTHONPATH':str(root),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    for name in ('GENSPACE_RUN_ROOT','GENSPACE_RUN_NAMESPACE','GENSPACE_SNAPSHOT_PATH','GENSPACE_AUTH_PATH','GENSPACE_TELEMETRY_PATH','GENSPACE_ORCHESTRATOR_PID'):
        env.pop(name,None)
    return subprocess.run([sys.executable,*args],cwd=root,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),capture_output=True,text=True)
def source_files():
    result=[]
    for name,pattern in (('src','*.py'),('tools','*.py'),('tests','*.py'),('schemas','*')):
        result.extend(p for p in (ROOT/name).rglob(pattern) if p.is_file())
    result.extend(ROOT/name for name in ('config.yaml','SMOKE02_SHADOW_PLAN.json','SMOKE02_PLAN_TEMPLATE.json','PILOT01_PLAN_TEMPLATE.json'))
    return result
def compare_research(old,new):
    def rows(v):return [{k:x for k,x in r.items() if k not in ('runtime_seconds','snapshot_hash')} for r in v['rows']]
    return rows(old)==rows(new) and old['check']==new['check']
def check_events(ids,events,snapshot_hash):
    result=[]
    for iid in ids:
        names=[e.get('event') for e in events if e.get('instance_id')==iid and e.get('event') in REQUIRED]
        result.append({'instance_id':iid,'events':names,'pass':tuple(names)==REQUIRED})
    def valid(e):
        if not all(k in e for k in FIELDS) or e['execution_snapshot_hash']!=snapshot_hash:return False
        identity=e['process_identity']
        if not isinstance(identity,dict) or identity.get('pid')!=e['pid'] or type(identity.get('creation_time')) is not int or identity['creation_time']<=0:return False
        values=('worker_rss','worker_peak_working_set','orchestrator_rss','system_used_physical','system_available_physical')
        return (type(e['pid']) is int and e['pid']>0 and all(type(e[k]) is int and e[k]>0 for k in values)
                and e['worker_peak_working_set']>=e['worker_rss'] and type(e['timestamp']) in (int,float) and e['timestamp']>0)
    fields=bool(events) and all(valid(e) for e in events)
    return {'per_instance':result,'fields':fields,'no_errors':not any(e.get('event')=='TELEMETRY_ERROR' for e in events),
            'pass':len(result)==16 and all(r['pass'] for r in result) and fields and not any(e.get('event')=='TELEMETRY_ERROR' for e in events)}
def prepare():
    if STAGE.exists():raise FileExistsError('refusing to overwrite existing staging evidence')
    STAGE.mkdir(parents=True)
    for name in ('src','tools','tests','schemas'):shutil.copytree(ROOT/name,STAGE/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('config.yaml','SMOKE02_SHADOW_PLAN.json','SMOKE02_PLAN_TEMPLATE.json','PILOT01_PLAN_TEMPLATE.json'):shutil.copy2(ROOT/name,STAGE/name)
    target=STAGE/'results'/'engineering';target.mkdir(parents=True)
    shutil.copy2(ROOT/'results/engineering/semantic_library.graph.gz',target)
    shutil.copytree(ROOT/'results/engineering/availability_indices',target/'availability_indices')
    (target/'external_full_depth2_cached_01').mkdir()
    shutil.copy2(ROOT/'results/engineering/external_full_depth2_cached_01/report.json',target/'external_full_depth2_cached_01/report.json')
    for p in source_files():
        if sha(p)!=sha(STAGE/p.relative_to(ROOT)):raise ValueError('staging source mismatch: '+str(p))
    for scope in ('shadow','smoke02'):
        p=command(STAGE,'-m','src.execution_snapshot','--scope',scope,'--write')
        if p.returncode:raise RuntimeError('snapshot: '+p.stderr)
    p=command(STAGE,'-c','from src.smoke_authorization import write_authorization;write_authorization()')
    if p.returncode:raise RuntimeError('isolated shadow authorization: '+p.stderr)
    out=STAGE/'audit_run'
    for name in ('instances','main','logs','telemetry'): (out/name).mkdir(parents=True,exist_ok=True)
    from src.instances import deserialize_instance
    plan=json.loads((ROOT/'SMOKE02_SHADOW_PLAN.json').read_text(encoding='utf8')); manifest={}
    from src.shadow_plans import validate_plan
    validate_plan(plan,'shadow')
    for slot in plan['instances']:
        iid=slot['instance_id']; raw=(HISTORICAL/'instances'/(iid+'.json')).read_bytes(); x=deserialize_instance(raw.decode())
        if x.namespace!=SHADOW or x.public.family!=slot['family'] or x.public.configuration!=slot['configuration'] or x.seed_label!=str(slot['seed_index']):raise ValueError('historical instance mismatch')
        (out/'instances'/(iid+'.json')).write_bytes(raw)
        manifest[iid]={'sha256':hashlib.sha256(raw).hexdigest(),'instance_hash':x.instance_hash,'public_hash':x.public_hash,'private_hash':x.private_hash}
    write(out/'instances_manifest.json',manifest)
    write(out/'state.json',{'phase':'PLAN_CREATED','snapshot_hash':sha(STAGE/'SMOKE02_SHADOW_EXECUTION_SNAPSHOT_FINGERPRINT.json')})
    write(STAGE/'staging_manifest.json',{'source_count':len(source_files()),'source_equal':True,'fixture_count':len(manifest)})
def in_stage():
    import src.experiment_orchestrator as orch
    from src.smoke_authorization import authorize
    from src.shadow_plans import shadow_plan
    snap=authorize(SHADOW)['snapshot_sha256'];ids=[x['instance_id'] for x in shadow_plan()['instances']]
    os.environ['GENSPACE_TELEMETRY']='on';orch.OUT=ROOT/'audit_run';orch.NAMESPACE=SHADOW;orch.SCOPE='shadow'
    jobs=[]
    for start in range(0,16,4):
        pending=ids[start:start+4]
        while pending:
            job=orch.launch('main',pending);jobs.append(job);write(ROOT/'audit_jobs.json',jobs)
            if job['status']=='OK':break
            if job['status']!='PAUSED_MEMORY':raise RuntimeError('batch failed '+repr(job))
            time.sleep(5)
            if authorize(SHADOW)['snapshot_sha256']!=snap:raise ValueError('snapshot changed')
            pending=[iid for iid in pending if orch.inspect(iid,snap) is None]
    results=[orch.inspect(iid,snap) for iid in ids]
    if any(x is None for x in results):raise ValueError('missing committed result')
    write(ROOT/'in_stage_complete.json',{'snapshot_sha256':snap,'complete':len(results),'jobs':jobs})
def evaluate():
    plan=json.loads((ROOT/'SMOKE02_SHADOW_PLAN.json').read_text(encoding='utf8'));ids=[s['instance_id'] for s in plan['instances']]
    actual=STAGE/'audit_run'; info=json.loads((STAGE/'in_stage_complete.json').read_text(encoding='utf8')); snap=info['snapshot_sha256']
    comparisons=[]
    for iid in ids:
        old=json.loads((HISTORICAL/'main'/iid/'result.json').read_bytes());new=json.loads((actual/'main'/iid/'result.json').read_bytes())
        comparisons.append({'instance_id':iid,'pass':compare_research(old,new)})
    event_files=sorted((actual/'telemetry').glob('*.jsonl')); events=[]; batches=[]
    for file in event_files:
        rows=[json.loads(line) for line in file.read_text(encoding='utf8').splitlines() if line.strip()];events.extend(rows)
        names=[e.get('event') for e in rows]
        assignment=next((e for e in rows if e.get('event')=='JOB_ASSIGNMENT'),{})
        done=next((e for e in rows if e.get('event')=='JOB_COMPLETE'),{})
        good=(all(names.count(n)==1 for n in ('JOB_ASSIGNMENT','CHILD_START','CHILD_PRE_EXIT','JOB_COMPLETE'))
          and names.index('JOB_ASSIGNMENT')<names.index('CHILD_START')<names.index('CHILD_PRE_EXIT')<names.index('JOB_COMPLETE')
          and assignment.get('lifecycle',{}).get('assignment_verified') is True
          and assignment.get('lifecycle',{}).get('create_suspended') is True
          and done.get('lifecycle',{}).get('job_accounting',{}).get('active_processes')==0)
        times=[e.get('timestamp',0) for e in rows]
        identities=[e.get('process_identity') for e in rows]
        good=good and times==sorted(times) and all(v==identities[0] for v in identities)
        batches.append({'file':file.name,'pass':good})
    events_check=check_events(ids,events,snap)
    passed=(len(comparisons)==16 and all(x['pass'] for x in comparisons) and events_check['pass'] and len(batches)==4 and all(x['pass'] for x in batches)
            and all(j['status']=='PAUSED_MEMORY' or j.get('lifecycle',{}).get('pass') is True for j in info['jobs']))
    output={'pass':passed,'matched':sum(x['pass'] for x in comparisons),'comparisons':comparisons,'events':events_check,'event_count':len(events),'batches':batches,'snapshot_sha256':snap}
    write(STAGE/'audit_report.json',output)
    return output
def execute():
    prepare(); p=command(STAGE,'-m','tools.pilot_routing_shadow_regression','--in-stage')
    write(STAGE/'stage_process.json',{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode:raise RuntimeError('stage failed: '+p.stderr[-2000:])
    output=evaluate();print('PILOT routing SHADOW 16/16 regression:', 'PASS' if output['pass'] else 'FAIL',flush=True)
    return output['pass']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--in-stage',action='store_true');a=p.parse_args()
    if a.in_stage:in_stage()
    elif a.execute:raise SystemExit(0 if execute() else 1)
    else:raise SystemExit('explicit --execute required')

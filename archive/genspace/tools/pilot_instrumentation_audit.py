"""Isolated SHADOW-only observational telemetry audit, explicit execution only.

Copies byte-identical source/config and immutable graph/index artifacts into a
separate staging tree. Reads existing SHADOW fixtures; never reads SMOKE data
or derives PILOT/CONFIRM seeds. Does not modify historical snapshots.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
STAGE=ROOT/'results'/'pilot_instrumentation_staging'
ORIGINAL=ROOT/'results'/'smoke02_shadow'/'instances'
REPORT=ROOT/'PILOT_INSTRUMENTATION_EQUIVALENCE_REPORT.md'
SHADOW='GENSPACE-FAIL-01-ENGINEERING-SHADOW'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf8')
def cmd(root,*args):
    env={**os.environ,'PYTHONPATH':str(root),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    return subprocess.run([sys.executable,*args],cwd=root,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),capture_output=True,text=True)

def source_files():
    files=[]
    for name,pattern in (('src','*.py'),('tools','*.py'),('tests','*.py'),('schemas','*')):
        files += [p for p in (ROOT/name).rglob(pattern) if p.is_file()]
    return files+[ROOT/'config.yaml',ROOT/'SMOKE02_SHADOW_PLAN.json',ROOT/'SMOKE02_PLAN_TEMPLATE.json']

def verify_staging():
    mismatch=[p.relative_to(ROOT).as_posix() for p in source_files() if not (STAGE/p.relative_to(ROOT)).is_file() or sha(p)!=sha(STAGE/p.relative_to(ROOT))]
    for name in ('results/engineering/semantic_library.graph.gz','results/engineering/external_full_depth2_cached_01/report.json'):
        if sha(ROOT/name)!=sha(STAGE/name):mismatch.append(name)
    folder=ROOT/'results'/'engineering'/'availability_indices'
    for p in folder.iterdir():
        if p.is_file() and sha(p)!=sha(STAGE/p.relative_to(ROOT)):mismatch.append(p.relative_to(ROOT).as_posix())
    if mismatch:raise ValueError('staging is stale or differs: '+repr(mismatch))

def prepare():
    if STAGE.exists():raise FileExistsError('staging already exists; preserve evidence')
    STAGE.mkdir(parents=True)
    ignored=shutil.ignore_patterns('__pycache__','*.pyc')
    for name in ('src','tools','tests','schemas'):shutil.copytree(ROOT/name,STAGE/name,ignore=ignored)
    for name in ('config.yaml','SMOKE02_SHADOW_PLAN.json','SMOKE02_PLAN_TEMPLATE.json'):
        shutil.copy2(ROOT/name,STAGE/name)
    target=STAGE/'results'/'engineering';target.mkdir(parents=True)
    shutil.copy2(ROOT/'results'/'engineering'/'semantic_library.graph.gz',target)
    shutil.copytree(ROOT/'results'/'engineering'/'availability_indices',target/'availability_indices')
    (target/'external_full_depth2_cached_01').mkdir()
    shutil.copy2(ROOT/'results'/'engineering'/'external_full_depth2_cached_01'/'report.json',target/'external_full_depth2_cached_01'/'report.json')
    graph_original=ROOT/'results'/'engineering'/'semantic_library.graph.gz'
    if sha(graph_original)!=sha(target/'semantic_library.graph.gz'):raise ValueError('staged semantic graph differs')
    indices=ROOT/'results'/'engineering'/'availability_indices'
    for source in indices.iterdir():
        if source.is_file() and sha(source)!=sha(target/'availability_indices'/source.name):raise ValueError('staged index differs')
    # Every fingerprinted file is compared byte-for-byte, including schema.
    files=source_files()
    mismatch=[p.relative_to(ROOT).as_posix() for p in files if sha(p)!=sha(STAGE/p.relative_to(ROOT))]
    if mismatch:raise ValueError('staging source mismatch: '+repr(mismatch))
    p=cmd(STAGE,'-m','src.execution_snapshot','--scope','shadow','--write')
    if p.returncode:raise RuntimeError('shadow snapshot '+p.stderr)
    p=cmd(STAGE,'-m','src.execution_snapshot','--scope','smoke02','--write')
    if p.returncode:raise RuntimeError('formal snapshot '+p.stderr)
    p=cmd(STAGE,'-c','from src.smoke_authorization import write_authorization;write_authorization()')
    if p.returncode:raise RuntimeError('isolated authorization '+p.stderr)
    # No source fixture, model, graph or index is ever modified.
    plan=json.loads((ROOT/'SMOKE02_SHADOW_PLAN.json').read_text(encoding='utf8'))
    if len(plan['instances'])!=16:raise ValueError('incorrect shadow plan')
    for mode in ('off','on'):
        out=STAGE/'audit_runs'/mode
        for part in ('instances','main','logs','telemetry'): (out/part).mkdir(parents=True,exist_ok=True)
        manifest={}
        sys.path.insert(0,str(STAGE))
        from src.instances import deserialize_instance
        for slot in plan['instances']:
            iid=slot['instance_id'];raw=(ORIGINAL/(iid+'.json')).read_bytes();obj=deserialize_instance(raw.decode())
            if obj.namespace!=SHADOW or obj.public.family!=slot['family'] or obj.public.configuration!=slot['configuration'] or obj.seed_label!=str(slot['seed_index']):raise ValueError('fixture mismatch')
            (out/'instances'/(iid+'.json')).write_bytes(raw)
            manifest[iid]={'sha256':hashlib.sha256(raw).hexdigest(),'instance_hash':obj.instance_hash,'public_hash':obj.public_hash,'private_hash':obj.private_hash}
        write(out/'instances_manifest.json',manifest)
        write(out/'state.json',{'phase':'PLAN_CREATED','snapshot_hash':sha(STAGE/'SMOKE02_SHADOW_EXECUTION_SNAPSHOT_FINGERPRINT.json')})
    write(STAGE/'staging_manifest.json',{'source_file_count':len(files),'source_equal':not mismatch,'namespace':SHADOW,'fixtures':16,'shadow_snapshot_sha256':sha(STAGE/'SMOKE02_SHADOW_EXECUTION_SNAPSHOT_FINGERPRINT.json')})

def in_stage():
    # Runs under the clone interpreter imports; do not import workspace modules.
    import src.experiment_orchestrator as orch
    from src.execution_snapshot import verify_snapshot,SMOKE02_SHADOW_SNAPSHOT
    from src.smoke_authorization import authorize
    from src.shadow_plans import shadow_plan
    snap=authorize(SHADOW)['snapshot_sha256'];verify_snapshot(path=SMOKE02_SHADOW_SNAPSHOT,scope='shadow')
    ids=[x['instance_id'] for x in shadow_plan()['instances']]
    results={}
    for mode in ('off','on'):
        os.environ['GENSPACE_TELEMETRY']=mode
        orch.OUT=ROOT/'audit_runs'/mode;orch.NAMESPACE=SHADOW;orch.SCOPE='shadow'
        jobfile=ROOT/'audit_runs'/f'{mode}_jobs.json'
        jobs=json.loads(jobfile.read_text(encoding='utf8')) if jobfile.exists() else []
        for start in range(0,16,4):
            todo=[iid for iid in ids[start:start+4] if orch.inspect(iid,snap) is None]
            if not todo:continue
            while True:
                job=orch.launch('main',todo);jobs.append(job);write(jobfile,jobs)
                if job.get('status')=='OK':break
                if job.get('status')!='PAUSED_MEMORY':raise RuntimeError(mode+' batch incomplete: '+str(job.get('status')))
                print(mode,'memory pause; preserving verified transactions',flush=True)
                # Safe pauses never lower the production guards. Re-check each
                # already committed item before a subsequent launch.
                time.sleep(5)
                if authorize(SHADOW)['snapshot_sha256']!=snap:raise ValueError('snapshot changed during pause')
                todo=[iid for iid in ids[start:start+4] if orch.inspect(iid,snap) is None]
                if not todo:break
        verified=[orch.inspect(iid,snap) for iid in ids]
        if any(x is None for x in verified):raise ValueError('missing complete transaction')
        results[mode]=verified;write(ROOT/'audit_runs'/f'{mode}_jobs.json',jobs)
    excluded={'runtime_seconds'}
    def scientific(item):return [{k:v for k,v in row.items() if k not in excluded} for row in item['rows']]
    comparison=[{'instance_id':iid,'method_fields_equal':scientific(a)==scientific(b),'validator_equal':a['check']==b['check']} for iid,a,b in zip(ids,results['off'],results['on'])]
    equal=all(x['method_fields_equal'] and x['validator_equal'] for x in comparison)
    required=('INSTANCE_START','LIBRARY_READY','PUBLIC_FILTER_START','PUBLIC_FILTER_END','V4_START','V4_END','V5_START','V5_END','REPRESENTATIVE_SELECTED','SERIALIZATION_START','SERIALIZATION_END','INSTANCE_COMPLETE')
    fields=('timestamp_ns','instance_id','pid','process_identity','worker_rss','worker_peak_rss','orchestrator_rss','system_used_physical','system_available_physical','execution_snapshot_hash')
    files=sorted((ROOT/'audit_runs'/'on'/'telemetry').glob('*.jsonl')); events=[];batch=[]
    for f in files:
        rows=[json.loads(line) for line in f.read_text(encoding='utf8').splitlines() if line.strip()];events.extend(rows)
        names=[x.get('event') for x in rows]
        assignment=[x for x in rows if x.get('event')=='JOB_ASSIGNMENT']
        finished=[x for x in rows if x.get('event')=='JOB_COMPLETE']
        lifecycle=(all(names.count(x)==1 for x in ('JOB_ASSIGNMENT','CHILD_START','CHILD_PRE_EXIT','JOB_COMPLETE'))
                   and len(assignment)==1 and assignment[0].get('lifecycle',{}).get('assignment_verified') is True
                   and len(finished)==1 and finished[0].get('lifecycle',{}).get('job_accounting',{}).get('active_processes')==0
                   and names.index('JOB_ASSIGNMENT')<names.index('CHILD_START')<names.index('CHILD_PRE_EXIT')<names.index('JOB_COMPLETE'))
        batch.append({'file':f.name,'pass':bool(lifecycle)})
    per=[]
    for iid in ids:
        rows=[x for x in events if x.get('instance_id')==iid and x.get('event') in required]
        names=[x['event'] for x in rows]
        per.append({'instance_id':iid,'events':names,'complete':tuple(names)==required})
    telemetry_fields=bool(events) and all(all(k in e for k in fields) and e['execution_snapshot_hash']==snap for e in events)
    no_errors=not any(e.get('event')=='TELEMETRY_ERROR' for e in events)
    event_pass=len(per)==16 and all(x['complete'] for x in per) and telemetry_fields and no_errors
    job_pass=len(batch)==4 and all(x['pass'] for x in batch)
    result={'snapshot_sha256':snap,'total':16,'equal_count':sum(x['method_fields_equal'] and x['validator_equal'] for x in comparison),'outputs_equal':equal,'phase_events_complete':event_pass,'event_fields_complete':telemetry_fields,'no_telemetry_errors':no_errors,'job_telemetry_complete':job_pass,'batch':batch,'per_instance':per,'instances':comparison}
    result['pass']=equal and event_pass and job_pass
    write(ROOT/'audit_runs'/'comparison.json',result)
    if not result['pass']:raise RuntimeError('ON/OFF equality or telemetry completeness failed')
    print('16/16 ON/OFF equality, phase events and Job telemetry PASS')

def execute(resume=False):
    if resume:
        if not (STAGE/'staging_manifest.json').is_file():raise ValueError('staging is incomplete')
        verify_staging()
    else:prepare()
    p=cmd(STAGE,'-m','tools.pilot_instrumentation_audit','--in-stage')
    write(STAGE/'stage_process.json',{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    if p.returncode:
        REPORT.write_text('# PILOT instrumentation equivalence\n\nBLOCKED. See results/pilot_instrumentation_staging/stage_process.json.\n',encoding='utf8')
        raise RuntimeError('staging audit failed: '+p.stderr[-1500:])
    data=json.loads((STAGE/'audit_runs'/'comparison.json').read_text(encoding='utf8'))
    REPORT.write_text('# PILOT instrumentation equivalence\n\nPASS: 16/16 existing SHADOW inputs produced identical non-timing B0/B1/B2/O1 fields and validator data with instrumentation OFF and ON. All applicable per-instance phase events and all four batch lifecycle event sets were recorded with required fields.\n\nStaging uses byte-identical source/config/plan and verified graph/indices in an isolated tree; historical SMOKE files and snapshots were not modified. See `results/pilot_instrumentation_staging/audit_runs/comparison.json`.\n',encoding='utf8')
    print(p.stdout.strip())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--in-stage',action='store_true');a=p.parse_args()
    if a.in_stage:in_stage()
    elif a.execute:execute(a.resume)
    else:raise SystemExit('explicit --execute required')

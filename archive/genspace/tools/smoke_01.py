"""SMOKE-01 driver. Does nothing unless explicitly executed after all gates.

Only GENSPACE-FAIL-01-SMOKE instances may be generated. This driver never
constructs or reads PILOT/CONFIRM seed values. Results are implementation
checks, not evidence of research success or failure.
"""
from __future__ import annotations
import argparse,csv,ctypes,hashlib,itertools,json,math,os,statistics,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'results'/'smoke'
NAMESPACE='GENSPACE-FAIL-01-SMOKE'
METHODS=('B0','B1','B2','O1')
FAMILIES=('F1','F2','F3','F4')
PRESSURES=('low','medium','high')
CONFLICTS=('medium','high')
RICHNESS=('sparse','rich')
DEPTHS=(1,2)
SEEDS=(0,1)
RUN_STARTED=False


def planned():
    for family,pressure,conflict,richness,depth,seed in itertools.product(FAMILIES,PRESSURES,CONFLICTS,RICHNESS,DEPTHS,SEEDS):
        config={'resource_pressure':pressure,'preference_conflict':conflict,
                'capability_richness':richness,'composition_depth':depth}
        iid=f'{family}__{pressure}__{conflict}__{richness}__d{depth}__s{seed}'
        yield {'instance_id':iid,'family':family,'configuration':config,'seed_index':seed}


def rerun_subset():
    return [x['instance_id'] for x in planned() if x['configuration']=={
      'resource_pressure':'medium','preference_conflict':'high','capability_richness':'rich','composition_depth':2}]


def parallel_subset():
    return [x['instance_id'] for x in planned() if x['configuration']['resource_pressure'] in ('low','high')
      and x['configuration']['preference_conflict']=='medium' and x['configuration']['capability_richness']=='sparse'
      and x['seed_index']==0]


def audit_subset():
    return [x['instance_id'] for x in planned() if x['configuration']=={
      'resource_pressure':'medium','preference_conflict':'high','capability_richness':'rich','composition_depth':2}
      and x['seed_index']==0]


def canonical_rows(rows):
    """Keep every scientific/output field; exclude only non-deterministic timing."""
    return json.dumps([{k:v for k,v in row.items() if k!='runtime_seconds'} for row in rows],
                      sort_keys=True,separators=(',',':'),allow_nan=False)


def write_json(path,obj):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8');os.replace(temp,path)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def worker(phase,worker_id,workers):
    # Only pre-existing serialized SMOKE inputs are read by any child process.
    from src.fast_exact import FastLibrary
    from src.fast_runner import run_paired_fast
    from src.instances import deserialize_instance
    from src.smoke_invariants import check_instance
    from src.execution_snapshot import SMOKE_SNAPSHOT,verify_snapshot
    library=FastLibrary.from_graph(scope='smoke'); expected_snapshot_sha=sha(SMOKE_SNAPSHOT)
    tasks=json.loads((OUT/'plan.json').read_text(encoding='utf8'))
    selected={'main':[x['instance_id'] for x in tasks], 'rerun':rerun_subset(),
              'parallel1':parallel_subset(), 'parallel2':parallel_subset()}[phase]
    target=OUT/'partial'/phase;target.mkdir(parents=True,exist_ok=True)
    for index,iid in enumerate(selected):
        if index%workers!=worker_id:continue
        path=target/(iid+'.json')
        if path.exists():raise FileExistsError(path)
        pre_verified=post_verified=False
        try:
            pre_verified=(sha(SMOKE_SNAPSHOT)==expected_snapshot_sha and verify_snapshot(path=SMOKE_SNAPSHOT,scope='smoke')==library.snapshot)
            if not pre_verified:raise ValueError('pre-instance execution snapshot mismatch')
            text=(OUT/'instances'/(iid+'.json')).read_text(encoding='utf8')
            inst=deserialize_instance(text)
            if inst.namespace!=NAMESPACE:raise ValueError('namespace mismatch')
            task=next(x for x in tasks if x['instance_id']==iid)
            if (inst.instance_hash!=task['instance_hash'] or inst.public_hash!=task['public_hash']
                or inst.private_hash!=task['private_hash']):raise ValueError('serialized instance differs from frozen plan hashes')
            checks=[]
            def observer(instance,lib,evaluator,evaluation,variant):
                if phase=='main':checks.append(check_instance(instance,lib,evaluator,evaluation,variant))
            audit=OUT/'audit_artifacts'/(iid+'.npz') if phase=='main' and iid in set(audit_subset()) else None
            rows,stages=run_paired_fast(text,library,candidate_layers_path=audit,evaluation_observer=observer)
            if len(rows)!=4 or {r['method'] for r in rows}!=set(METHODS):raise ValueError('method rows incomplete')
            if phase=='main' and len(checks)!=1:raise ValueError('invariant observer not invoked exactly once')
            seed_index=next(x['seed_index'] for x in tasks if x['instance_id']==iid)
            for row in rows:
                rejected=row['validator_rejections']
                row.update(instance_id=iid,seed_index=seed_index,smoke_snapshot_sha256=expected_snapshot_sha,
                    source_tree_sha256=library.snapshot['source_tree_sha256'],
                    graph_sha256=library.snapshot['semantic_library_sha256'],
                    availability_manifest_sha256=library.snapshot['availability_manifest_sha256'],
                    public_eligible_count=row['candidate_count']-sum(rejected.get(x,0) for x in ('V1','V2','V3')))
                row.update({f'failure_{x}':rejected.get(x,0) for x in ('V1','V2','V3','V4','V5')})
            post_verified=(sha(SMOKE_SNAPSHOT)==expected_snapshot_sha and verify_snapshot(path=SMOKE_SNAPSHOT,scope='smoke')==library.snapshot)
            if not post_verified:raise ValueError('post-instance execution snapshot mismatch')
            result={'instance_id':iid,'phase':phase,'instance_hash':inst.instance_hash,'rows':rows,
                    'stages':stages,'check':checks[0] if checks else None,'ok':True,
                    'snapshot_pre_verified':pre_verified,'snapshot_post_verified':post_verified}

        except Exception as exc:
            result={'instance_id':iid,'phase':phase,'ok':False,'error':str(exc),'traceback':traceback.format_exc(),
                    'snapshot_pre_verified':pre_verified,'snapshot_post_verified':post_verified}
        write_json(path,result)
        print(phase,worker_id,iid,'ok',result['ok'],flush=True)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total_phys',ctypes.c_ulonglong),('avail_phys',ctypes.c_ulonglong),('total_page',ctypes.c_ulonglong),('avail_page',ctypes.c_ulonglong),('total_virtual',ctypes.c_ulonglong),('avail_virtual',ctypes.c_ulonglong),('avail_extended',ctypes.c_ulonglong)]


def memory_status():
    m=MEMORYSTATUSEX();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise OSError('GlobalMemoryStatusEx')
    return int(m.total_phys),int(m.avail_phys)


def available_memory():return memory_status()[1]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]


def process_memory(pid):
    k=ctypes.windll.kernel32;p=ctypes.windll.psapi
    k.OpenProcess.argtypes=(ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong);k.OpenProcess.restype=ctypes.c_void_p
    k.CloseHandle.argtypes=(ctypes.c_void_p,);p.GetProcessMemoryInfo.argtypes=(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong)
    handle=k.OpenProcess(0x1000|0x10,False,pid)
    if not handle:raise OSError('OpenProcess failed')
    try:
        m=PROCESS_MEMORY_COUNTERS();m.cb=ctypes.sizeof(m)
        if not p.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):raise OSError('GetProcessMemoryInfo')
        return int(m.WorkingSetSize),int(m.PeakWorkingSetSize)
    finally:k.CloseHandle(handle)



def run_phase(phase,workers):
    if workers not in (1,2):raise ValueError('unsupported worker count')
    logdir=OUT/'logs';logdir.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0);children=[];logs=[];start=time.perf_counter();memory_abort=False
    peak_process=peak_worker_sum=peak_system_used=0;memory_samples=0
    try:
        for i in range(workers):
            log=(logdir/f'{phase}_{i}.log').open('x',encoding='utf8');logs.append(log)
            children.append(subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',phase,'--worker-id',str(i),'--workers',str(workers)],cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,creationflags=flags,env=env))
        while any(p.poll() is None for p in children):
            total,available=memory_status();peak_system_used=max(peak_system_used,total-available);memory_samples+=1
            live=[]
            for proc in children:
                if proc.poll() is None:
                    try:live.append(process_memory(proc.pid))
                    except OSError:pass
            if live:
                peak_process=max(peak_process,max(x[1] for x in live));peak_worker_sum=max(peak_worker_sum,sum(x[0] for x in live))
            if available<768*1024**2:
                memory_abort=True
                for p in children:
                    if p.poll() is None:p.terminate()
                break
            time.sleep(1)
        for p in children:p.wait()
    finally:
        for p in children:
            if p.poll() is None:p.terminate();p.wait()
        for stream in logs:stream.close()
    return {'phase':phase,'workers':workers,'returncodes':[p.returncode for p in children],
            'memory_abort':memory_abort,'seconds':time.perf_counter()-start,
            'peak_process_rss_bytes':peak_process,'peak_aggregate_worker_rss_sample_bytes':peak_worker_sum,
            'peak_system_physical_used_sample_bytes':peak_system_used,'memory_samples':memory_samples}


def read_phase(phase):
    directory=OUT/'partial'/phase
    if not directory.exists():return []
    return [json.loads(p.read_text(encoding='utf8')) for p in sorted(directory.glob('*.json'))]


def persist_csv(path,rows):
    keys=sorted({k for row in rows for k in row})
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})


def check_audit_artifacts(directory, expected_ids, rows, graph_hash, snapshot_hash, validations):
    """Require the exact four NPZ artifacts and verify decoded counts/identity."""
    import numpy as np
    from src.stage_report import CODES
    directory=Path(directory);expected=set(expected_ids)
    files={p.name for p in directory.iterdir() if p.is_file()}
    actual={name[:-4] for name in files if name.endswith('.npz')}
    checks={'exact_artifact_set':files=={iid+'.npz' for iid in expected},'decoded_artifacts_match_rows':True}
    errors=[];hashes={}
    byid={iid:{r['method']:r for r in rows if r.get('instance_id')==iid} for iid in expected}
    for iid in sorted(expected & actual):
        try:
            path=directory/(iid+'.npz');hashes[iid]=sha(path)
            with np.load(path,allow_pickle=False) as data:
                layers=data['layers'];metadata=json.loads(data['metadata_json'].item())
                group=byid[iid]
                if set(group)!=set(METHODS):raise ValueError('missing method rows')
                if layers.dtype!=np.uint8 or layers.shape!=(1394064,) or not bool(np.all(np.isin(layers,list(CODES.values())))):
                    raise ValueError('invalid layer array or unknown code')
                if (metadata.get('format')!='GENSPACE-CLASS-LAYERS-v1'
                    or metadata.get('instance_id')!=iid
                    or metadata.get('graph_sha256')!=graph_hash or metadata.get('snapshot_sha256')!=snapshot_hash
                    or metadata.get('instance_hash')!=group['O1']['instance_hash'] or metadata.get('codes')!=CODES):
                    raise ValueError('artifact identity mismatch')
                expected_layer_hash=(validations.get(iid) or {}).get('counts',{}).get('first_failure_layer_sha256')
                if hashlib.sha256(layers.tobytes()).hexdigest()!=expected_layer_hash:
                    raise ValueError('per-class layer bytes differ from observer')
                o1=group['O1'];rejection=o1['validator_rejections']
                for name in ('V1','V2','V3','V4','V5'):
                    if int(np.count_nonzero(layers==CODES[name+'_FAILED']))!=rejection.get(name,0):
                        raise ValueError('O1 '+name+' count mismatch')
                if int(np.count_nonzero(layers==CODES['VERIFIED']))!=o1['verified_count']:
                    raise ValueError('O1 verified count mismatch')
                if int(np.count_nonzero(layers==CODES['NOT_GENERATED']))!=o1['not_generated_count']:
                    raise ValueError('O1 not-generated count mismatch')
                if len(layers)-int(np.count_nonzero(layers==CODES['OUT_OF_DEPTH']))!=o1['rich_graph_in_domain_count']:
                    raise ValueError('O1 depth-domain count mismatch')
                baseline=metadata.get('baseline_candidate_layers',{})
                if set(baseline)!={'B0','B1','B2'}:raise ValueError('baseline layers missing')
                for method,records in baseline.items():
                    if len(records)!=group[method]['candidate_count']:raise ValueError(method+' candidate count mismatch')
                    if (any(not isinstance(record,dict) or set(record)!={'candidate','first_failure_layer','reason'}
                            or record['first_failure_layer'] not in ('V1','V2','V3','V4','V5','VERIFIED')
                            or not isinstance(record['candidate'],str) or not isinstance(record['reason'],str) for record in records)
                        or len({record['candidate'] for record in records})!=len(records)):
                        raise ValueError(method+' invalid/duplicate baseline artifact records')
                    counts={name:sum(record['first_failure_layer']==name for record in records)
                            for name in ('V1','V2','V3','V4','V5','VERIFIED')}
                    if counts['VERIFIED']!=group[method]['verified_count']:raise ValueError(method+' verified count mismatch')
                    if any(counts[name]!=group[method]['validator_rejections'].get(name,0) for name in ('V1','V2','V3','V4','V5')):
                        raise ValueError(method+' rejection count mismatch')
        except Exception as exc:
            checks['decoded_artifacts_match_rows']=False;errors.append({'instance_id':iid,'error':str(exc)})
    return {'ok':all(checks.values()),'checks':checks,'expected_count':len(expected),'observed_count':len(actual),'sha256':hashes,'errors':errors}


def runtime_stats(values):
    values=sorted(v for v in values if v is not None)
    if not values:return {'median_seconds':None,'p95_seconds':None,'max_seconds':None}
    pos=(len(values)-1)*.95;a=int(pos);b=min(a+1,len(values)-1)
    return {'median_seconds':statistics.median(values),'p95_seconds':values[a]+(values[b]-values[a])*(pos-a),'max_seconds':values[-1]}


def mean_present(values):
    a=[v for v in values if v is not None]
    return statistics.mean(a) if a else None


def summaries(rows):
    method=[]
    for name in METHODS:
        g=[r for r in rows if r['method']==name]
        method.append({'method':name,'instances':len(g),'agreements':sum(bool(r['agreement']) for r in g),
                       'deadlocks':len(g)-sum(bool(r['agreement']) for r in g),
                       **runtime_stats([r.get('runtime_seconds') for r in g]),
                       'mean_runtime_seconds':mean_present([r.get('runtime_seconds') for r in g])})
    config=[]
    for item in planned():
        if item['seed_index']!=0:continue
        group=[r for r in rows if r['family']==item['family'] and r['configuration']==item['configuration']]
        for name in METHODS:
            g=[r for r in group if r['method']==name]
            config.append({'family':item['family'],**item['configuration'],'method':name,'instances':len(g),
                           'agreements':sum(bool(r['agreement']) for r in g),
                               'deadlocks':len(g)-sum(bool(r['agreement']) for r in g),
                           **runtime_stats([r.get('runtime_seconds') for r in g])})
    family=[]
    for fam in FAMILIES:
        for name in METHODS:
            g=[r for r in rows if r['family']==fam and r['method']==name]
            family.append({'family':fam,'method':name,'instances':len(g),'agreements':sum(bool(r['agreement']) for r in g),
                               'deadlocks':len(g)-sum(bool(r['agreement']) for r in g),
                           **runtime_stats([r.get('runtime_seconds') for r in g]),
                           'mean_candidate_count':mean_present([r.get('candidate_count') for r in g]),
                           'mean_runtime_seconds':mean_present([r.get('runtime_seconds') for r in g])})
    return method,config,family


def execute():
    global RUN_STARTED
    from src.instances import generate_instance,derive_seed,deserialize_instance
    from src.execution_snapshot import SMOKE_SNAPSHOT,verify_snapshot
    from src.smoke_invariants import check_rows,check_repeats,check_snapshot_unchanged,check_execution_status
    prereg_path=ROOT/'SMOKE_PREREGISTRATION.md'
    if not prereg_path.is_file():raise RuntimeError('missing SMOKE preregistration')
    prereg_sha=sha(prereg_path)
    snapshot=verify_snapshot(path=SMOKE_SNAPSHOT,scope='smoke');snapshot_sha=sha(SMOKE_SNAPSHOT)
    if OUT.exists() and any(OUT.iterdir()):raise FileExistsError('refusing to overwrite smoke output')
    for name in ('SMOKE_REPORT.md','SMOKE_INVARIANT_REPORT.md','SMOKE_REPRODUCIBILITY.md'):
        if (ROOT/name).exists():raise FileExistsError('refusing to overwrite '+name)
    OUT.mkdir(parents=True,exist_ok=True);RUN_STARTED=True;(OUT/'instances').mkdir();(OUT/'audit_artifacts').mkdir()
    tasks=list(planned())
    if len(tasks)!=192 or len(rerun_subset())!=8 or len(parallel_subset())!=16 or len(audit_subset())!=4:raise RuntimeError('plan cardinality error')
    for item in tasks:
        inst=generate_instance(item['family'],item['configuration'],item['seed_index'],namespace=NAMESPACE)
        if inst.namespace!=NAMESPACE:raise RuntimeError('wrong instance namespace')
        item.update(instance_hash=inst.instance_hash,public_hash=inst.public_hash,private_hash=inst.private_hash,
                    seed_hex=f"{derive_seed(NAMESPACE,item['family'],item['configuration'],item['seed_index']):064x}")
        (OUT/'instances'/(item['instance_id']+'.json')).write_text(inst.serialize()+'\n',encoding='utf8')
    write_json(OUT/'plan.json',tasks)
    plan_sha=sha(OUT/'plan.json')
    write_json(OUT/'run_metadata.json',{'namespace':NAMESPACE,'preregistration_sha256':prereg_sha,
      'snapshot_sha256':snapshot_sha,'source_tree_sha256':snapshot['source_tree_sha256'],
      'graph_sha256':snapshot['semantic_library_sha256'],
      'availability_manifest_sha256':snapshot['availability_manifest_sha256'],
      'driver_sha256':sha(Path(__file__).resolve()),'plan_sha256':plan_sha})
    # Budget uses measured 0.76 GiB per worker * 1.4 plus 1 GiB OS reserve.
    need_two=int(2*760_000_000*1.4+1024**3)
    main_workers=2 if available_memory()>=need_two else 1
    phases=[run_phase('main',main_workers),run_phase('rerun',1),run_phase('parallel1',1)]
    if available_memory()>=need_two:phases.append(run_phase('parallel2',2))
    else:phases.append({'phase':'parallel2','workers':2,'returncodes':[],'memory_abort':True,'seconds':0,'reason':'insufficient memory for predeclared 2-worker comparison'})
    main=read_phase('main');rerun=read_phase('rerun');p1=read_phase('parallel1');p2=read_phase('parallel2')
    rows=[row for item in main if item.get('ok') for row in item['rows']]
    instances={item['instance_id']:deserialize_instance((OUT/'instances'/(item['instance_id']+'.json')).read_text(encoding='utf8')) for item in tasks}
    expected=[item['instance_id'] for item in tasks]
    per_instance={x['instance_id']:x.get('check') for x in main if x.get('ok')}
    checks=check_rows(rows,instances,expected,validations=per_instance)
    exceptions=[x for x in main+rerun+p1+p2 if not x.get('ok')]
    exceptions.extend(p for p in phases if p.get('returncodes') and any(c!=0 for c in p['returncodes']))
    skips=[p for p in phases if p.get('memory_abort') or not p.get('returncodes')]
    execution=check_execution_status([x['instance_id'] for x in main if x.get('ok')],exceptions,skips,expected)
    def map_rows(items):return {x['instance_id']:x['rows'] for x in items if x.get('ok')}
    primary=map_rows(main);repeat_rows=map_rows(rerun);one=map_rows(p1);two=map_rows(p2)
    rerun_check=check_repeats(primary,repeat_rows,rerun_subset())
    parallel_check=check_repeats(one,two,parallel_subset())
    parallel_vs_primary=check_repeats(primary,one,parallel_subset())
    snapshot_check=check_snapshot_unchanged(snapshot_sha,sha(SMOKE_SNAPSHOT))
    snapshot_check['preregistration_unchanged']=(sha(prereg_path)==prereg_sha)
    snapshot_check['plan_unchanged']=(sha(OUT/'plan.json')==plan_sha)
    snapshot_check['serialized_instances_unchanged']=all(
      instances[item['instance_id']].instance_hash==item['instance_hash']
      and instances[item['instance_id']].public_hash==item['public_hash']
      and instances[item['instance_id']].private_hash==item['private_hash'] for item in tasks)
    try:
        snapshot_verified=(snapshot==verify_snapshot(path=SMOKE_SNAPSHOT,scope='smoke'))
    except Exception as exc:
        snapshot_verified=False
        snapshot_check['verification_error']=str(exc)
    def every(*names):
        return len(per_instance)==192 and all(v is not None and all(v.get('checks',{}).get(n) is True for n in names) for v in per_instance.values())
    no_crashes=all(p.get('returncodes') and all(c==0 for c in p['returncodes']) and not p.get('memory_abort') for p in phases) and all(x.get('ok') for x in main+rerun+p1+p2)
    c=checks['checks']
    invariants={
      'C01_192_complete': execution['checks']['every_instance_completed_once'] and c['exact_instance_coverage'],
      'C02_zero_crash': execution['checks']['no_crash_or_exception'] and no_crashes,
      'C03_zero_silent_skip': execution['checks']['no_explicit_or_silent_skip'] and c['exact_instance_coverage'] and c['four_distinct_methods'],
      'C04_same_instance_hash': c['paired_instance_hashes'],
      'C05_space_containment': every('m0_subset_mr_subset_b2','b2_subset_mc','b2_matches_library_static_mask'),
      'C06_negative_control_exact': every('negative_control_pattern_zero','negative_control_o1_equals_b2'),
      'C07_invalid_never_verified': every('stage_masks_nested','verified_only_generated','generated_only_in_domain','all_capacity_cells_finite_nonnegative','no_invalid_class_verified') and all(v.get('ok') is True for v in per_instance.values()),
      'C08_zero_nan_inf': c['output_finite'] and every('reached_v5_utility_finite_unit_interval'),
      'C09_utility_unit_interval': c['reported_utilities_unit_interval'] and every('reached_v5_utility_finite_unit_interval'),
      'C10_schema_complete': c['complete_output_schema'] and c['aggregate_counts_consistent'] and c['per_instance_checks_all_pass'] and c['o1_generated_count_matches'] and all(
          p.get('memory_samples',0)>0 and p.get('peak_process_rss_bytes',0)>0 and p.get('peak_system_physical_used_sample_bytes',0)>0 for p in phases) and all(
          all(key in row for key in ('smoke_snapshot_sha256','source_tree_sha256','graph_sha256','availability_manifest_sha256','public_eligible_count','failure_V1','failure_V2','failure_V3','failure_V4','failure_V5'))
          and row['public_eligible_count']==row['candidate_count']-sum(row['validator_rejections'].get(x,0) for x in ('V1','V2','V3'))
          and all(row['failure_'+x]==row['validator_rejections'].get(x,0) for x in ('V1','V2','V3','V4','V5')) for row in rows),
      'C11_rerun_8_equal': rerun_check['ok'],
      'C12_1v2_16_equal': parallel_check['ok'] and parallel_vs_primary['ok'],
      'C13_snapshot_unchanged': snapshot_check['ok'] and snapshot_check['preregistration_unchanged'] and snapshot_check['plan_unchanged'] and snapshot_check['serialized_instances_unchanged'] and snapshot_verified and all(
          x.get('snapshot_pre_verified') is True and x.get('snapshot_post_verified') is True for x in main+rerun+p1+p2) and all(
          row.get('smoke_snapshot_sha256')==snapshot_sha and row.get('source_tree_sha256')==snapshot['source_tree_sha256']
          and row.get('graph_sha256')==snapshot['semantic_library_sha256']
          and row.get('availability_manifest_sha256')==snapshot['availability_manifest_sha256'] for row in rows),
    }
    audit_check=check_audit_artifacts(OUT/'audit_artifacts',audit_subset(),rows,snapshot['semantic_library_sha256'],snapshot_sha,per_instance)
    invariants['C10_schema_complete'] = invariants['C10_schema_complete'] and audit_check['ok']
    all_ok=all(invariants.values())
    checks={'ok':all(invariants.values()),'invariants':invariants,'row_checks':checks,'execution':execution,'audit_artifacts':audit_check,'per_instance':per_instance}
    repeats={'ok':rerun_check['ok'] and parallel_check['ok'] and parallel_vs_primary['ok'],
             'rerun8_ids':rerun_subset(),'parallel16_ids':parallel_subset(),
             'rerun8':rerun_check,'parallel_1v2':parallel_check,'parallel_vs_primary':parallel_vs_primary}
    persist_csv(OUT/'raw_results.csv',rows)
    stage_keys=sorted({k for item in main if item.get('ok') for k in item['stages']})
    stage_rows=[{'stage':key,'instances':sum(key in item['stages'] for item in main if item.get('ok')),
                 **runtime_stats([item['stages'].get(key) for item in main if item.get('ok')])} for key in stage_keys]
    persist_csv(OUT/'stage_timing_summary.csv',stage_rows)
    for name,contents in zip(('method_summary.csv','config_summary.csv','family_diagnostics.csv'),summaries(rows)):persist_csv(OUT/name,contents)
    write_json(OUT/'invariant_results.json',{'checks':checks,'repeats':repeats,'phases':phases,'snapshot_sha':snapshot_sha,'status':'SMOKE_PASS' if all_ok else 'SMOKE_FAIL'})
    with (ROOT/'CHANGELOG_PREPILOT.md').open('a',encoding='utf8') as log:
        log.write('\n## SMOKE-01 diagnostic execution\n\nStatus: '+('SMOKE_PASS' if all_ok else 'SMOKE_FAIL')+'. Completed '+str(sum(bool(x.get('ok')) for x in main))+'/192; snapshot SHA256 '+snapshot_sha+'. Engineering/exploratory pipeline check only; no confirmation claim.\n')
    report=['# SMOKE-01 diagnostic report','',f"Status: {'SMOKE_PASS' if all_ok else 'SMOKE_FAIL'}.",
      f'Completed instances: {sum(bool(x.get("ok")) for x in main)}/192.',
      f'Primary worker count: {main_workers}. No bootstrap, research gates or research-success conclusion were computed.',
      f"Peak observed worker RSS: {max((p.get('peak_process_rss_bytes',0) for p in phases),default=0)} bytes; peak sampled aggregate workers: {max((p.get('peak_aggregate_worker_rss_sample_bytes',0) for p in phases),default=0)} bytes; peak sampled system physical used: {max((p.get('peak_system_physical_used_sample_bytes',0) for p in phases),default=0)} bytes.",
      'Memory samples are periodic and may miss transient spikes. Percentiles use linear interpolation at (n−1)×p.',
      'Failed invariants: '+(', '.join(k for k,v in invariants.items() if not v) or 'none')+'.',
      f"Negative-control exact equality (all instances): {'PASS' if invariants['C06_negative_control_exact'] else 'FAIL/UNCHECKABLE'}.",
      f"Snapshot, source, graph, indices, plan and preregistration unchanged: {'PASS' if invariants['C13_snapshot_unchanged'] else 'FAIL/UNCHECKABLE'}.",
      'SMOKE-01 is an engineering/exploratory pipeline check and is not confirmation evidence for the research hypothesis.',
      'Public eligible count is conditioned candidate count minus V1/V2/V3 failures; it is not the number passing capacity or private acceptance.',
      'Finite/unit-interval checks apply to defined output and V5-reached utilities; utilities for non-eligible or infeasible classes are undefined and are not treated as zero.',
      'The results characterize implementation diagnostics only. PILOT/CONFIRM were not run.',
      '', '| Family | Method | Instances | Agreements | Deadlocks | All zero | All one |', '|---|---|---:|---:|---:|---|---|']
    for stat in summaries(rows)[2]:
        report.append(f"| {stat['family']} | {stat['method']} | {stat['instances']} | {stat['agreements']} | {stat['deadlocks']} | {stat['instances']>0 and stat['agreements']==0} | {stat['instances']>0 and stat['deadlocks']==0} |")
    for key in ('O1_s','complete_run_paired_s'):
        values=[item['stages'][key] for item in main if item.get('ok') and key in item['stages']]
        st=runtime_stats(values)
        report.append(f"\n{key}: median={st['median_seconds']}, p95={st['p95_seconds']}, max={st['max_seconds']} seconds (n={len(values)}).")
    (ROOT/'SMOKE_REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    (ROOT/'SMOKE_INVARIANT_REPORT.md').write_text('# SMOKE invariants\n\n```json\n'+json.dumps(checks,indent=2,ensure_ascii=False)+'\n```\n',encoding='utf8')
    (ROOT/'SMOKE_REPRODUCIBILITY.md').write_text('# SMOKE reproducibility\n\n```json\n'+json.dumps(repeats,indent=2,ensure_ascii=False)+'\n```\n',encoding='utf8')
    print('SMOKE status', 'SMOKE_PASS' if all_ok else 'SMOKE_FAIL',flush=True)
    if not all_ok:raise SystemExit(1)


def self_test():
    p=list(planned());assert len(p)==192 and len({x['instance_id'] for x in p})==192
    assert len(rerun_subset())==8 and len(parallel_subset())==16 and len(audit_subset())==4
    assert set(audit_subset())<=set(rerun_subset()) and not(set(rerun_subset()) & set(parallel_subset()))
    assert canonical_rows([{'runtime_seconds':1,'x':2}])==canonical_rows([{'runtime_seconds':5,'x':2}])
    assert canonical_rows([{'runtime_seconds':1,'x':2}])!=canonical_rows([{'runtime_seconds':1,'x':3}])
    print('pure plan self-test passed; no instances or seeds generated')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--self-test',action='store_true')
    p.add_argument('--worker',choices=('main','rerun','parallel1','parallel2'));p.add_argument('--worker-id',type=int);p.add_argument('--workers',type=int)
    args=p.parse_args()
    if args.self_test:self_test()
    elif args.worker is not None:
        if args.worker_id is None or args.workers not in (1,2):raise SystemExit('invalid worker arguments')
        worker(args.worker,args.worker_id,args.workers)
    elif args.execute:
        try:
            execute()
        except BaseException as exc:
            # If a run has actually begun, preserve incomplete evidence and
            # issue explicit FAIL. Preflight refusals must not overwrite an
            # earlier run or manufacture reports.
            if RUN_STARTED and not (isinstance(exc,SystemExit) and (ROOT/'SMOKE_REPORT.md').exists()):
                error={'status':'SMOKE_FAIL','error':str(exc),'traceback':traceback.format_exc(),
                       'invariants':'uncheckable unless independently established'}
                if not (OUT/'driver_error.json').exists():write_json(OUT/'driver_error.json',error)
                reports={
                  'SMOKE_REPORT.md':'# SMOKE-01 diagnostic report\n\nStatus: SMOKE_FAIL. The driver stopped before completing verification.\n\nSMOKE-01 is an engineering/exploratory pipeline check and is not confirmation evidence for the research hypothesis.\n',
                  'SMOKE_INVARIANT_REPORT.md':'# SMOKE invariants\n\nSMOKE_FAIL: not all invariants were checkable; see results/smoke/driver_error.json.\n',
                  'SMOKE_REPRODUCIBILITY.md':'# SMOKE reproducibility\n\nIncomplete; see results/smoke/driver_error.json.\n'}
                for name,text in reports.items():
                    path=ROOT/name
                    if not path.exists():path.write_text(text,encoding='utf8')
            raise
    else:raise SystemExit('SMOKE not started; --execute requires verified dedicated snapshot and preregistration')

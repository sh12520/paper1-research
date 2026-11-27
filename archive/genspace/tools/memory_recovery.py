"""Seed-isolated engineering audit: 32 paired instances, one worker at a time.

No SMOKE/PILOT/CONFIRM instance or seed is created. Run only after source freeze.
"""
from __future__ import annotations
import argparse, itertools, json, os, subprocess, sys, time, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'results'/'memory_recovery_engineering'
NS='GENSPACE-FAIL-01-ENGINEERING'
THRESHOLD=768*1024**2


def plan():
    return [dict(id=f'{f}_{r}_d{d}_s{s}',family=f,seed=s,configuration=dict(resource_pressure='medium',preference_conflict='high',capability_richness=r,composition_depth=d))
        for f,r,d,s in itertools.product(('F1','F2','F3','F4'),('sparse','rich'),(1,2),(0,1))]


def sample(pid=None,event='periodic'):
    from tools.smoke_01 import memory_status,process_memory
    total,avail=memory_status()
    try: worker,peak=process_memory(pid) if pid else (None,None)
    except OSError: worker,peak=None,None
    try: orchestrator,_=process_memory(os.getpid())
    except OSError:orchestrator=0
    return dict(t=time.time(),event=event,worker_rss=worker,worker_peak=peak,orchestrator_rss=orchestrator,system_used=total-avail,system_available=avail)


def child(phase,indexes):
    from src.fast_exact import FastLibrary
    from src.fast_runner import run_paired_fast
    lib=FastLibrary.from_graph(scope='engineering')
    def mark(event,i):
        with (OUT/'events.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps({'event':event,'index':i,'phase':phase,'t':time.time()})+'\n')
            f.flush()
    for i in indexes:
        mark('instance_start',i)
        text=(OUT/'instances'/f'{i:02d}.json').read_text(encoding='utf8')
        def observer(*args):mark('evaluation_complete',i)
        rows,stages=run_paired_fast(text,lib,evaluation_observer=observer)
        mark('instance_end',i)
        target=OUT/phase/f'{i:02d}.json';tmp=target.with_suffix('.tmp')
        with tmp.open('x',encoding='utf8') as f:
            json.dump({'rows':rows,'stages':stages},f,ensure_ascii=False,allow_nan=False,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(tmp,target)


def run_child(phase,indexes):
    cmd=[sys.executable,str(Path(__file__).resolve()),'--child',phase,'--indexes',','.join(map(str,indexes))]
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    if sample()['system_available']<THRESHOLD:return {'error':'memory guard before child','indexes':indexes}
    start=time.monotonic();proc=subprocess.Popen(cmd,cwd=ROOT,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    samples=[];terminated=False;event_offset=0
    while proc.poll() is None:
        s=sample(proc.pid);s['phase']=phase;s['indexes']=indexes;samples.append(s)
        if s['system_available']<THRESHOLD:
            proc.terminate();terminated=True;break
        time.sleep(.2)
    code=proc.wait()
    held=sample(proc.pid,event='child_exit_handle_held');held.update(phase=phase,indexes=indexes,process_exited=proc.poll() is not None,exit_code=code);samples.append(held)
    # Windows retains the terminated process object while Popen owns this
    # handle. Close it only after wait() has captured the return code.
    proc._handle.Close()
    after=sample(proc.pid,event='child_exit');after.update(phase=phase,indexes=indexes,process_exited=proc.poll() is not None,exit_code=code);samples.append(after)
    for _ in range(5):
        time.sleep(.2)
        s=sample(proc.pid,event='post_child_exit');s.update(phase=phase,indexes=indexes,process_exited=proc.poll() is not None,exit_code=code);samples.append(s)
    with (OUT/'samples.jsonl').open('a',encoding='utf8') as f:
        for s in samples:f.write(json.dumps(s)+'\n')
    return {'indexes':indexes,'returncode':code,'memory_guard':terminated,'seconds':time.monotonic()-start,'samples':len(samples),'exit':after}


def slope(values):
    if len(values)<2:return None
    xm=(len(values)-1)/2;ym=sum(values)/len(values)
    return sum((i-xm)*(y-ym) for i,y in enumerate(values))/sum((i-xm)**2 for i in range(len(values)))


def execute():
    from src.execution_snapshot import verify_snapshot
    from src.instances import generate_instance
    from tools.smoke_01 import sha
    verify_snapshot(scope='engineering')
    if OUT.exists():raise FileExistsError('refusing overwrite of engineering evidence')
    OUT.mkdir(parents=True);(OUT/'instances').mkdir();(OUT/'long').mkdir();(OUT/'batch').mkdir()
    fixed=plan(); assert len(fixed)==32 and len({x['id'] for x in fixed})==32
    (OUT/'fixed_plan.json').write_text(json.dumps(fixed,indent=2)+'\n',encoding='utf8')
    for i,p in enumerate(fixed):
        x=generate_instance(p['family'],p['configuration'],p['seed'],namespace=NS)
        assert x.namespace==NS
        (OUT/'instances'/f'{i:02d}.json').write_text(x.serialize()+'\n',encoding='utf8')
    started=time.monotonic();long=run_child('long',list(range(32)));batches=[]
    if long.get('returncode')==0:
        for start in range(0,32,4):
            b=run_child('batch',list(range(start,start+4)));batches.append(b)
            if b.get('returncode')!=0 or b.get('memory_guard'):break
    def canonical(i,phase):
        x=json.loads((OUT/phase/f'{i:02d}.json').read_text(encoding='utf8'))
        return [{k:v for k,v in row.items() if k!='runtime_seconds'} for row in x['rows']]
    verify_snapshot(scope='engineering')
    completed=[i for i in range(32) if (OUT/'long'/f'{i:02d}.json').exists() and (OUT/'batch'/f'{i:02d}.json').exists()]
    same=[i for i in completed if canonical(i,'long')==canonical(i,'batch')]
    events=[json.loads(x) for x in (OUT/'events.jsonl').read_text(encoding='utf8').splitlines()] if (OUT/'events.jsonl').exists() else []
    samples=[json.loads(x) for x in (OUT/'samples.jsonl').read_text(encoding='utf8').splitlines()] if (OUT/'samples.jsonl').exists() else []
    def nearest(t,phase):
        x=[s for s in samples if s['phase']==phase and s['event']=='periodic']
        return min(x,key=lambda s:abs(s['t']-t)) if x else None
    metrics={}
    for phase in ('long','batch'):
        end=[(e,nearest(e['t'],phase)) for e in events if e['phase']==phase and e['event']=='instance_end']
        end=[(e,s) for e,s in end if s]
        exits=[s for s in samples if s['phase']==phase and s['event']=='child_exit']
        live=[s for s in samples if s['phase']==phase and s['event']=='periodic']
        recoveries=[]
        for exit in exits:
            batch_live=[s for s in live if s['indexes']==exit['indexes']]
            if batch_live:recoveries.append({'indexes':exit['indexes'],'initial_rss':batch_live[0]['worker_rss'],'final_rss':batch_live[-1]['worker_rss'],'available_before_exit':batch_live[-1]['system_available'],'available_after_exit':exit['system_available'],'available_change':exit['system_available']-batch_live[-1]['system_available']})
        metrics[phase]={'instance_end_count':len(end),'initial_rss':live[0]['worker_rss'] if live else None,'final_rss':live[-1]['worker_rss'] if live else None,'initial_available':live[0]['system_available'] if live else None,'final_available':live[-1]['system_available'] if live else None,'rss_slope_bytes_per_instance':slope([s['worker_rss'] for e,s in end if s['worker_rss'] is not None]),'available_slope_bytes_per_instance':slope([s['system_available'] for e,s in end]),'peak_worker_rss':max((s['worker_peak'] for s in samples if s['phase']==phase and s['worker_peak'] is not None),default=0),'min_available':min((s['system_available'] for s in samples if s['phase']==phase),default=0),'exit_available':[s['system_available'] for s in exits],'exit_worker_rss':[s['worker_rss'] for s in exits],'exit_process_exited':[s['process_exited'] for s in exits],'exit_recoveries':recoveries}
    ex=metrics['batch']['exit_available']; monotonic=len(ex)>1 and all(b<a for a,b in zip(ex,ex[1:]));reclaimed=len(ex)==8 and all(metrics['batch']['exit_process_exited']) and all(x is None or x==0 for x in metrics['batch']['exit_worker_rss'])
    result={'fixed_plan':fixed,'long':long,'batches':batches,'metrics':metrics,'matched':len(same),'compared':len(completed),'exact_equal':len(same)==len(completed)==32,'os_child_exit_reclaimed':reclaimed,'exit_available_strictly_decreasing':monotonic,'wall_seconds':time.monotonic()-started,'snapshot_sha256':sha(ROOT/'EXECUTION_SNAPSHOT_FINGERPRINT.json'),'sampling_note':'0.2-second periodic process-level samples matched to instance boundary events; evaluation_complete observer occurs immediately after evaluator returns; internal evaluator stage boundaries not instrumented. RSS peaks use OS PeakWorkingSetSize. Child reclamation inferred from observed process exit and unavailable/zero working-set access; system available memory can change concurrently due to unrelated processes and does not prove bytewise recovery.'}
    ok=result['exact_equal'] and reclaimed and not monotonic and long.get('returncode')==0 and len(batches)==8 and all(b.get('returncode')==0 and not b.get('memory_guard') for b in batches)
    result['status']='PASS' if ok else 'BLOCKED'
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    report=['# MEMORY-RECOVERY-ENGINEERING-01','',f"Status: {result['status']}",'','Fixed plan: 32 ENGINEERING instances, family × richness × depth × two fixed indices; pressure medium and conflict high.','No SMOKE/PILOT/CONFIRM seed or instance used.',f"Exact non-timing output equality: {len(same)}/{len(completed)} compared, 32 required.",f"Batch children exited and RSS reclaimed: {reclaimed}. Strictly monotonically declining available memory at child exits: {monotonic}.",f"Total wall time: {result['wall_seconds']:.2f} s.",result['sampling_note'],'','```json',json.dumps({'long':long,'batches':batches,'metrics':metrics},indent=2),'```']
    (ROOT/'MEMORY_RECOVERY_ENGINEERING_REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    print(result['status'],flush=True)
    return ok


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--child',choices=('long','batch'));p.add_argument('--indexes');a=p.parse_args()
    if a.child:child(a.child,[int(x) for x in a.indexes.split(',')])
    elif a.execute:raise SystemExit(0 if execute() else 1)
    else:print('prepared only; --execute required')

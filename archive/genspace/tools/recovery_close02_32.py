"""32-instance engineering-only real FAST batch audit; explicit execution only."""
import argparse,json,os,subprocess,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'results'/'recovery_close02_32'
REF=ROOT/'results'/'memory_recovery_engineering'
EVENTS=('INSTANCE_START','PUBLIC_FILTER_START','PUBLIC_FILTER_END','V4_START','V4_END','V5_START','V5_END','REPRESENTATIVE_SELECTED','SERIALIZATION_START','SERIALIZATION_END','INSTANCE_COMPLETE')

def child(start):
    from src.process_lifecycle import join_job
    join_job(os.environ['GENSPACE_JOB'])
    from src.fast_exact import FastLibrary
    from src.engineering_recovery import run_one
    from src.process_lifecycle import identity,memory_sample,EMERGENCY_FLOOR
    from tools.smoke_01 import process_memory
    pid=os.getpid(); parent=os.getppid(); ident=identity(pid); current=[None]
    def observe(event):
        s=memory_sample(); rss,peak=process_memory(pid); parent_rss,_=process_memory(parent)
        row=dict(event=event,instance_id=current[0],pid=pid,process_identity=ident,worker_rss=rss,worker_peak_rss=peak,orchestrator_pid=parent,orchestrator_rss=parent_rss,system_used=s['used'],system_available=s['available'],timestamp=s['timestamp'])
        with (OUT/f'events_{start:02d}.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(row)+'\n');f.flush()
        if s['available']<EMERGENCY_FLOOR:
            (OUT/f'pause_{start:02d}.json').write_text(json.dumps(row),encoding='utf8')
            raise RuntimeError('PAUSED_MEMORY: emergency floor')
    lib=FastLibrary.from_graph(scope='engineering');observe('LIBRARY_READY')
    for i in range(start,start+4):
        current[0]=f'engineering_{i:02d}'
        run_one(OUT/'commits',current[0],(REF/'instances'/f'{i:02d}.json').read_bytes(),lib,phase_observer=observe)
    current[0]=None;observe('CHILD_PRE_EXIT')

def execute():
    from src.process_lifecycle import LifecycleTracker,prelaunch_guard,emergency_guard,memory_sample,create_job,job_active,close_job
    from src.engineering_recovery import snapshot,inspect
    if OUT.exists():raise FileExistsError('refusing overwrite of audit evidence')
    if not (REF/'fixed_plan.json').is_file():raise RuntimeError('missing previous fixed engineering reference')
    snapshot_hash=snapshot(); OUT.mkdir(parents=True);(OUT/'commits').mkdir()
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    batches=[];started=time.perf_counter()
    for start in range(0,32,4):
        guard=prelaunch_guard(); info={'start':start,'prelaunch':guard,'snapshot_hash':snapshot_hash}
        if not guard['pass']:
            info.update(status='PAUSED_MEMORY',reason='prelaunch_floor');batches.append(info);break
        log=(OUT/f'child_{start:02d}.log').open('x',encoding='utf8')
        job,name=create_job()
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child',str(start)],cwd=ROOT,env={**env,'GENSPACE_JOB':name},stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            tracker=LifecycleTracker(p); samples=[]; paused=False
            while p.poll() is None:
                tracker.observe(); g=emergency_guard(); samples.append(g['sample'])
                if not g['pass']:p.terminate();paused=True;break
                time.sleep(.2)
            p.wait();log.close();before=samples[-1] if samples else None
            paused=paused or (OUT/f'pause_{start:02d}.json').exists()
            life=tracker.finish();after=memory_sample(); job_info=job_active(job)
        finally:log.close();close_job(job)
        info.update(status='PAUSED_MEMORY' if paused else 'FINISHED',samples=samples,lifecycle=life,job=job_info,before_exit=before,after_exit=after)
        batches.append(info)
        if paused or not life['pass'] or job_info['active_processes']!=0 or job_info['total_processes']<1:break
    results=[];matches=[];errors=[]
    for i in range(32):
        iid=f'engineering_{i:02d}';raw=(REF/'instances'/f'{i:02d}.json').read_bytes()
        try:
            if inspect(OUT/'commits',iid,raw,snapshot_hash):
                item=json.loads((OUT/'commits'/iid/'result.json').read_bytes()); original=json.loads((REF/'long'/f'{i:02d}.json').read_bytes())
                clean=lambda rows:[{k:v for k,v in r.items() if k!='runtime_seconds'} for r in rows]
                matches.append(clean(item['rows'])==clean(original['rows']));results.append(iid)
        except Exception as exc:errors.append({'instance_id':iid,'error':str(exc)})
    events=[json.loads(line) for f in sorted(OUT.glob('events_*.jsonl')) for line in f.read_text(encoding='utf8').splitlines()]
    phase={}
    for event in sorted(set(x['event'] for x in events)):
        x=[v['worker_rss'] for v in events if v['event']==event]
        phase[event]={'count':len(x),'median_rss':statistics.median(x),'max_rss':max(x)}
    batch_metrics=[]
    for b in batches:
        path=OUT/f"events_{b['start']:02d}.jsonl"
        es=[json.loads(x) for x in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
        batch_metrics.append({'start':b['start'],'max_rss':max((e['worker_rss'] for e in es),default=None),
                              'min_available':min((e['system_available'] for e in es),default=None),
                              'available_before_exit':(b.get('before_exit') or {}).get('available'),
                              'available_after_exit':(b.get('after_exit') or {}).get('available')})
    complete_events=all(sum(x['event']==e and x['instance_id']==iid for x in events)==1 for iid in results for e in EVENTS)
    complete_events &= len([x for x in events if x['event']=='LIBRARY_READY'])==8 and len([x for x in events if x['event']=='CHILD_PRE_EXIT'])==8
    report={'snapshot_hash':snapshot_hash,'completed':len(results),'matched_reference':sum(matches),'validation_errors':errors,'batches':batches,'batch_metrics':batch_metrics,'phase':phase,'all_events_present':complete_events,'min_available':min((x['system_available'] for x in events),default=None),'wall_seconds':time.perf_counter()-started}
    report['pass']=len(results)==32 and sum(matches)==32 and not errors and len(batches)==8 and all(x.get('lifecycle',{}).get('pass') and x.get('status')=='FINISHED' and x.get('job',{}).get('active_processes')==0 and x.get('job',{}).get('total_processes',0)>=1 for x in batches) and complete_events and snapshot()==snapshot_hash
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    lines=['# Real FAST 32-instance memory audit','','Status: '+('PASS' if report['pass'] else 'BLOCKED'),f"Completed {len(results)}/32; exact reference matches {sum(matches)}/32.",f"Phase events complete: {complete_events}; minimum event-sampled available physical bytes: {report['min_available']}; wall time: {report['wall_seconds']:.3f} s.",'Job assignment happens at the beginning of the Python child entry point, after interpreter startup; this is not CREATE_SUSPENDED coverage. Periodic samples and phase events cannot prove the absence of an unobserved transient.','','| Phase | Count | Median worker RSS bytes | Max worker RSS bytes |','|---|---:|---:|---:|']
    for name,value in sorted(phase.items()):lines.append(f"| {name} | {value['count']} | {value['median_rss']} | {value['max_rss']} |")
    lines+=['','| First index | Peak event RSS | Min event available | Available before exit | Available after exit |','|---:|---:|---:|---:|---:|']
    for b in batch_metrics:lines.append(f"| {b['start']} | {b['max_rss']} | {b['min_available']} | {b['available_before_exit']} | {b['available_after_exit']} |")
    lines += ['','Complete lifecycle, Job Object and memory records: `results/recovery_close02_32/report.json`.']
    (ROOT/'REAL_FAST_MEMORY_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('32-instance real-path audit:', 'PASS' if report['pass'] else 'BLOCKED',flush=True)
    return report['pass']

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');a.add_argument('--child',type=int);args=a.parse_args()
    if args.child is not None:child(args.child)
    elif args.execute:raise SystemExit(0 if execute() else 1)
    else:print('explicit --execute required')

"""P1--P5 real FAST ENGINEERING test for the shared transaction primitive.

Explicit execution only. Existing experimental seeds are never generated.
"""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
RAW=ROOT/'results'/'memory_recovery_engineering'/'instances'/'00.json'
OUT=ROOT/'results'/'shared_primitive_fault_regression'
NS='GENSPACE-FAIL-01-ENGINEERING';IID='fixture_00'

def child(root,point):
    from src.fast_exact import FastLibrary
    from src.fast_runner import run_paired_fast
    from src.instances import deserialize_instance
    from src.execution_snapshot import verify_snapshot,SNAPSHOT,sha256_file
    from src.smoke02_commit import inspect_complete,commit_instance,quarantine_incomplete
    raw=RAW.read_bytes();obj=deserialize_instance(raw.decode())
    if obj.namespace!=NS:raise ValueError('not ENGINEERING')
    def gate():
        verify_snapshot(scope='engineering');return sha256_file(SNAPSHOT)
    def validator(b):
        x=deserialize_instance(b.decode());return x.instance_hash,x.namespace
    snap=gate();root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if (root/IID/'COMPLETE.json').exists():
        inspect_complete(root,IID,obj.instance_hash,snap,gate,validator,namespace=NS)
        print('skipped',flush=True);return
    if (root/IID).exists():quarantine_incomplete(root,IID,snap,gate)
    def fault(stage):
        if point=='P3' and stage=='before_rename':os._exit(83)
        if point=='P4' and stage=='after_rename':os._exit(84)
    def phase(event):
        if point=='P1' and event=='INSTANCE_START':os._exit(81)
    lib=FastLibrary.from_graph(scope='engineering')
    rows,_=run_paired_fast(raw.decode(),lib,phase_observer=phase)
    if point=='P2':os._exit(82)
    result={'instance_id':IID,'namespace':NS,'instance_hash':obj.instance_hash,'rows':rows}
    commit_instance(root,IID,obj.instance_hash,raw,result,snap,gate,validator,hook=fault,namespace=NS)
    if point=='P5':os._exit(85)
    print('completed',flush=True)

def canonical(root):
    x=json.loads((root/IID/'result.json').read_text(encoding='utf8'))
    for r in x['rows']:r.pop('runtime_seconds',None)
    return x

def execute():
    from src.process_lifecycle import prelaunch_guard,emergency_guard
    from src.windows_suspended_job import launch
    if OUT.exists():raise FileExistsError('refusing to overwrite old fault evidence')
    OUT.mkdir(parents=True);records=[]
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    def run(name,point,expected):
        guard=prelaunch_guard()
        if not guard['pass']:raise RuntimeError('PAUSED_MEMORY prelaunch')
        log=OUT/f'{name}_{point}.log'
        p=launch([sys.executable,str(Path(__file__).resolve()),'--child',str(OUT/name),'--point',point],cwd=str(ROOT),env=env,stdout_path=str(log))
        samples=[]
        while p.poll() is None:
            m=emergency_guard();samples.append(m['sample'])
            if not m['pass']:
                p.terminate();p.finish(expected_exit=1);raise RuntimeError('PAUSED_MEMORY emergency')
            time.sleep(.2)
        life=p.finish(expected_exit=expected)
        if not life['pass']:raise RuntimeError('unexpected child outcome: '+str(life))
        records.append({'case':name,'point':point,'prelaunch':guard,'samples':samples,'lifecycle':life})
        return log.read_text(encoding='utf8').strip()
    run('baseline','normal',0);reference=canonical(OUT/'baseline');cases={}
    for point in ('P1','P2','P3','P4','P5'):
        run(point,point,80+int(point[1]));pre=(OUT/point/IID/'COMPLETE.json').exists()
        status=run(point,'normal',0);matches=canonical(OUT/point)==reference
        count=sum(p.is_dir() and not p.name.startswith('.') and (p/'COMPLETE.json').is_file() for p in (OUT/point).iterdir())
        cases[point]={'complete_before_resume':pre,'resume':status,'exact_non_timing_equal':matches,'complete_count':count,
                      'pass':pre==(point=='P5') and status==('skipped' if point=='P5' else 'completed') and matches and count==1}
    result={'cases':cases,'jobs':records,'pass':all(v['pass'] for v in cases.values())}
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print('shared primitive real FAST P1-P5:', 'PASS' if result['pass'] else 'FAIL',flush=True)
    return result['pass']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--child');p.add_argument('--point',default='normal');a=p.parse_args()
    if a.child:child(a.child,a.point)
    elif a.execute:raise SystemExit(0 if execute() else 1)
    else:raise SystemExit('explicit --execute required')

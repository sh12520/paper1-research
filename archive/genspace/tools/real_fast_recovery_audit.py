"""ENGINEERING-only real subprocess fault injection. Explicit --execute required."""
import argparse,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'results'/'real_fast_recovery_engineering'
IID='engineering_fixture_00'
RAW=ROOT/'results'/'memory_recovery_engineering'/'instances'/'00.json'

def child(root,point):
    from src.fast_exact import FastLibrary
    from src.engineering_recovery import run_one
    lib=FastLibrary.from_graph(scope='engineering')
    print(run_one(root,IID,RAW.read_bytes(),lib,inject=None if point=='none' else point),flush=True)

def run(root,point='none'):
    from src.process_lifecycle import prelaunch_guard,emergency_guard
    def record(event):
        with (OUT/'memory_samples.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(event,sort_keys=True)+'\n')
    pre=prelaunch_guard();record({'event':'prelaunch','point':point,**pre})
    if not pre['pass']:
        (OUT/'PAUSED_MEMORY.json').write_text(json.dumps({'reason':'prelaunch_floor','point':point,'samples':pre['samples']},indent=2))
        raise RuntimeError('PAUSED_MEMORY: prelaunch threshold')
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    cmd=[sys.executable,__file__,'--child',str(root),'--point',point]
    proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    while proc.poll() is None:
        state=emergency_guard();record({'event':'running','point':point,**state})
        if not state['pass']:
            proc.terminate();stdout,stderr=proc.communicate()
            (OUT/'PAUSED_MEMORY.json').write_text(json.dumps({'reason':'emergency_floor','point':point,'sample':state['sample'],'stdout':stdout,'stderr':stderr},indent=2))
            raise RuntimeError('PAUSED_MEMORY: emergency floor')
        time.sleep(.2)
    stdout,stderr=proc.communicate()
    return subprocess.CompletedProcess(cmd,proc.returncode,stdout,stderr)

def canon(path):
    x=json.loads((path/IID/'result.json').read_text());x.pop('stages')
    for row in x['rows']:row.pop('runtime_seconds',None)
    return x

def main():
    from unittest.mock import patch
    import src.engineering_recovery as recovery
    from src.engineering_recovery import inspect,snapshot
    from src.execution_snapshot import verify_snapshot,SNAPSHOT
    snap=snapshot()
    if OUT.exists():raise FileExistsError('refusing overwrite')
    OUT.mkdir(parents=True);raw=RAW.read_bytes()
    baseline=OUT/'baseline';p=run(baseline)
    if p.returncode!=0:raise RuntimeError(p.stderr)
    expected=canon(baseline);points={}
    for point in ('P1','P2','P3','P4','P5'):
        root=OUT/point;p=run(root,point);before=(root/IID/'COMPLETE.json').exists()
        second=run(root);equal=second.returncode==0 and canon(root)==expected
        count=sum(1 for x in root.iterdir() if x.is_dir() and not x.name.startswith('.'))
        points[point]={'injected_returncode':p.returncode,'complete_before_resume':before,'resume_returncode':second.returncode,'resume_stdout':second.stdout.strip(),'exact_non_timing_equal':equal,'valid_final_count':count,'passed':p.returncode==80+int(point[1]) and second.returncode==0 and equal and count==1 and (second.stdout.strip()=='skipped' if point=='P5' else second.stdout.strip()=='completed')}
    fake=[]
    original=json.loads(SNAPSHOT.read_text())
    for key in ('source_tree_sha256','config_sha256','semantic_library_sha256','registry_fingerprint','model_fingerprint','dependency_fingerprint'):
        changed=dict(original);changed[key]='0'*64
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'bad.json';f.write_text(json.dumps(changed))
            try:
                with patch.object(recovery,'verify_snapshot',lambda **kwargs:verify_snapshot(path=f,scope='engineering')):
                    inspect(baseline,IID,raw,snap)
                rejected=False
            except ValueError:rejected=True
        fake.append({'field':key,'rejected':rejected})
    corrupt=OUT/'tampered';shutil.copytree(baseline,corrupt)
    with (corrupt/IID/'result.json').open('ab') as f:f.write(b' ')
    try:inspect(corrupt,IID,raw,snap);rejected=False
    except (ValueError,KeyError):rejected=True
    report={'points':points,'snapshot_mismatch':fake,'tampered_result_rejected':rejected,'snapshot_after':snapshot()==snap}
    report['passed']=all(x['passed'] for x in points.values()) and all(x['rejected'] for x in fake) and rejected and report['snapshot_after']
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'REAL_FAST_RECOVERY_AUDIT.md').write_text('# REAL FAST recovery ENGINEERING audit\n\nStatus: '+('PASS' if report['passed'] else 'BLOCKED')+'\n\nOne ENGINEERING fixture; no SMOKE/PILOT/CONFIRM. Snapshot mismatch cases alter a temporary saved fingerprint and compare to actual live source/config/library/runtime, rather than changing production files.\n\n```json\n'+json.dumps(report,indent=2)+'\n```\n',encoding='utf8')
    print('PASS' if report['passed'] else 'BLOCKED')
    return 0 if report['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--child');p.add_argument('--point',default='none');a=p.parse_args()
    if a.child:child(Path(a.child),a.point)
    elif a.execute:sys.exit(main())
    else:print('prepared only')

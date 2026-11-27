"""Guarded, resumable launcher for the fixed development harness.

Only existing PILOT instances are consumed by the child. Memory pauses are
engineering events, not study results. Each restart uses the same harness,
which checks source/config/input hashes before accepting completed records.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.execution_snapshot import verify_snapshot,PILOT_EXECUTABLE_SNAPSHOT,sha256_file
from tools.smoke_01 import memory_status,process_memory

BASE=ROOT/'results/method_dev_v1'
EXPECTED='18c3ef2eda454dd91a607eaecdd7501f5f82624f907d09bd6939cc77dd6bec0f'
PRELAUNCH=2048*1048576
EMERGENCY=768*1048576

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-name',default='run')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run_name):raise ValueError('unsafe run directory name')
    if (ROOT/'FROZEN_CONFIG.yaml').exists():raise RuntimeError('unexpected frozen config')
    auth=json.loads((ROOT/'PILOT_AUTHORIZATION_STATE.json').read_text(encoding='utf8'))
    if auth['namespace_authorizations']['CONFIRM']['allowed'] is not False:raise RuntimeError('CONFIRM must remain disabled')
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    if sha256_file(PILOT_EXECUTABLE_SNAPSHOT)!=EXPECTED:raise RuntimeError('snapshot changed')
    samples=[]
    for _ in range(3):samples.append(memory_status()[1]);time.sleep(.2)
    if min(samples)<PRELAUNCH:
        print(json.dumps({'status':'PAUSED_MEMORY','prelaunch_available':samples}),flush=True)
        return 2
    segments=BASE/'segments';segments.mkdir(exist_ok=True)
    number=len(list(segments.glob('segment_*.json')))
    log_path=segments/f'segment_{number:03d}.log';status_path=segments/f'segment_{number:03d}.json'
    if log_path.exists() or status_path.exists():raise RuntimeError('segment collision')
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    minimum=min(samples);peak=0;breach=False;started=time.time()
    with log_path.open('x',encoding='utf8') as log:
        child=subprocess.Popen([sys.executable,str(BASE/'harness.py'),'--output','results/method_dev_v1/'+args.run_name],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        while child.poll() is None:
            minimum=min(minimum,memory_status()[1])
            try:peak=max(peak,process_memory(child.pid)[1])
            except OSError:pass
            if minimum<EMERGENCY:breach=True;child.terminate();break
            time.sleep(.25)
        code=child.wait()
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    status={'status':'PAUSED_MEMORY' if breach else ('COMPLETE' if code==0 else 'ERROR'),
            'returncode':code,'start':started,'end':time.time(),'prelaunch_available':samples,
            'minimum_available':minimum,'peak_worker_working_set':peak,'snapshot_sha256':EXPECTED,
            'launcher_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'run_name':args.run_name,'log':str(log_path.relative_to(ROOT))}
    status_path.write_text(json.dumps(status,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(status,sort_keys=True),flush=True)
    return 0 if status['status']=='COMPLETE' else 2 if breach else 1

if __name__=='__main__':raise SystemExit(main())

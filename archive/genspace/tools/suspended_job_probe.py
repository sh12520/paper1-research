"""Seed-free Job launcher observation; no research execution."""
import json,sys,time
from pathlib import Path
from src.windows_suspended_job import launch
from src.process_lifecycle import classify

def run():
    results=[]
    for _ in range(3):
        p=launch([sys.executable,'-c','pass']); result=p.finish();start=time.monotonic(); observations=[]
        while True:
            c=classify(result['identity']);elapsed=time.monotonic()-start
            observations.append({'elapsed_seconds':elapsed,'classification':c['status']})
            if c['pass'] or elapsed>=2:break
            time.sleep(.1)
        results.append({'launch':result,'post_close_observations':observations,'disappearance_seconds':elapsed if c['pass'] else None,'right_censored':not c['pass']})
    out=Path('results/windows_lifecycle_engineering');out.mkdir(parents=True,exist_ok=True)
    (out/'lingering_probe.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    print(json.dumps([{'status':x['launch']['classification'],'passed':x['launch']['pass'],'elapsed':x['disappearance_seconds'],'right_censored':x['right_censored']} for x in results]))
    return all(x['launch']['pass'] for x in results)

if __name__=='__main__':raise SystemExit(0 if run() else 1)

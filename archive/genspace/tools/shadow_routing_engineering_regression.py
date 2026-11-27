"""One explicitly authorized serialized ENGINEERING semantics regression.

Requires an up-to-date engineering snapshot; never generates any seed or
instance and must be run only after all routing source has been frozen.
"""
from __future__ import annotations
import json
from pathlib import Path
from src.process_lifecycle import prelaunch_guard, emergency_guard
from src.execution_snapshot import SNAPSHOT, sha256_file, verify_snapshot
from src.fast_exact import FastLibrary
from src.fast_runner import run_paired_fast

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'results'/'memory_recovery_engineering'
OUT=ROOT/'results'/'shadow_routing_engineering_regression.json'

def main():
    if OUT.exists():raise FileExistsError('refusing to overwrite engineering regression')
    pre=prelaunch_guard()
    if not pre['pass']:raise RuntimeError('PAUSED_MEMORY prelaunch')
    before=sha256_file(SNAPSHOT);verify_snapshot(scope='engineering')
    raw=(DATA/'instances'/'00.json').read_text(encoding='utf8')
    instance=json.loads(raw)
    if instance.get('namespace')!='GENSPACE-FAIL-01-ENGINEERING':raise ValueError('unexpected fixture namespace')
    reference=json.loads((DATA/'long'/'00.json').read_text(encoding='utf8'))['rows']
    lib=FastLibrary.from_graph(scope='engineering')
    samples=[]
    def monitor(event):
        state=emergency_guard();samples.append({'event':event,**state})
        if not state['pass']:raise RuntimeError('PAUSED_MEMORY emergency')
    rows,_=run_paired_fast(raw,lib,phase_observer=monitor)
    def canonical(data):
        rows=[{k:v for k,v in r.items() if k!='runtime_seconds'} for r in data]
        return json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False)
    after=sha256_file(SNAPSHOT);verify_snapshot(scope='engineering')
    result={'fixture':'results/memory_recovery_engineering/instances/00.json',
            'reference':'results/memory_recovery_engineering/long/00.json',
            'method_count':len(rows),'non_timing_field_counts':{r['method']:len(r)-('runtime_seconds' in r) for r in rows},
            'exact_non_timing_equal':canonical(reference)==canonical(rows),
            'snapshot_sha256':before,'snapshot_unchanged':before==after,
            'prelaunch':pre,'memory_samples':samples}
    result['pass']=result['exact_non_timing_equal'] and result['snapshot_unchanged'] and len(rows)==4
    OUT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    if not result['pass']:raise SystemExit('FAIL')
    print('ENGINEERING serialized instance regression PASS')

if __name__=='__main__':main()

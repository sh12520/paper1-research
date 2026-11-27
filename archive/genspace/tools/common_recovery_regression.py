"""Real FAST SHADOW recovery regressions; never access SMOKE/PILOT/CONFIRM.

Requires completed locked snapshot/authorization, and an earlier complete
SHADOW run as the independent research-output reference. Explicit --execute.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
from tools.compare_shadow_research import compare

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / 'results' / 'smoke02_shadow' / 'main'
PART = ROOT / 'results' / 'common_recovery_hard_interrupt'
PAUSE = ROOT / 'results' / 'common_recovery_memory_pause'
OUTPUT = ROOT / 'results' / 'common_recovery_regression.json'

def call(root, extra):
    env = {**os.environ, 'OMP_NUM_THREADS':'1', 'OPENBLAS_NUM_THREADS':'1',
           'MKL_NUM_THREADS':'1', 'NUMEXPR_NUM_THREADS':'1'}
    command = [sys.executable, '-m', 'src.experiment_orchestrator', '--execute',
               '--output-root', str(root), *extra]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                               text=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return {'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}

def read(path): return json.loads(Path(path).read_text(encoding='utf8'))
def marker(root, iid): return root / 'main' / iid / 'COMPLETE.json'

def execute():
    if OUTPUT.exists() or PART.exists() or PAUSE.exists():
        raise FileExistsError('refusing to overwrite recovery evidence')
    plan = read(ROOT / 'SMOKE02_SHADOW_PLAN.json')
    ids = [s['instance_id'] for s in plan['instances']]
    first = call(PART, ['--inject-json',json.dumps({'hard_interrupt':
        {'batch_offset':0,'instance_index':2,'phase':'V4_START'}})])
    seg0 = read(PART / 'segments' / '00.json')
    event = read(PART / 'hard_interrupt_event.json')
    before = [marker(PART,i).exists() for i in ids[:4]]
    first2 = [marker(PART,i).read_bytes() for i in ids[:2] if marker(PART,i).is_file()]
    if (first['returncode'] == 0 or seg0['status'] != 'HARD_INTERRUPTED'
            or event.get('instance_id') != ids[2] or event.get('phase') != 'V4_START'
            or before != [True,True,False,False]):
        raise RuntimeError('hard interruption preconditions failed')
    resumed = call(PART, ['--stop-after','4'])
    seg1 = read(PART / 'segments' / '01.json')
    part_comparison = compare(OLD, PART / 'main', ids[:4])
    unique = len([p for p in (PART/'main').iterdir() if p.is_dir() and (p/'COMPLETE.json').is_file()]) == 4
    part_ok = (resumed['returncode'] == 0 and seg1['status'] == 'PLANNED_STOP'
               and seg1['validated_skips'] == ids[:2] and seg1['executed'] == ids[2:4]
               and first2 == [marker(PART,i).read_bytes() for i in ids[:2]]
               and unique and part_comparison['all_equal'])
    pause_first = call(PAUSE, ['--inject-json',json.dumps({'pause_after_completed':4})])
    pause0 = read(PAUSE/'segments'/'00.json')
    paused_markers = [marker(PAUSE,i).read_bytes() for i in ids[:4] if marker(PAUSE,i).is_file()]
    pause_valid = (pause_first['returncode'] == 0 and pause0['status'] == 'PAUSED_MEMORY'
                   and len(pause0['jobs']) == 1 and len(paused_markers) == 4
                   and not marker(PAUSE,ids[4]).exists()
                   and pause0.get('simulated') is True
                   and pause0.get('virtual_policy') == 2048 * 1024 ** 2
                   and pause0.get('virtual_available') == 2048 * 1024 ** 2 - 1
                   and pause0.get('actual_prelaunch', {}).get('pass') is True
                   and len(pause0.get('actual_prelaunch', {}).get('samples', [])) == 3)
    if not pause_valid: raise RuntimeError('memory pause preconditions failed')
    pause_resume = call(PAUSE, [])
    pause1 = read(PAUSE/'segments'/'01.json')
    pause_comparison = compare(OLD, PAUSE/'main', ids)
    pause_ok = (pause_resume['returncode'] == 0 and pause1['validated_skips'] == ids[:4]
                and paused_markers == [marker(PAUSE,i).read_bytes() for i in ids[:4]]
                and pause_comparison['all_equal'] and read(PAUSE/'aggregation.json')['ok'])
    result = {'partial_batch':{'ok':part_ok,'initial':first,'event':event,
             'prior_complete':[True,True,False,False],'resume':resumed,
             'validated_skips':seg1['validated_skips'],'executed_after_resume':seg1['executed'],
             'single_valid_transaction_per_instance':unique,'reference_comparison':part_comparison},
             'memory_pause':{'ok':pause_ok,'initial':pause_first,'resume':pause_resume,
             'prelaunch_jobs':len(pause0['jobs']),'validated_skips':pause1['validated_skips'],
             'reference_comparison':pause_comparison}}
    result['ok'] = part_ok and pause_ok
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('common real FAST recovery regressions:', 'PASS' if result['ok'] else 'FAIL',flush=True)
    return result['ok']

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');args=p.parse_args()
    if args.execute:raise SystemExit(0 if execute() else 1)
    raise SystemExit('explicit --execute required')

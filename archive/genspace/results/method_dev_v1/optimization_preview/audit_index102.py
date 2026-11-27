"""Compare existing reference and preview protocol traces at five budgets."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'results/method_dev_v1'
paths=[next((B/'profile_index102').glob('*/record.json')),next((B/'optimization_preview/index102_final').glob('*/record.json'))]
data=[json.loads(p.read_text(encoding='utf8'))['methods']['DG-PCE'] for p in paths]
drop={'elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds','state_machine_calls'}
budgets={k:{x:v for x,v in data[0]['budgets'][k].items() if x not in drop}=={x:v for x,v in data[1]['budgets'][k].items() if x not in drop} for k in data[0]['budgets']}
result={'pass':data[0]['history']==data[1]['history'] and all(budgets.values()),'history_equal':data[0]['history']==data[1]['history'],
        'history_message_count':len(data[0]['history']),'budget_matches':budgets,
        'verification_calls':{k:v['verification_calls'] for k,v in data[0]['budgets'].items()},
        'record_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'scope':'one pre-existing PILOT fixture; excludes timing and interpreter implementation call count'}
(Path(__file__).parent/'index102_independent_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
print(json.dumps(result,sort_keys=True))
if not result['pass']:raise SystemExit(1)

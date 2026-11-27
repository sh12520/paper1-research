"""Check regrouped FLAT order against unmodified GLOBAL make_plan."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,itertools,numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'results/method_dev_v1')]
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary
from runtime import verification_public,choose_variant
from public_search import sanitize_public,make_plan,group_bits
from rank_topk_audit import require_memory
rows=[json.loads(x) for x in (ROOT/'results/flat_audit/rank_topk_records.jsonl').read_text(encoding='utf8').splitlines()]
require_memory(2048)
lib=FastLibrary.from_graph(scope='pilot-execution')
results=[]
for fam in ('F1','F2','F3','F4'):
 for depth in (1,2):
  require_memory(2048)
  row=next((x for x in rows if x['family']==fam and x['configuration']['composition_depth']==depth and x['configuration']['capability_richness']=='rich'),None)
  if row is None:raise ValueError('missing stratified test '+fam+str(depth))
  iid=row['instance_id'];inst=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
  p=verification_public(inst.public);lib.bind_public_basis(p);view=sanitize_public(inst.public);variant=choose_variant(p,lib)
  rec=json.loads((ROOT/'results/method_dev_v1/run_protocol_fixed'/iid/'record.json').read_text(encoding='utf8'))
  b2=rec['methods']['FLAT-FEASIBILITY']['budgets']['10000']['public_feasible_b2']
  flat=make_plan(view,lib,variant,b2,'FLAT-FEASIBILITY')
  global_plan=make_plan(view,lib,variant,b2,'GLOBAL-FREQUENCY')
  bits=group_bits(lib);namebit={'O':8,'P':4,'C':1,'D':2}
  ranking=[n for n in ('O','P','C','D') if np.any(bits[flat.order]==namebit[n])]
  groups=[namebit[n] for n in ranking]+[namebit[a]|namebit[b] for a,b in itertools.combinations(ranking,2)]
  pieces=[flat.order[bits[flat.order]==b] for b in groups]
  reconstructed=np.concatenate([x for x in pieces if len(x)]) if any(len(x) for x in pieces) else np.empty(0,dtype=int)
  if not np.array_equal(reconstructed,global_plan.order):raise AssertionError('GLOBAL sorted order mismatch '+iid)
  results.append({'instance_id':iid,'n':len(reconstructed),'exact':True})
(ROOT/'results/flat_audit/global_order_tests.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
print('GLOBAL order exact equality: '+str(len(results))+'/8')

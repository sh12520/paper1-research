"""Integrate preserved V1 records with capability-conditioned class counts.
No candidate search or benchmark/seed generation. B=5000 accounting is observed;
conditioned domain counts are public availability facts even when B2 stops early.
"""
import sys
sys.dont_write_bytecode=True
import csv, json, hashlib, time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'results/flat_audit'
sys.path[:0]=[str(ROOT),str(ROOT/'results/method_dev_v1')]
import numpy as np
import src.instances as im
from src.fast_exact import FastLibrary, FastPublicCompatibility
from public_search import group_bits
from tools.smoke_01 import memory_status

def forbidden(*args,**kwargs): raise AssertionError('seed and instance generation forbidden')
im.derive_seed=forbidden; im.generate_instance=forbidden

def main():
 for _ in range(3):
  if memory_status()[1]<2048*1048576: raise RuntimeError('PAUSED_MEMORY prelaunch')
  time.sleep(.2)
 lib=FastLibrary.from_graph(scope='pilot-execution');bits=group_bits(lib)
 allowed=np.isin(bits,np.array([1,2,4,8,3,5,9,6,10,12],dtype=np.uint8)); struct=bits!=0
 rich=lib.availability.entries[31]
 scopes={d:{'legal_structural_full_rich':int(np.count_nonzero(rich.mask(d)&struct)),
            'legal_structural_method_eligible_rich':int(np.count_nonzero(rich.mask(d)&allowed))} for d in (1,2)}
 manifest=json.loads((ROOT/'results/pilot/instances_manifest.json').read_text(encoding='utf8'))
 by_id={}
 rank_path=OUT/'rank_topk_records.jsonl'
 if rank_path.exists():
  for line in rank_path.read_text(encoding='utf8').splitlines():
   item=json.loads(line); iid=item['instance_id']
   if iid in by_id: raise ValueError('duplicate rank '+iid)
   by_id[iid]=item
 cache={}; rows=[]; files=sorted((ROOT/'results/method_dev_v1/run_protocol_fixed').glob('*/record.json'))
 for path in files:
  if memory_status()[1]<768*1048576:raise RuntimeError('PAUSED_MEMORY emergency')
  rec=json.loads(path.read_text(encoding='utf8')); iid=rec['instance_id']; raw=(ROOT/'results/pilot/instances'/f'{iid}.json').read_bytes()
  if hashlib.sha256(raw).hexdigest()!=manifest[iid]['sha256']:raise AssertionError('serialized input hash '+iid)
  inst=im.deserialize_instance(raw.decode('utf8'))
  if any(getattr(inst,k)!=rec[k] or rec[k]!=manifest[iid][k] for k in ('instance_hash','public_hash','private_hash')):raise AssertionError('identity '+iid)
  p=inst.public; capkey=json.dumps([sorted(p.capabilities),p.registry],sort_keys=True,default=lambda x:x.__dict__,separators=(',',':'))
  if capkey not in cache:
   compatibility=FastPublicCompatibility(p); pattern=lib.availability.pattern(SimpleNamespace(reference=compatibility))
   idx=lib.availability.entries[pattern]
   cache[capkey]=(pattern,{d:int(np.count_nonzero(idx.mask(d)&allowed)) for d in (1,2)},
                    {d:int(np.count_nonzero(idx.mask(d)&struct)) for d in (1,2)})
  pattern, cond, allstruct=cache[capkey]; depth=p.configuration['composition_depth']
  flat=rec['methods']['FLAT-FEASIBILITY']['budgets']; glob=rec['methods']['GLOBAL-FREQUENCY']['budgets']; fb=flat['5000'];gb=glob['5000']
  for method in (fb,gb):
   if method['public_ranked_count'] != (0 if method['b2_agreement'] else cond[depth]):raise AssertionError('domain count '+iid)
  row={'instance_id':iid,'instance_hash':inst.instance_hash,'public_hash':inst.public_hash,'private_hash':inst.private_hash,
       'family':rec['family'],**p.configuration,'target_b2_no_full_o1_yes':int(rec['oracle']['recoverable']),
       'availability_pattern':pattern,'full_graph_semantic_count':len(bits),**scopes[depth],
       'conditioned_structural_all_groups':allstruct[depth], 'conditioned_structural_method_eligible':cond[depth],
       'full_o1_conditioned_all_classes':rec['oracle']['O1_candidate_count']}
  for label,r in [('flat',fb),('global',gb)]:
   row.update({label+'_metadata_unique_records_touched':len(bits),label+'_metadata_full_passes':1 if r['b2_agreement'] else 2,
    label+'_structural_feature_evaluations':r['public_ranked_count'],label+'_structural_score_evaluations':r['public_ranked_count'],
    label+'_structural_sort_candidates':r['public_ranked_count'],label+'_static_proxy_evaluations':r['b2_proxy_count'],
    label+'_exact_verification_calls':r['verification_calls'],label+'_b2_exact_calls':r['b2_verification_calls'],
    label+'_public_feasible_verified':r['public_feasible_candidates'],label+'_proposals':r['proposals'],
    label+'_agreement':int(r['agreement']),label+'_failure':int(not r['agreement']),label+'_selected_class':r['class_id'],
    label+'_selected_group_mask':r['selected_group_mask'],label+'_runtime_seconds':r['elapsed_seconds'],
    label+'_agreement_100':int((flat if label=='flat' else glob)['100']['agreement']),
    label+'_agreement_500':int((flat if label=='flat' else glob)['500']['agreement'])})
  diag=by_id.get(iid)
  if diag and diag['instance_hash']!=inst.instance_hash:raise AssertionError('rank instance mismatch')
  for key in ('rank_first_public_feasible','rank_first_mutually_acceptable','rank_selected_agreement','rank_best_nash_actually_verified','global_first_mutual_actual_verification_ordinal','global_selected_actual_verification_ordinal','global_selected_full_grouped_rank'):
   row[key]='' if not diag else diag.get(key,'')
  rows.append(row)
 assert len(rows)==1920 and len({r['instance_id'] for r in rows})==1920 and sum(r['target_b2_no_full_o1_yes'] for r in rows)==842
 if len(by_id)!=842:raise RuntimeError(f'expected 842 target diagnostic records, got {len(by_id)}')
 for row in rows:
  if row['target_b2_no_full_o1_yes'] and not row['rank_first_mutually_acceptable']: raise ValueError('missing target rank '+row['instance_id'])
 with (OUT/'per_instance.csv').open('w',encoding='utf8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 def stats(x):return (float(np.median(x)),float(np.percentile(x,95)))
 out=[]
 for pop in ('ALL','TARGET'):
  for fam in ('ALL','F1','F2','F3','F4'):
   subset=[r for r in rows if (pop=='ALL' or r['target_b2_no_full_o1_yes']) and (fam=='ALL' or r['family']==fam)]
   rr={'population':pop,'family':fam,'n':len(subset)}
   for key in ('conditioned_structural_method_eligible','flat_structural_score_evaluations','flat_exact_verification_calls','flat_public_feasible_verified','flat_proposals','flat_runtime_seconds','global_structural_score_evaluations','global_exact_verification_calls','global_runtime_seconds'):
    m,p=stats([r[key] for r in subset]);rr[key+'_median']=m;rr[key+'_p95']=p
   for label in ('flat','global'):
    for b in (100,500,5000):
     key=label+'_agreement'+('_'+str(b) if b!=5000 else '')
     rr[label+'_agreement_'+str(b)]=sum(r[key] for r in subset)
   out.append(rr)
 with (OUT/'family_summary.csv').open('w',encoding='utf8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
 (OUT/'accounting_integrity.json').write_text(json.dumps({'rows':len(rows),'target_ranks':len(by_id),'availability_registry_variants':len(cache),'scopes':scopes,'complete':True},indent=2)+'\n',encoding='utf8')
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()

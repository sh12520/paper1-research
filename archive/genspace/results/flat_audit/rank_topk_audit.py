"""Replay the frozen FLAT public plan, then do explicitly offline diagnostics.

Inputs are existing PILOT instance/records. Never generates an instance or seed.
The original method gets ONLY sanitize_public; private checks run after the plan
is completely constructed. Use python -B and write only in results/flat_audit.
"""
import sys
sys.dont_write_bytecode = True
import argparse, collections, ctypes, hashlib, json, os, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'results/method_dev_v1')]
import numpy as np
import src.instances as im
from src.fast_exact import FastLibrary
from runtime import verification_public, choose_variant
from public_search import sanitize_public, make_plan, group_bits, _proxy
from private_protocol import PrivateAgent, PublicVerifier

OUT = ROOT/'results/flat_audit'
MI = 1024*1024

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                ('total_page', ctypes.c_ulonglong), ('avail_page', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                ('avail_extended', ctypes.c_ulonglong)]

def available():
    s=MEMORYSTATUSEX(); s.length=ctypes.sizeof(s)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
        raise OSError('GlobalMemoryStatusEx failed')
    return s.avail_phys

def require_memory(floor):
    avail=available()
    if avail < floor*MI:
        raise RuntimeError(f'PAUSED_MEMORY available_MiB={avail/MI:.1f} floor={floor}')
    return avail/MI

def denied(*_a, **_k):
    raise AssertionError('benchmark seed/instance generation forbidden')
im.derive_seed=denied; im.generate_instance=denied

def calculate(slot, rec, raw, lib):
    iid=slot['instance_id']; inst=im.deserialize_instance(raw.decode('utf-8'))
    if inst.instance_hash!=rec['instance_hash'] or inst.namespace!='GENSPACE-FAIL-01-PILOT':
        raise ValueError('serialized instance identity mismatch '+iid)
    pub=verification_public(inst.public); view=sanitize_public(inst.public)
    lib.bind_public_basis(pub); variant=choose_variant(pub,lib)
    original=rec['methods']['FLAT-FEASIBILITY']; final=original['budgets']['10000']
    if final['b2_agreement'] or not rec['oracle']['recoverable'] or not final['agreement']:
        raise ValueError('outside primary target / no FLAT agreement')
    # Important: no private preference, oracle outcome or family information is
    # passed into plan generation. The stored public B2-feasible count is public.
    plan=make_plan(view,lib,variant,final['public_feasible_b2'],'FLAT-FEASIBILITY')
    if len(plan.order)!=final['public_ranked_count']:
        raise AssertionError('public scored count mismatch '+iid)
    verified=final['verification_calls']-27
    if not 0 <= verified <= len(plan.order):raise AssertionError('bad verification count')
    want=min(len(plan.order),max(500,verified))
    ids=plan.order[:want]; bits=group_bits(lib)
    pos=np.flatnonzero(ids==final['class_id'])
    if len(pos)!=1 or int(pos[0])>=verified:raise AssertionError('selected class not in exact verified prefix '+iid)
    selected_rank=int(pos[0])+1
    selected_evidence=None; statuses=[]; first_public=None; first_mutual=None
    verified_public=0; best=None; checks=PublicVerifier(pub,variant,view.depth,want,lib)
    app=PrivateAgent('application',pub,inst.private.application)
    net=PrivateAgent('network',pub,inst.private.network)
    proposals={}
    history=original['history']
    for j, event in enumerate(history):
        if event['message']=='PROPOSE':
            if j+1>=len(history) or history[j+1]['message'] not in ('ACCEPT','REJECT'):
                raise AssertionError('malformed original negotiation history')
            proposals[int(event['candidate_id'])]=(event['agent'],history[j+1]['message'])
    checked_proposals=0
    for start in range(0,want,16):
        if start%256==0:require_memory(768)
        batch=ids[start:start+16];checks.prepare_batch(batch)
        for offset,cid0 in enumerate(batch):
            cid=int(cid0);rank=start+offset+1; ev=checks.verify(cid)
            public_ok=ev is not None; mutual=False
            if public_ok:
                if first_public is None:first_public=rank
                if rank<=verified:verified_public+=1
                aa=app.respond(ev); nn=net.respond(ev); mutual=aa==nn=='ACCEPT'
                if mutual and first_mutual is None:first_mutual=rank
                if rank<=verified and mutual:
                    a,n=im.utilities(pub,inst.private,ev.actions,cell_surcharges=ev.cell_surcharges,cell_execution_costs=ev.cell_execution_costs)
                    score=a*n
                    if best is None or score>best[1]:best=(rank,score)
                if cid in proposals:
                    who, response=proposals[cid]
                    if (nn if who==0 else aa)!=response:raise AssertionError('original proposal response mismatch '+iid)
                    checked_proposals+=1
                if cid==final['class_id']:selected_evidence=(aa,nn)
            elif cid in proposals:raise AssertionError('original proposal publicly infeasible '+iid)
            statuses.append((public_ok,mutual))
    if verified_public+final['public_feasible_b2']!=final['public_feasible_candidates']:
        raise AssertionError('public-feasible verified count mismatch '+iid)
    if selected_evidence!=('ACCEPT','ACCEPT') or first_mutual is None:
        raise AssertionError('selected agreement not mutually acceptable '+iid)
    if final['class_id'] not in proposals or proposals[final['class_id']][1]!='ACCEPT':
        raise AssertionError('selected not accepted proposal '+iid)
    v,m,q,c=_proxy(view,lib,ids[:min(500,want)])
    stats={}
    for k in (10,50,100,500):
        n=min(k,len(ids)); subset=ids[:n]; masks=bits[subset]; counts=collections.Counter(int(x) for x in masks)
        qcounts=collections.Counter(format(float(x),'.12g') for x in q[:n])
        statuses_k=statuses[:n]
        stats[str(k)]={'n':n,'group_masks':{str(x):z for x,z in sorted(counts.items())},
          'offload':int(np.count_nonzero(masks & 8)),
          'quality':dict(sorted(qcounts.items())),
          'public_violation_sum':float(np.sum(v[:n])), 'feasibility_margin_sum':float(np.sum(m[:n])),
          'capability_cost_sum':float(np.sum(c[:n])),
          'complexity_sum':sum(int(x).bit_count() for x in masks),
          'public_feasible':sum(x[0] for x in statuses_k),
          'mutually_acceptable':sum(x[1] for x in statuses_k)}
    # GLOBAL uses exactly the same _proxy + lexsort order, regrouped by its
    # frozen public frequency order; quota-truncated verification ordinal is
    # distinct from rank in the untruncated grouped ordering.
    global_final=rec['methods']['GLOBAL-FREQUENCY']['budgets']['10000']
    g_stages=global_final['stages'][1:]
    namebit={'O':8,'P':4,'C':1,'D':2}
    ranking=[name for name in ('O','P','C','D') if np.any(bits[plan.order]==namebit[name])]
    groups=[(name,namebit[name]) for name in ranking]
    import itertools
    groups += [(x+'+'+y,namebit[x]|namebit[y]) for x,y in itertools.combinations(ranking,2)]
    groups=[(name,mask,plan.order[bits[plan.order]==mask]) for name,mask in groups]
    groups=[g for g in groups if len(g[2])]
    g_stage_map={x['stage']:x for x in g_stages}
    if [x['stage'] for x in g_stages] != [x[0] for x in groups[:len(g_stages)]]:
        raise AssertionError('GLOBAL stage order mismatch '+iid)
    actual=[]; grand_rank=0; selected_global_rank=None
    for name,mask,ids_group in groups:
        if name in g_stage_map:
            st=g_stage_map[name]
            if st['available']!=len(ids_group):raise AssertionError('GLOBAL stage size mismatch '+iid)
            actual.extend(ids_group[:st['verified']])
        if global_final['class_id'] is not None:
            match=np.flatnonzero(ids_group==global_final['class_id'])
            if len(match):selected_global_rank=grand_rank+int(match[0])+1
        grand_rank+=len(ids_group)
    if len(actual)!=global_final['verification_calls']-27:raise AssertionError('GLOBAL calls mismatch '+iid)
    gchecks=PublicVerifier(pub,variant,view.depth,len(actual),lib)
    gap=PrivateAgent('application',pub,inst.private.application);gnet=PrivateAgent('network',pub,inst.private.network)
    g_first=None; g_selected_ordinal=None; g_public=0;g_sel=None
    for start in range(0,len(actual),16):
        if start%256==0:require_memory(768)
        batch=actual[start:start+16];gchecks.prepare_batch(batch)
        for offset,cid0 in enumerate(batch):
            cid=int(cid0);ev=gchecks.verify(cid);ordinal=start+offset+1
            if ev is None:continue
            g_public+=1
            both=gap.respond(ev)==gnet.respond(ev)=='ACCEPT'
            if both and g_first is None:g_first=ordinal
            if cid==global_final['class_id']:g_selected_ordinal=ordinal;g_sel=both
    if g_public+global_final['public_feasible_b2']!=global_final['public_feasible_candidates']:
        raise AssertionError('GLOBAL verified public-feasible mismatch '+iid)
    if global_final['agreement'] and (not g_sel or selected_global_rank is None or g_first is None):
        raise AssertionError('GLOBAL selected mismatch '+iid)
    return {'instance_id':iid,'instance_hash':inst.instance_hash,'family':slot['family'],
        'configuration':slot['configuration'],'conditioned_count':len(plan.order),
        'metadata_touched':len(lib.keys),'public_scored':len(plan.order),
        'b2_exact_verification':27,'structural_exact_verification':verified,
        'all_exact_verification':final['verification_calls'],'public_feasible_verified':final['public_feasible_candidates'],
        'proposals':final['proposals'],'selected_class':final['class_id'],
        'rank_first_public_feasible':first_public,'rank_first_mutually_acceptable':first_mutual,
        'rank_selected_agreement':selected_rank,'rank_best_nash_actually_verified':best[0],
        'best_nash_actually_verified':best[1], 'original_structural_proposals_checked':checked_proposals,
        'diagnostic_candidates_checked':want,'topk':stats,
        'global_agreement':global_final['agreement'],
        'global_selected_full_grouped_rank':selected_global_rank,
        'global_selected_actual_verification_ordinal':g_selected_ordinal,
        'global_first_mutual_actual_verification_ordinal':g_first,
        'global_selected_offload':bool(global_final['selected_group_mask'] & 8) if global_final['agreement'] else None,
        'global_verified_structural':len(actual)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--output',default='rank_topk_records.jsonl')
    parser.add_argument('--instance-id');parser.add_argument('--resume',action='store_true'); a=parser.parse_args()
    target=OUT/a.output
    if target.exists() and not a.resume:raise ValueError('refusing to overwrite '+str(target))
    prior={}
    if target.exists():
        for line in target.read_text(encoding='utf8').splitlines():
            item=json.loads(line); iid=item['instance_id']
            if iid in prior:raise AssertionError('duplicate checkpoint '+iid)
            rec=json.loads((ROOT/'results/method_dev_v1/run_protocol_fixed'/iid/'record.json').read_text(encoding='utf8'))
            if item['instance_hash']!=rec['instance_hash'] or not rec['oracle']['recoverable']:
                raise AssertionError('checkpoint identity mismatch '+iid)
            prior[iid]=item
    require_memory(2048)
    lib=FastLibrary.from_graph(scope='pilot-execution')
    plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    manifest=json.loads((ROOT/'results/pilot/instances_manifest.json').read_text(encoding='utf8'))
    count=0;start=time.perf_counter()
    with target.open('a' if prior else 'x',encoding='utf8',newline='\n') as out:
        for slot in plan:
            iid=slot['instance_id']
            if a.instance_id and iid!=a.instance_id:continue
            if iid in prior:continue
            rec=json.loads((ROOT/'results/method_dev_v1/run_protocol_fixed'/iid/'record.json').read_text(encoding='utf8'))
            if not rec['oracle']['recoverable']:continue
            require_memory(2048)
            raw=(ROOT/'results/pilot/instances'/f'{iid}.json').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=manifest[iid]['sha256']:raise AssertionError('serialized input hash mismatch')
            result=calculate(slot,rec,raw,lib)
            out.write(json.dumps(result,sort_keys=True,allow_nan=False)+'\n');out.flush();os.fsync(out.fileno())
            count+=1
            print(f'{count} {iid} elapsed={time.perf_counter()-start:.1f}s available_MiB={available()/MI:.1f}',flush=True)
            if a.limit and count>=a.limit:break
    print(f'DONE count={count} elapsed={time.perf_counter()-start:.1f}s',flush=True)

if __name__=='__main__':main()

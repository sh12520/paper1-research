"""Independent signature-to-action evidence audit on existing PILOT fixtures.

No benchmark seeds or instances are generated. This samples legal normalized
AST classes and compares every packed cell, role set and numeric role cost to
the original AST interpreter; it does not make an effect-size claim.
"""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'results/method_dev_v1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
import src.instances as instances
from src.instances import deserialize_instance,registry_from_public
from src.fast_exact import FastLibrary,FastEvaluator
from src.fast_runner import _decode_witness
from src.state_machine import normalize,_active_roles,_role_costs
from src.registry import default_registry
from runtime import verification_public,choose_variant
from public_search import group_bits
def blocked(*a,**k):raise AssertionError('forbidden seed/instance/private full-graph evaluation')
instances.derive_seed=instances.generate_instance=blocked;FastEvaluator.evaluate=blocked
def main():
    start=time.perf_counter();slots=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[s for s in slots if s['configuration']['preference_conflict']=='high' and s['seed_index']==0]
    if len(slots)!=48:raise ValueError('fixture coverage')
    lib=FastLibrary.from_graph(scope='pilot-execution');bits=group_bits(lib);roles=tuple(sorted(default_registry()))
    n=0;cells=0;group_counts={};initialized=False
    for s in slots:
        iid=s['instance_id'];ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        pub=verification_public(ins.public);depth=ins.public.configuration['composition_depth']
        if not initialized:lib.bind_public_basis(pub);initialized=True
        v=choose_variant(pub,lib);registry=registry_from_public(pub);mask=v.mask(depth)
        for group in (0,1,2,4,8,3,5,9,6,10,12):
            ids=np.flatnonzero(mask & (bits==group))
            for cid in sorted({int(ids[k]) for k in (0,len(ids)//2,len(ids)-1)}) if len(ids) else ():
                node=normalize(_decode_witness(json.loads(v.witness(cid,depth))),pub)
                for j,(t,state) in enumerate((t,s) for t in range(pub.horizon) for s in pub.states):
                    expected=_active_roles(node,t,state);pid=int(lib.profiles[cid,j]);cells+=1
                    if expected is None:
                        if pid!=255:raise AssertionError(('idle mismatch',iid,cid,j))
                        continue
                    if pid==255:raise AssertionError(('active mismatch',iid,cid,j))
                    profile,level,active=expected;packed_level='edge' if int(lib.level[cid,j]) else 'none';maskbits=int(lib.role_masks[cid,j])
                    actual_roles={roles[i] for i in range(len(roles)) if maskbits&(1<<i)}
                    if profile!=pub.b2_profiles[pid] or level!=packed_level or active!=actual_roles:raise AssertionError(('packed cell mismatch',iid,cid,j))
                    costs,execution=_role_costs(active,registry)
                    if tuple(float(x) for x in lib.role_costs[maskbits])!=costs or float(lib.execution_costs[maskbits])!=execution:raise AssertionError(('role cost mismatch',iid,cid,j))
                n+=1;group_counts[str(group)]=group_counts.get(str(group),0)+1
    out={'pass':True,'fixture_count':len(slots),'candidate_classes_checked':n,'cells_checked':cells,'groups_checked':group_counts,
         'no_instance_seed_or_full_private_evaluation':True,'scope':'48 existing PILOT fixtures; sampled generated legal classes only',
         'seconds':time.perf_counter()-start,
         'original_source_sha256':{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ('public_search.py','private_protocol.py','runtime.py')}}
    (Path(__file__).parent/'packed_schedule_audit.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps(out,sort_keys=True),flush=True)
if __name__=='__main__':main()

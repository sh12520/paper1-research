"""Selected-only public verifier differential; no new randomized instances.

48 original PILOT public fixtures cover 4 families x 3 pressures x 2
richness x 2 depths (fixed conflict/index). Three extra synthetic public-only
boundary copies test exactly equal and adjacent representable capacities;
they are not serialized experiment instances or research data.
"""
import hashlib,json,sys,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
import src.instances as instances
from src.fast_exact import FastLibrary
from src.fast_runner import _decode_witness
from src.state_machine import verify_instance,normalize,_active_roles,_role_costs
from src.instances import deserialize_instance,registry_from_public
from public_search import group_bits
from private_protocol import PublicVerifier,_A0,_N0
from runtime import verification_public,choose_variant

def blocked(*a,**k):raise AssertionError('seed/instance generator called')
instances.generate_instance=blocked;instances.derive_seed=blocked
def ref(pub,variant,depth,cid):
    node=normalize(_decode_witness(json.loads(variant.witness(int(cid),depth))),pub)
    dummy=SimpleNamespace(public=pub,private=SimpleNamespace(application=_A0.copy(),network=_N0.copy()))
    res=verify_instance(node,dummy,depth)
    if not res.verified:return res.failed_layer,None
    reg=registry_from_public(pub);sur={};exe={}
    for t in range(pub.horizon):
        for state in pub.states:
            active=_active_roles(node,t,state)
            if active is not None:
                cost,e=_role_costs(active[2],reg);sur[(t,state)]=dict(zip(('RAN','FH','EDGE'),cost));exe[(t,state)]=e
    return 'PASS',(res.actions,sur,exe)

def compare(pub,variant,depth,lib,ids):
    verifier=PublicVerifier(pub,variant,depth,len(ids),lib);cases=[]
    for start in range(0,len(ids),16):
        chunk=ids[start:start+16];verifier.prepare_batch(chunk)
        for cid in chunk:
            expected,ev=ref(pub,variant,depth,cid);before=dict(verifier.failures)
            actual=verifier.verify(int(cid))
            failed=[k for k,v in verifier.failures.items() if v>before.get(k,0)]
            got='PASS' if actual is not None else (failed[0] if len(failed)==1 else 'INVALID_FAILURE_REPORT')
            if got!=expected:raise AssertionError(('first-failure mismatch',cid,expected,got))
            if actual is not None and (actual.actions,actual.cell_surcharges,actual.cell_execution_costs)!=ev:
                raise AssertionError(('public evidence mismatch',cid))
            cases.append(got)
    if verifier.calls!=len(ids) or verifier.batch_candidate_checks!=len(ids) or verifier._prechecked:
        raise AssertionError('budget or batch accounting mismatch')
    return cases

def main():
    t=time.perf_counter();plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[s for s in plan if s['configuration']['preference_conflict']=='high' and s['seed_index']==0]
    if len(slots)!=48:raise AssertionError('fixture coverage')
    lib=FastLibrary.from_graph(scope='pilot-execution');bits=group_bits(lib)
    outcomes={};samples=0;initialized=False;first=None
    for slot in slots:
        iid=slot['instance_id'];ins=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
        pub=verification_public(ins.public);depth=ins.public.configuration['composition_depth']
        if not initialized:lib.bind_public_basis(pub);initialized=True
        variant=choose_variant(pub,lib);mask=variant.mask(depth);picked=[]
        for group in (0,1,2,4,8,3,5,9,6,10,12):
            x=np.flatnonzero(mask&(bits==group))
            if x.size:
                for k in (0,len(x)//2,len(x)-1):
                    cid=int(x[k])
                    if cid not in picked:picked.append(cid)
        got=compare(pub,variant,depth,lib,picked);samples+=len(got)
        for k in got:outcomes[k]=outcomes.get(k,0)+1
        if first is None:first=(pub,variant,depth)
    pub,variant,depth=first
    candidates=np.flatnonzero(variant.mask(depth)&(bits==0))
    cid=next(int(i) for i in candidates if all(pub.b2_profiles[int(lib.profiles[i,j])].quality>=pub.public_constraints['min_quality'] and pub.b2_profiles[int(lib.profiles[i,j])].deadline<=pub.public_constraints['max_deadline'] for j in range(len(pub.states)*pub.horizon)))
    prof=int(lib.profiles[cid,0]);lev=int(lib.level[cid,0]);roles=int(lib.role_masks[cid,0])
    boundary=float((lib.base_demand[prof,lev]+lib.role_costs[roles])[0]); boundary_results=[]
    for cap in (np.nextafter(boundary,-np.inf),boundary,np.nextafter(boundary,np.inf)):
        data=dict(vars(pub));data['capacity']=tuple((t,s,float(cap) if (t,s)==(0,pub.states[0]) else 1e6,1e6,1e6) for t in range(pub.horizon) for s in pub.states)
        synthetic=SimpleNamespace(**data);boundary_results.append({'boundary':float(cap),'outcomes':compare(synthetic,variant,depth,lib,[cid])})
    result={'pass':True,'real_fixture_count':len(slots),'real_candidate_checks':samples,'real_outcomes':outcomes,
            'synthetic_public_only_boundaries':boundary_results,'no_seed_or_instance_generator_called':True,
            'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('private_protocol.py','runtime.py','public_search.py')},'seconds':time.perf_counter()-t}
    (Path(__file__).parent/'batch_differential_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps(result,sort_keys=True),flush=True)

if __name__=='__main__':main()

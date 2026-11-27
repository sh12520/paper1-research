"""Audit V2/V3 across 17 indexed availability patterns, no instance creation.

The 17 capability sets below are synthetic public-only registry scenarios,
not benchmark instances. The public basis is read from one existing PILOT
serialization. This verifies all indexed semantic classes, not all typed ASTs
or arbitrary public registries.
"""
import hashlib,json,sys,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
import src.instances as instances
from src.instances import deserialize_instance
from src.fast_exact import FastLibrary,FastPublicCompatibility
from src.registry import default_registry
from runtime import verification_public
def forbidden(*a,**k):raise AssertionError('new random instance or seed')
instances.derive_seed=instances.generate_instance=forbidden
GROUPS=(('observe_motion_state','apply_conditional_policy'),('apply_phased_policy',),('schedule_start',),('enable_edge_offload','reserve_edge_compute'),('set_validity_interval',))
def main():
    start=time.perf_counter();slots=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    iid=slots[0]['instance_id'];inst=deserialize_instance((ROOT/'results/pilot/instances'/f'{iid}.json').read_text(encoding='utf8'))
    base=verification_public(inst.public);lib=FastLibrary.from_graph(scope='pilot-execution');lib.bind_public_basis(base)
    invalid_v3=int(np.count_nonzero(lib.keys[:,0]!=1));rows=[]
    if invalid_v3:raise AssertionError('rich graph contains V3-invalid key')
    for pattern in (0,*range(16,32)):
        available=set(default_registry())
        for i,g in enumerate(GROUPS):
            if not pattern&(1<<i):available.difference_update(g)
        fields=dict(vars(base));fields['capabilities']=tuple(sorted(available))
        pub=SimpleNamespace(**fields);ref=FastPublicCompatibility(pub)
        am=sum(1<<i for i,yes in enumerate(ref.available) if yes)
        missing=(lib.required_role_masks & np.uint16((~am)&0xfff))!=0
        invalid=missing.copy()
        for i in range(len(ref.roles)):
            scope=lib.keys[:,1+2*i];predicate=lib.keys[:,2+2*i]
            invalid|=(scope!=255)&((not ref.available[i])|((scope & (~ref.supported[i]&255))!=0)|(predicate!=ref.expected[i]))
        for depth in (1,2):
            mask=lib.availability.entries[pattern].mask(depth);bad=int(np.count_nonzero(mask&invalid))
            rows.append({'pattern':pattern,'depth':depth,'generated':int(np.count_nonzero(mask)),'v2_invalid':bad})
            if bad:raise AssertionError(('generated indexed class failed V2',pattern,depth,bad))
    result={'pass':True,'patterns':17,'depths':[1,2],'rich_graph_invalid_v3_classes':invalid_v3,'rows':rows,
            'scope':'fixed benchmark basis and 17 indexed synthetic public availability patterns; not arbitrary invalid ASTs/registries',
            'no_new_instance_or_seed':True,'seconds':time.perf_counter()-start,
            'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('private_protocol.py','runtime.py','public_search.py')}}
    (Path(__file__).parent/'v2_universe_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({'pass':result['pass'],'patterns':17,'depths':2,'v3_invalid':invalid_v3,'seconds':result['seconds']}))
if __name__=='__main__':main()

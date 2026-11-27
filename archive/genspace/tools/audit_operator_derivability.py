"""Engineering-only root-derivability accounting for a fixed public grammar.

This records every root derivation in a bitmask, NOT a lexical-witness count or
an operator-removal causal contribution. No instance or study seed is used.
"""
from __future__ import annotations
import hashlib, json, time, itertools
from collections import Counter
from pathlib import Path
from src.engine import Domain, enumerate_compositions
from src.models import Static, If, Sequence, Delay, ValidFor, Offload
from src.compact_semantics import CompactEncoder
from src.compact_dp import compact_library
from src.fingerprints import fingerprint
from tools.audit_external_reference import fixture
from tools.audit_full_graph_reference import graph_keys

OPS=('Static','If','Sequence','Delay','ValidFor','Offload')
BIT={name:1<<i for i,name in enumerate(OPS)}
OUT=Path('results/engineering/operator_derivability_audit.json')
GRAPH=Path('results/engineering/semantic_library.graph.gz')

def filehash(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def summary(masks):
    hist=Counter(masks.values())
    per={a:sum(n for mask,n in hist.items() if mask & BIT[a]) for a in OPS}
    exclusive={a:hist[BIT[a]] for a in OPS}
    overlap={a+' & '+b:sum(n for mask,n in hist.items() if mask&BIT[a] and mask&BIT[b]) for a,b in itertools.combinations(OPS,2)}
    order={}; prefix=0
    for op in OPS:
        order[op]=sum(n for mask,n in hist.items() if mask&BIT[op] and not(mask&prefix))
        prefix |= BIT[op]
    return {'unique_total':len(masks),'derivable_by_root':per,'exclusive_root':exclusive,
            'pairwise_root_overlap':overlap,'ordered_first_root_attribution':order,
            'root_mask_histogram':{str(m):n for m,n in sorted(hist.items())}}

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    before=fingerprint(); helper_before=filehash(Path(__file__)); graph_before=filehash(GRAPH)
    start=time.perf_counter(); public=fixture(27); encoder=CompactEncoder(public)
    domain=Domain(public.b2_profiles, public.conditions, public.durations, public.offsets, public.intervals, public.offload_levels)
    masks={}
    def put(key,op): masks[key]=masks.get(key,0)|BIT[op]
    for node in enumerate_compositions(domain,1,public.capabilities):
        put(encoder.encode(node),type(node).__name__)
    one=summary(masks)
    children=tuple(compact_library(public,1))
    if len(children)!=len(masks) or set(children)!=set(masks): raise ValueError('depth-one set differs')
    for i,(left,right) in enumerate(itertools.product(children,repeat=2),1):
        put(encoder.apply_if('moving',left,right),'If')
        put(encoder.apply_sequence(1,left,right),'Sequence')
        if i%250000==0: print('pairs',i,'semantic_keys',len(masks),'seconds',round(time.perf_counter()-start,2),flush=True)
    for key in children:
        put(encoder.apply_delay(1,key),'Delay')
        put(encoder.apply_valid_for((0,2),key),'ValidFor')
        put(encoder.apply_offload('edge',key),'Offload')
    two=summary(masks)
    count=0; missing=0
    for text in graph_keys(GRAPH):
        count+=1
        if bytes.fromhex(text.decode('ascii').strip()) not in masks: missing+=1
    equal=not missing and count==len(masks)
    after=fingerprint(); helper_after=filehash(Path(__file__)); graph_after=filehash(GRAPH)
    if (before,helper_before,graph_before)!=(after,helper_after,graph_after): raise RuntimeError('source, helper, graph, configuration or dependencies changed')
    if not equal: raise ValueError('mask union does not equal graph key set')
    data={'kind':'fixed synthetic public grammar only; no experimental seed',
          'definition':'Per-root derivability denotes existence of at least one AST with that root, depth <= bound; multiple roots may overlap. Exclusive counts mean no other possible root. Ordered first-root attribution is order-dependent and is not leave-one-operator-out. This does not quantify removing an operator recursively.',
          'ops_order':OPS,'depth1':one,'depth2':two,'exact_graph_key_set_equal':equal,
          'graph_key_count':count,'wall_seconds':round(time.perf_counter()-start,3),
          'fingerprint':before,'helper_sha256':helper_before,'graph_sha256':graph_before,
          'limits':'Root derivability via compact transfer relies on documented fixed-domain context congruence; full syntax independent reference verifies union, not each root-specific set.'}
    OUT.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k not in ('fingerprint','depth1','depth2')},indent=2),flush=True)

if __name__=='__main__': main()

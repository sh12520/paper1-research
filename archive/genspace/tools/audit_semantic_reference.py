"""Bounded engineering-only streaming reference, never samples experiment seeds."""
import argparse
import tracemalloc
import time
from itertools import product
from dataclasses import asdict
from types import SimpleNamespace
from src.models import Profile
from src.registry import default_registry
from src.engine import Domain, enumerate_compositions
from src.state_machine import semantic_key

parser=argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=120)
parser.add_argument('--memory-mib', type=float, default=3500)
args=parser.parse_args()
reg=default_registry()
profiles=tuple(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
p=SimpleNamespace(b2_profiles=profiles, conditions=('moving',), durations=(1,), offsets=(1,), intervals=((0,2),), offload_levels=('edge',), capabilities=tuple(reg), registry={k:asdict(v) for k,v in reg.items()}, horizon=3, states=('still','moving'), public_constraints={'reservation_supported':True})
d=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
tracemalloc.start(); start=time.perf_counter(); seen=set(); reason='complete'; count=0
for node in enumerate_compositions(d,2,p.capabilities):
    seen.add(semantic_key(node,p)); count+=1
    if count % 1000 == 0:
        elapsed=time.perf_counter()-start; mem=tracemalloc.get_traced_memory()[1]
        if elapsed >= args.seconds: reason='time_budget'; break
        if mem >= args.memory_mib*1024*1024: reason='memory_guard'; break
elapsed=time.perf_counter()-start
print('status',reason,'syntax_processed',count,'unique_observed',len(seen),'wall_seconds',round(elapsed,3),'python_traced_peak_bytes',tracemalloc.get_traced_memory()[1], flush=True)

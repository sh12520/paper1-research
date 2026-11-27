"""Exact depth<=2 syntax-stream vs experimental DP engineering audit.

Never uses private preferences or experimental namespaces. Both sides are
independently generated and their full packed signatures sorted externally;
checksums are not used to decide equality. No truncation is permitted.
"""
from __future__ import annotations
import argparse
import base64
from dataclasses import asdict
from itertools import product
import json
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.enumeration import exact_syntax_count
from src.fingerprints import fingerprint
from src.models import Profile
from src.registry import default_registry
from src.semantic_dp import library
from tools.external_reference import external_unique, compare_sorted


def fixture(profile_count):
    """Pure synthetic fixed public fixture, with no experimental seed."""
    reg=default_registry()
    if profile_count == 27:
        profiles=tuple(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
    elif profile_count == 2:
        profiles=(Profile(.4,1.,1.), Profile(.8,1.,1.))
    else: raise ValueError('supported fixtures use 2 or 27 profiles')
    return SimpleNamespace(b2_profiles=profiles, conditions=('moving',), durations=(1,),
        offsets=(1,), intervals=((0,2),), offload_levels=('edge',),
        capabilities=tuple(reg), registry={k:asdict(v) for k,v in reg.items()},
        horizon=3, states=('still','moving'), public_constraints={'reservation_supported':True})


def run(output_dir, profile_count, depth):
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    reference=output_dir/'reference.gz'; dynamic=output_dir/'dynamic.gz'; report=output_dir/'report.json'
    if any(p.exists() for p in (reference,dynamic,report)):
        raise FileExistsError('Refusing to overwrite prior audit outputs')
    before=fingerprint(); p=fixture(profile_count); enc=CompactEncoder(p)
    domain=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
    expected=exact_syntax_count(domain,depth,p.capabilities)
    def reference_records():
        for node in enumerate_compositions(domain,depth,p.capabilities):
            yield base64.b64encode(enc.encode(node))+b'\n'
    start=perf_counter()
    ref=external_unique(reference_records(),reference,workspace=output_dir)
    ref_elapsed=perf_counter()-start
    if ref['input_count'] != expected:
        raise RuntimeError('Full reference stream count does not match syntax recurrence')
    start=perf_counter()
    values=library(p,depth)
    dp=external_unique((base64.b64encode(enc.pack(key))+b'\n' for key in values),dynamic,workspace=output_dir)
    dp_elapsed=perf_counter()-start
    same=compare_sorted(reference,dynamic)
    after=fingerprint()
    if before != after:
        raise RuntimeError('Source/config/dependency fingerprint changed during audit; results invalid')
    data={'fixture_kind':'synthetic engineering-only; no seed', 'profile_count':profile_count, 'depth':depth,
          'reference':ref, 'reference_seconds':ref_elapsed, 'dp':dp, 'dp_seconds':dp_elapsed,
          'exact_bytewise_sets_equal':same, 'fingerprint':before,
          'caveat':'signature equivalence and contextual congruence require independent proof'}
    report.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--profiles',type=int,choices=(2,27),default=2)
    parser.add_argument('--depth',type=int,choices=(1,2),default=2)
    args=parser.parse_args()
    result=run(args.output_dir,args.profiles,args.depth)
    print(json.dumps({k:v for k,v in result.items() if k!='fingerprint'},indent=2))
    if not result['exact_bytewise_sets_equal']: raise SystemExit(1)

if __name__ == '__main__': main()

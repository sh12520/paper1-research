"""Experimental compact depth-two library with public-only transfer.

Valid only after exhaustive small-domain differential tests and fixed-domain
preconditions. This is a work in progress, not a completed O1 audit.
"""
import json
from itertools import product
from .compact_semantics import CompactEncoder
from .enumeration import syntax_key
from .engine import Domain, enumerate_compositions, STRUCTURAL
from .models import If, Sequence, Delay, ValidFor, Offload
from .state_machine import normalize


def compact_library(public, depth, progress=None):
    if depth not in (0,1,2): raise ValueError('depth must be 0, 1, or 2')
    encoder=CompactEncoder(public)
    domain=Domain(tuple(public.b2_profiles),tuple(public.conditions),tuple(public.durations),
                  tuple(public.offsets),tuple(public.intervals),tuple(public.offload_levels))
    from .instances import registry_from_public
    from .state_machine import bind_capabilities
    from .registry import default_registry
    reg=registry_from_public(public)
    roles={role for role in default_registry() if bind_capabilities({role},public.capabilities,reg) is not None}
    result={}; normal_forms={}
    for node in enumerate_compositions(domain,min(depth,1),roles):
        key=encoder.encode(node); witness=syntax_key(node)
        if key not in result or witness<result[key]: result[key]=witness
        norm=syntax_key(normalize(node, public))
        if key in normal_forms and normal_forms[key]!=norm:
            raise ValueError('child semantics not composition-congruent: multiple normalized ASTs')
        normal_forms[key]=norm
    if depth<2: return result
    children=tuple(result.items())
    def put(key,text):
        old=result.get(key)
        if old is None or text<old: result[key]=text
    # All source children are depth<=1. Every such semantic equivalence class
    # has one normalized AST by the exhaustive check above. Different public
    # domains may fail this check instead of silently losing candidates.
    for index,((lk,lw),(rk,rw)) in enumerate(product(children,repeat=2),1):
        if progress is not None and index % 10000 == 0: progress(index, len(result))
        for condition in (public.conditions if STRUCTURAL[If] <= roles else ()):
            key=encoder.combine('If',condition,lk,rk)
            put(key,'["If",'+json.dumps(condition,separators=(',',':'))+','+lw+','+rw+']')
        for duration in (public.durations if STRUCTURAL[Sequence] <= roles else ()):
            key=encoder.combine('Sequence',duration,lk,rk)
            put(key,'["Sequence",'+json.dumps(duration,separators=(',',':'))+','+lw+','+rw+']')
    for key,witness in children:
        for name,values in (('Delay',public.offsets if STRUCTURAL[Delay] <= roles else ()),('ValidFor',public.intervals if STRUCTURAL[ValidFor] <= roles else ()),('Offload',public.offload_levels if STRUCTURAL[Offload] <= roles else ())):
            for value in values:
                new=encoder.combine(name,value,key)
                put(new,'['+json.dumps(name)+','+json.dumps(value,separators=(',',':'))+','+witness+']')
    return result

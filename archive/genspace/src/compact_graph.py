"""Compact semantic witness DAG for the fixed depth-two public grammar.

The result stores each witness as operator + parameter + child pool indices,
not recursively repeated AST strings. The small depth<=1 pool is shared.
"""
from dataclasses import dataclass
from itertools import product
import json
from .compact_dp import compact_library
from .compact_semantics import CompactEncoder
from .engine import STRUCTURAL
from .instances import registry_from_public
from .registry import default_registry
from .state_machine import bind_capabilities
from .models import If, Sequence, Delay, ValidFor, Offload

@dataclass
class GraphLibrary:
    entries: dict
    pool: tuple

    def render(self, token):
        op,param,l,r=token
        if op=='Static': return param
        text='['+json.dumps(op)+','+param+','+self.pool[l]
        if r>=0: text+=','+self.pool[r]
        return text+']'


def graph_library(public, progress=None):
    """Return compact witness graph after public-only DP through depth two."""
    encoder=CompactEncoder(public)
    first=compact_library(public,1)
    # Include depth-zero textual ASTs used as children by depth-one witnesses.
    descendants=set(first.values())
    for text in first.values():
        tree=json.loads(text)
        if tree[0]=='Static': continue
        descendants.add(json.dumps(tree[2],separators=(',',':')))
        if tree[0] in ('If','Sequence'): descendants.add(json.dumps(tree[3],separators=(',',':')))
    pool=tuple(sorted(descendants)); rank={text:i for i,text in enumerate(pool)}
    def token(text):
        tree=json.loads(text); op=tree[0]
        if op=='Static': return ('Static',text,-1,-1)
        param=json.dumps(tree[1],separators=(',',':'))
        l=rank[json.dumps(tree[2],separators=(',',':'))]
        r=rank[json.dumps(tree[3],separators=(',',':'))] if op in ('If','Sequence') else -1
        return (op,param,l,r)
    result={key:token(text) for key,text in first.items()}
    children=tuple((key,rank[text]) for key,text in first.items())
    registry=registry_from_public(public)
    roles={role for role in default_registry() if bind_capabilities({role},public.capabilities,registry) is not None}
    def put(key,tok):
        old=result.get(key)
        if old is None or tok<old: result[key]=tok
    for index,((lk,l),(rk,r)) in enumerate(product(children,repeat=2),1):
        if progress and index%10000==0: progress(index,len(result))
        if STRUCTURAL[If] <= roles:
            for value in public.conditions: put(encoder.apply_if(value,lk,rk),('If',json.dumps(value,separators=(',',':')),l,r))
        if STRUCTURAL[Sequence] <= roles:
            for value in public.durations: put(encoder.apply_sequence(value,lk,rk),('Sequence',json.dumps(value,separators=(',',':')),l,r))
    for key,idx in children:
        for cls,name,values,fn in ((Delay,'Delay',public.offsets,encoder.apply_delay),(ValidFor,'ValidFor',public.intervals,encoder.apply_valid_for),(Offload,'Offload',public.offload_levels,encoder.apply_offload)):
            if STRUCTURAL[cls] <= roles:
                for val in values: put(fn(val,key),(name,json.dumps(val,separators=(',',':')),idx,-1))
    return GraphLibrary(result,pool)

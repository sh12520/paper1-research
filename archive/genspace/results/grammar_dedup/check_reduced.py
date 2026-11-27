"""Exhaustive small-profile differential using two existing serialized inputs."""

from dataclasses import replace
from pathlib import Path
import json
import struct
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'results/grammar_gate'),str(ROOT/'results/method_dev_v1')]

import numpy as np

from dedup_search import DedupCursor
from grammar_search import Limits
from protocol_adapter import _public_cost_basis
from public_search import _proxy, group_bits, sanitize_public
from runtime import verification_public
from src.compact_semantics import CompactEncoder
from src.engine import enumerate_compositions
from src.enumeration import public_domain, syntax_key
from src.instances import deserialize_instance
from src.state_machine import normalize


def native_order(public, rows, encoder):
    keys = sorted(rows)
    arrays = np.frombuffer(b''.join(keys),dtype=np.uint8).reshape(-1,49)
    cells = arrays[:,25:].reshape(-1,6,4)
    bits = group_bits(SimpleNamespace(keys=arrays))
    groups = np.asarray([int(x).bit_count() for x in bits],dtype=np.uint8)
    ids = np.flatnonzero((groups>=1)&(groups<=2))
    lib = _public_cost_basis(public,encoder.roles)
    lib.profiles, lib.level = cells[:,:,0], cells[:,:,1]
    lib.role_masks = (cells[:,:,2].astype(np.uint16)<<8)|cells[:,:,3].astype(np.uint16)
    v,m,q,c = _proxy(sanitize_public(public),lib,ids)
    score = v-0.025*m+0.02*c+0.08*(1.-q)
    score += 0.01*groups[ids]
    order = np.lexsort((ids,score))
    return [(keys[ids[j]],float(score[j])) for j in order]


def check(iid, depth):
    path=ROOT/'results/pilot/instances'/(iid+'.json')
    public=deserialize_instance(path.read_text(encoding='utf8')).public
    public=replace(public,b2_profiles=tuple(public.b2_profiles[i] for i in (0,10,26)))
    cursor=DedupCursor(verification_public(public),depth,Limits(30.,500000,260000))
    retrieved=[]
    while (entry:=cursor.next_contract()) is not None:
        retrieved.append(entry)

    # Independent test lane. Only the deliberately reduced profile domain is
    # enumerated and no benchmark input or graph artifact is produced.
    encoder=CompactEncoder(public)
    minimum={}
    n=0
    for node in enumerate_compositions(public_domain(public),depth,public.capabilities):
        n+=1
        k=encoder.encode(node)
        raw=syntax_key(node)
        if k not in minimum or raw<minimum[k][0]:
            minimum[k]=(raw,node)
    expected=native_order(public,minimum,encoder)
    if len(expected)!=len(retrieved):
        raise AssertionError(f'reduced semantic counts differ: {iid}, depth {depth}')
    for actual,(key,score) in zip(retrieved,expected):
        if (actual.key!=key or struct.pack('>d',actual.score)!=struct.pack('>d',score)
                or actual.raw_witness!=minimum[key][0]
                or actual.witness!=syntax_key(normalize(minimum[key][1],public))):
            raise AssertionError(f'order, score bits or lexical witness differs: {iid}, depth {depth}')
    return dict(instance_id=iid, depth=depth, profiles=len(public.b2_profiles), syntax_leaves=n,
                exact_structural_classes=len(expected), prefixes={k:min(k,len(expected)) for k in (10,50,100,500)},
                total_order_score_bits_and_witness='PASS')


def main():
    fixtures=('F1__medium__medium__rich__d2__s0','F4__low__medium__sparse__d2__s0')
    results=[check(iid,d) for iid in fixtures for d in (1,2)]
    text=json.dumps(results,indent=2)+'\n'
    with (HERE/'reduced_correctness.json').open('x',encoding='utf8') as out:
        out.write(text)
    print(text,flush=True)


if __name__=='__main__':
    main()

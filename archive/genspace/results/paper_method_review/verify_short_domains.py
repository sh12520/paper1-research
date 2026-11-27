"""Independently exhaust the five fixed small depth-3 capability domains."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'results/method_dev_v1')]

import numpy as np

from public_search import (COST_WEIGHT, GROUP_COMPLEXITY_WEIGHT, MARGIN_WEIGHT,
                           QUALITY_WEIGHT, _proxy, group_bits, sanitize_public)
from src.compact_semantics import CompactEncoder
from src.engine import STRUCTURAL, ast_depth, enumerate_compositions, required_capabilities
from src.enumeration import exact_syntax_count, public_domain, syntax_key
from src.instances import deserialize_instance, registry_from_public
from src.models import If, Sequence
from src.registry import default_registry
from src.state_machine import _signature, bind_capabilities, normalize


FIXTURES = (
    'F1__low__high__sparse__d2__s0',
    'F2__high__high__sparse__d2__s0',
    'F3__high__high__sparse__d2__s0',
    'F4__medium__high__sparse__d2__s0',
    'F4__high__high__sparse__d2__s0',
)
DEPTH = 3
MAX_TINY_SYNTAX = 500
ARCHIVE = ROOT/'results/depth3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def exact_proxy(public, keys, roles):
    """Use the original FLAT vector arithmetic on in-memory reduced rows."""
    rows = np.frombuffer(b''.join(keys),dtype=np.uint8).reshape(-1,49)
    cells = rows[:,25:].reshape(-1,6,4)
    group = np.array([int(x).bit_count() for x in group_bits(SimpleNamespace(keys=rows))],dtype=np.uint8)
    registry = registry_from_public(public)
    energy = np.zeros(1 << len(roles),dtype=np.float64)
    cost = np.zeros((len(energy),3),dtype=np.float64)
    for mask in range(len(energy)):
        chosen = tuple(registry[role] for i,role in enumerate(roles) if mask & (1 << i))
        energy[mask] = sum(item.execution_cost for item in chosen)
        cost[mask] = [sum(item.resource_cost.get(resource,0.) for item in chosen)
                      for resource in ('RAN','FH','EDGE')]
    tiny = SimpleNamespace(profiles=cells[:,:,0], level=cells[:,:,1],
                           role_masks=(cells[:,:,2].astype(np.uint16) << 8)|cells[:,:,3],
                           role_costs=cost, execution_costs=energy)
    allowed = np.flatnonzero((group>=1)&(group<=4))
    v,m,q,c = _proxy(sanitize_public(public),tiny,allowed)
    score = v-MARGIN_WEIGHT*m+COST_WEIGHT*c+QUALITY_WEIGHT*(1.-q)
    score += GROUP_COMPLEXITY_WEIGHT*group[allowed]
    sorted_order = np.lexsort((allowed,score))
    return [(keys[allowed[j]],float(score[j])) for j in sorted_order],dict(Counter(map(int,group)))


def independent_domain(public):
    registry = registry_from_public(public)
    reference = default_registry()
    if any(role not in registry or _signature(registry[role])!=_signature(cap) for role,cap in reference.items()):
        raise ValueError('changed frozen public registry')
    available = {role for role in reference if bind_capabilities({role},public.capabilities,registry) is not None}
    operator_domains = {cls.__name__: getattr(public,field) for cls,field in zip(
        STRUCTURAL,('conditions','durations','offsets','intervals','offload_levels')) if STRUCTURAL[cls]<=available}
    if any(STRUCTURAL[binary]<=available for binary in (If,Sequence)):
        raise ValueError('fixture has a binary production; refuse further enumeration')
    domain = public_domain(public)
    predicted = exact_syntax_count(domain,DEPTH,available)
    if not (0<predicted<=MAX_TINY_SYNTAX and len(domain.profiles)==27):
        raise ValueError('fixture is outside the preselected tiny full-profile scopes')

    encoder = CompactEncoder(public)
    representatives = {}
    syntax = 0
    for node in enumerate_compositions(domain,DEPTH,available):
        syntax += 1
        if ast_depth(node)>DEPTH or not required_capabilities(node)<=available:
            raise AssertionError('enumerated AST falls outside its public grammar scope')
        key = encoder.encode(node)
        if len(key)!=49 or key[0]!=1:
            raise ValueError('fixed grammar unexpectedly yielded an invalid semantic signature')
        token = syntax_key(node)
        if key not in representatives or token<representatives[key][0]:
            representatives[key] = (token,node)
    if syntax!=predicted:
        raise AssertionError('independent raw enumeration cardinality differs from recurrence')
    order, groups = exact_proxy(public,sorted(representatives),encoder.roles)
    rows = [(key,score,syntax_key(normalize(representatives[key][1],public))) for key,score in order]
    return rows, {'operator_domains':operator_domains, 'profiles':len(domain.profiles),
                  'raw_syntax_all':syntax, 'semantic_all':len(representatives),
                  'semantic_static':groups.get(0,0), 'semantic_structural':len(rows),
                  'semantic_count_by_mechanism_groups':groups}


def sealed_compare(iid, rows, counts, case, seal_entry):
    source = ARCHIVE/'development'/(iid+'.json')
    if seal_entry['path']!=source.relative_to(ARCHIVE).as_posix() or digest(source)!=seal_entry['sha256']:
        raise ValueError('depth-3 case does not match the clean online seal')
    if case['effective_depth']!=DEPTH or case['instance_id']!=iid or case['derived_query_id']!=iid+'__METHOD_D3':
        raise ValueError('effective depth or fixture identity mismatch')
    emitted = case['topk']
    actual = [bytes.fromhex(row['key']) for row in emitted]
    expected = [key for key,_,_ in rows]
    if len(emitted)!=len(set(actual)) or set(actual)!=set(expected):
        raise AssertionError('sealed and independent complete structural semantic sets differ')
    if any(actual[j]!=key or struct.pack('>d',emitted[j]['score'])!=struct.pack('>d',score)
           or emitted[j]['witness']!=witness for j,(key,score,witness) in enumerate(rows)):
        raise AssertionError('sealed order, binary64 score or normalized witness differs')

    prefix = sha256(b''.join(struct.pack('>d',score)+key for key,score,_ in rows)).hexdigest()
    for k in (100,500):
        cert = case['k_certificates'][str(k)]
        if (len(rows)>=k or cert['status']!='EXACT_TOPK_CERTIFIED' or cert['full_domain_exhausted'] is not True
                or cert['returned']!=len(rows) or cert['frontier_remaining']!=0
                or cert['frontier_min_lb'] is not None or cert['buffered_best_score'] is not None
                or cert['prefix_sha256']!=prefix):
            raise AssertionError('sealed short certificate is not exact domain exhaustion')
    return {'instance_id':iid, **counts, 'sealed_emitted_count':len(emitted),
            'domain_equality':'PASS','order_bits_and_witness':'PASS',
            'exhaustion_certificates':'PASS','prefix_sha256':prefix,
            'sealed_case_sha256':seal_entry['sha256']}


def main():
    current_manifest = read(ROOT/'results/pilot/instances_manifest.json')
    independent = {}
    for iid in FIXTURES:
        source = ROOT/'results/pilot/instances'/(iid+'.json')
        raw = source.read_bytes()
        instance = deserialize_instance(raw.decode('utf8'))
        identity = {'sha256':sha256(raw).hexdigest(),'instance_hash':instance.instance_hash,
                    'public_hash':instance.public_hash,'private_hash':instance.private_hash}
        if identity!=current_manifest.get(iid) or instance.namespace!='GENSPACE-FAIL-01-PILOT':
            raise ValueError('independent fixture does not match its original public source')
        independent[iid] = (*independent_domain(instance.public),identity)

    # Only after computing every independent domain do we read any result.
    summary = read(ARCHIVE/'gate_summary.json')
    seal_path = ARCHIVE/'development/search_seal.json'
    seal = read(seal_path)
    clean = seal['guard']
    seal_sha = digest(seal_path)
    if (summary['status']!='DEPTH3_PARTIAL' or summary['online_seal_sha256']!=seal_sha
            or seal.get('complete_batch') is not True or seal['manifest']['phase']!='development'
            or clean.get('pass') is not True or clean.get('blocked')!=[]
            or not clean.get('forbidden_call_counts') or any(clean['forbidden_call_counts'].values())):
        raise ValueError('official archived gate or clean development seal does not match')
    case_rows = []
    for iid,(rows,counts,identity) in independent.items():
        source = ARCHIVE/'development'/(iid+'.json')
        case = read(source)
        if case['serialized_sha256']!=identity['sha256'] or case['instance_hash']!=identity['instance_hash']:
            raise ValueError('sealed case does not use the original serialized instance')
        case_rows.append(sealed_compare(iid,rows,counts,case,seal['cases'][iid]))

    output = {'status':'PASS','archived_gate_status':summary['status'],
              'development_seal_sha256':seal_sha,'cases':case_rows}
    text = json.dumps(output,indent=2,allow_nan=False)+'\n'
    with (HERE/'short_domain_verification.json').open('x',encoding='utf8') as out:
        out.write(text)
    print(text,flush=True)


if __name__=='__main__':
    main()

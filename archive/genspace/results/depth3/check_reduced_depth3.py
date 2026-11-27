"""Exhaustive differential on deliberately reduced existing public domains.

Does not instantiate a benchmark case, read a result, or load a graph.  The
independent lane materializes only the finite test grammars from this script.
"""

from dataclasses import replace
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from struct import pack
from types import SimpleNamespace
import argparse
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'results/grammar_gate'), str(ROOT/'results/grammar_dedup'),
                str(ROOT/'results/method_dev_v1')]

import numpy as np

from public_search import (_proxy, group_bits, sanitize_public, COST_WEIGHT,
                           MARGIN_WEIGHT, QUALITY_WEIGHT, GROUP_COMPLEXITY_WEIGHT)
from runtime import verification_public
from grammar_search import Limits, decode_witness
from abstract_semantics import AbstractSemantics, ClauseHole
from src.compact_semantics import CompactEncoder
from src.engine import ast_depth, enumerate_compositions, required_capabilities
from src.enumeration import public_domain, syntax_key
from src.instances import deserialize_instance, registry_from_public
from src.models import Delay, If, Offload, Sequence, Static, ValidFor
from src.state_machine import normalize


OPERATORS = ('conditions', 'durations', 'offsets', 'intervals', 'offload_levels')
FIXTURE = 'F1__medium__medium__rich__d2__s0'
CASES = (
    ('conditional-delay', ('conditions', 'offsets'), (), (0,-1)),
    ('phased-validity', ('durations', 'intervals'), (), (0,-1)),
    ('offload', ('offload_levels',), (), (0,-1)),
    ('offload-unavailable', ('offload_levels',), ('enable_edge_offload', 'reserve_edge_compute'), (0,-1)),
    ('four-groups', ('conditions','durations','offsets','offload_levels'), (), (-1,)),
)


def reduced_public(source, fields, unavailable, profiles):
    return replace(source, b2_profiles=tuple(source.b2_profiles[i] for i in profiles),
                   capabilities=tuple(c for c in source.capabilities if c not in unavailable),
                   **{field: tuple(getattr(source, field)) if field in fields else () for field in OPERATORS})


def score_order(public, keys, encoder, depth):
    """Unchanged frozen NumPy proxy/sort with only reduced-test packed rows."""
    keys = sorted(keys)
    rows = np.frombuffer(b''.join(keys), dtype=np.uint8).reshape(-1,49)
    cells = rows[:,25:].reshape(-1,6,4)
    group = np.array([int(bits).bit_count() for bits in group_bits(SimpleNamespace(keys=rows))], dtype=np.uint8)
    roles = encoder.roles
    registry = registry_from_public(public)
    execution = np.empty(1 << len(roles), dtype=np.float64)
    resource = np.empty((len(execution),3), dtype=np.float64)
    for mask in range(len(execution)):
        members = tuple(registry[r] for i,r in enumerate(roles) if mask & (1 << i))
        execution[mask] = sum(cap.execution_cost for cap in members)
        resource[mask] = [sum(cap.resource_cost.get(r,0.) for cap in members) for r in ('RAN','FH','EDGE')]
    packed = SimpleNamespace(profiles=cells[:,:,0], level=cells[:,:,1],
                             role_masks=(cells[:,:,2].astype(np.uint16)<<8)|cells[:,:,3],
                             role_costs=resource, execution_costs=execution)
    ids = np.arange(len(keys), dtype=np.int64)
    v,m,q,c = _proxy(sanitize_public(public), packed, ids)
    score = v - MARGIN_WEIGHT*m + COST_WEIGHT*c + QUALITY_WEIGHT*(1.-q)
    score += GROUP_COMPLEXITY_WEIGHT*group
    by_key = {key:(float(score[i]), int(group[i])) for i,key in enumerate(keys)}
    eligible = np.flatnonzero((group>=1)&(group<=(2 if depth<=2 else 4)))
    ordering = np.lexsort((eligible,score[eligible]))
    return [(keys[i],float(score[i])) for i in eligible[ordering]], by_key


def independent_complete(public, depth):
    encoder = CompactEncoder(public)
    minimum, shapes, count = {}, {}, 0
    for node in enumerate_compositions(public_domain(public), depth, public.capabilities):
        count += 1
        if ast_depth(node)>depth or not required_capabilities(node)<=set(public.capabilities):
            raise AssertionError('independent typed enumerator escaped its scope')
        key = encoder.encode(node)
        if len(key)!=49 or key[0]!=1:
            raise AssertionError('reduced grammar yielded an invalid signature')
        shapes.setdefault(shape_prefix(node),set()).add(key)
        raw = syntax_key(node)
        prior = minimum.get(key)
        if prior is None or raw<prior[0]:
            minimum[key] = (raw,node)
    ordering, score = score_order(public,minimum,encoder,depth)
    return encoder, minimum, ordering, score, count, shapes


def shape_prefix(node):
    """Independent preorder description of a shape or leftmost-hole prefix."""
    def walk(term):
        if isinstance(term,ClauseHole):
            yield None
        elif isinstance(term,Static):
            yield ('Static',)
        elif isinstance(term,If):
            yield ('If',term.condition)
            yield from walk(term.then_clause)
            yield from walk(term.else_clause)
        elif isinstance(term,Sequence):
            yield ('Sequence',term.duration)
            yield from walk(term.first)
            yield from walk(term.second)
        elif isinstance(term,(Delay,ValidFor,Offload)):
            value = (term.offset if isinstance(term,Delay) else
                     term.interval if isinstance(term,ValidFor) else term.level)
            yield (type(term).__name__,value)
            yield from walk(term.clause)
        else:
            raise TypeError('unrecognized shape')

    result = tuple(walk(node))
    if None not in result:
        return result
    end = result.index(None)
    if any(entry is not None for entry in result[end:]):
        raise AssertionError('non-prefix shape refinement in audited cursor')
    return result[:end]


def symbolic_identity(key,groups):
    values, cells = [], []
    for pos in range(25,49,4):
        p,level,hi,lo = key[pos:pos+4]
        if p==255:
            cells.append((-1,0,0))
        else:
            if p not in values:
                values.append(p)
            cells.append((values.index(p),level,hi*256+lo))
    return (key[:25],tuple(cells),len(values),groups),tuple(values)


def instrument_bounds(cursor_cls, shapes, exact, depth, observations):
    """Check the actual two queue boundaries against the independent oracle."""
    prefix_scores = {}
    prefix_allowed = set()
    allowed_max = 2 if depth<=2 else 4
    for shape, keys in shapes.items():
        min_score = min(exact[k][0] for k in keys)
        any_eligible = any(1<=exact[k][1]<=allowed_max for k in keys)
        for end in range(len(shape)+1):
            prefix = shape[:end]
            prefix_scores[prefix] = min(min_score,prefix_scores.get(prefix,min_score))
            if any_eligible:
                prefix_allowed.add(prefix)
    assignments = {}
    for key,(score,groups) in exact.items():
        if 1<=groups<=allowed_max:
            identity,values = symbolic_identity(key,groups)
            assignments.setdefault(identity,[]).append((values,score))

    class CheckedCursor(cursor_cls):
        def _push_shape(self, shape):
            initial = len(self.shapes)
            value = super()._push_shape(shape)
            prefix = shape_prefix(shape)
            if len(self.shapes)==initial:
                if prefix in prefix_allowed:
                    raise AssertionError('queued skeleton pruning lost an independent signature')
            else:
                actual = next(bound for bound,_,member in self.shapes if member is shape)
                if actual>prefix_scores[prefix]:
                    raise AssertionError('skeleton frontier bound exceeds independent descendant score')
                observations['live_skeleton_bounds_checked'] += 1
            return value

        def _bound(self, template, values, current_mask, used):
            bound = super()._bound(template,values,current_mask,used)
            identity = template.prefix,template.cells,template.visible,template.groups
            index = len(values)
            possible = [score for profiles,score in assignments[identity]
                        if profiles[:index]==values and current_mask & (1<<profiles[index])]
            if not possible or bound>min(possible):
                raise AssertionError('profile-assignment frontier bound exceeds independent descendant score')
            observations['live_assignment_bounds_checked'] += 1
            return bound

    return CheckedCursor


def check_envelope(abstract, node, key, env):
    required = sum(1<<i for i in range(12) if key[1+2*i]!=255)
    if env.mandatory_roles & ~required or required & ~env.possible_roles:
        raise AssertionError(f'completed footprint outside envelope: {node!r}')
    for cell, pos in zip(env.cells, range(25,49,4)):
        profile, level, hi, lo = key[pos:pos+4]
        if profile==255:
            if not cell.may_idle:
                raise AssertionError('complete idle cell is not in its envelope')
            continue
        profile_mask = cell.edge_profiles if level else cell.local_profiles
        role_mask = (hi << 8)|lo
        if not (profile_mask & (1<<profile)) or cell.mandatory_roles & ~role_mask or role_mask & ~cell.possible_roles:
            raise AssertionError('complete profile or cell role is not in its envelope')
        if any(x<lower or x>upper for x,lower,upper in zip(
                abstract.demand_basis[level][profile],cell.demand_min,cell.demand_max)):
            raise AssertionError('complete demand is not in its envelope')


def check_all_partial_bounds(public, depth, scorer, encoder, exact, count):
    grammar = AbstractSemantics(verification_public(public), depth)
    observed = {'partial_bounds_checked':0, 'abstract_complete_keys_checked':0,
                'pruned_domains_checked':0, 'syntax_leaves_checked':0}

    def descend(node):
        envelope = grammar.envelope(node)
        if envelope.complete:
            key = encoder.encode(node)
            if grammar.encoded(node)!=key:
                raise AssertionError('packed transfer differs from independent interpreter')
            check_envelope(grammar,node,key,envelope)
            score,groups = exact[key]
            possible = int(1<=groups<=(2 if depth<=2 else 4))
            observed['abstract_complete_keys_checked'] += 1
            observed['syntax_leaves_checked'] += 1
        else:
            children = [descend(child) for child in grammar.expand(node)]
            if not children:
                raise AssertionError('unknown or empty partial subtree')
            score = min(item[0] for item in children)
            possible = sum(item[1] for item in children)
            observed['partial_bounds_checked'] += 1
        if scorer.lower_bound(envelope)>score:
            raise AssertionError(f'bound exceeds independent minimum completion score: {node!r}')
        if envelope.max_groups==0 or depth<=2 and envelope.min_groups>2:
            observed['pruned_domains_checked'] += 1
            if possible:
                raise AssertionError('partial pruning excluded an eligible descendant')
        return score,possible

    descend(grammar.root)
    if observed['syntax_leaves_checked']!=count:
        raise AssertionError('typed expansions did not cover the independent reduced syntax count')
    return observed


def check(cursor_cls, case, public, depth):
    encoder, minimum, expected, exact, count, shapes = independent_complete(public,depth)
    observations = {'live_skeleton_bounds_checked':0,'live_assignment_bounds_checked':0}
    checked_cls = instrument_bounds(cursor_cls,shapes,exact,depth,observations)
    cursor = checked_cls(verification_public(public),depth,Limits(90.,300000,180000))
    previous = None
    consumed = 0
    for key,score in expected:
        actual = cursor.next_contract()
        if actual is None:
            raise AssertionError('cursor ended before the independent ordering')
        raw,node = minimum[key]
        if (actual.key!=key or pack('>d',actual.score)!=pack('>d',score) or
                actual.raw_witness!=raw or actual.witness!=syntax_key(normalize(node,public))):
            raise AssertionError(f'ordered signature, binary64 score or representative differs at {case} depth {depth} rank {consumed+1}')
        if previous is not None and (actual.score,actual.key)<=previous:
            raise AssertionError('duplicate or non-increasing certified result')
        previous = actual.score,actual.key
        raw_node = decode_witness(actual.raw_witness)
        if ast_depth(raw_node)>depth or not required_capabilities(raw_node)<=set(public.capabilities):
            raise AssertionError('emitted witness exceeds tested depth or capability set')
        consumed += 1
    if cursor.next_contract() is not None:
        raise AssertionError('cursor contains a surplus signature')
    counters = check_all_partial_bounds(public,depth,cursor.scorer,encoder,exact,count)
    return dict(case=case, depth=depth, profiles=len(public.b2_profiles), syntax=count,
                all_signatures=len(minimum), structural_signatures=consumed, **counters, **observations,
                eligible_signatures_by_group={n:sum(exact[k][1]==n for k,_ in expected) for n in range(1,5)},
                exact_complete_order_score_bits_witness='PASS'), set(k for k,_ in expected)


def predicate_negative_control(cursor_cls, public):
    scoped = reduced_public(public,('offload_levels',),(),(0,))
    scoped = replace(scoped,public_constraints=dict(scoped.public_constraints,reservation_supported=False))
    try:
        cursor = cursor_cls(verification_public(scoped),3,Limits(5.,1000,1000))
        cursor.next_contract()
    except ValueError as exc:
        if 'predicate' not in str(exc).lower():
            raise
        return {'status':'PASS','exception':str(exc)}
    raise AssertionError('search did not fail closed outside the positive public predicates')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cursor',default='depth_search:DepthCursor',help='module:class of the searched cursor')
    parser.add_argument('--output',type=Path,default=HERE/'reduced_depth3_correctness.json')
    args = parser.parse_args()
    lane_module, lane_class = args.cursor.split(':',1)
    cursor_module = import_module(lane_module)
    cursor_cls = getattr(cursor_module,lane_class)
    path = ROOT/'results/pilot/instances'/(FIXTURE+'.json')
    public = deserialize_instance(path.read_text(encoding='utf8')).public
    reports = []
    for case,fields,unavailable,profiles in CASES:
        reduced = reduced_public(public,fields,unavailable,profiles)
        shallow, old = check(cursor_cls,case,reduced,2)
        deeper, new = check(cursor_cls,case,reduced,3)
        if not old<=new:
            raise AssertionError('increasing the allowed depth dropped existing signatures')
        deeper['structural_signatures_new_at_depth3'] = len(new-old)
        if case=='conditional-delay' and not new-old:
            raise AssertionError('positive depth-3 control has no new structural signature')
        if case=='offload-unavailable' and new:
            raise AssertionError('capability negative control retained an offload signature')
        if case=='four-groups' and deeper['eligible_signatures_by_group'][4]==0:
            raise AssertionError('depth3 positive control did not exercise all four structural groups')
        reports.extend((shallow,deeper))
        print(json.dumps(deeper),flush=True)
    report = dict(status='PASS',fixture=FIXTURE,cursor=args.cursor,cases=reports,
                  depth_search_sha256=sha256(Path(cursor_module.__file__).read_bytes()).hexdigest(),
                  predicate_negative_control=predicate_negative_control(cursor_cls,public))
    with args.output.open('x',encoding='utf8') as out:
        json.dump(report,out,indent=2)
        out.write('\n')


if __name__=='__main__':
    main()

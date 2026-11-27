"""Graph-free, certifying best-first traversal of partial contracts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
import json
from math import isfinite
from time import perf_counter

from src.enumeration import syntax_key
from src.models import Delay, If, Offload, Sequence, Static, ValidFor
from src.registry import default_registry
from src.state_machine import normalize

from abstract_semantics import AbstractSemantics


@dataclass(frozen=True, slots=True)
class Limits:
    wall_seconds: float
    expanded: int
    frontier: int


class SearchLimit(RuntimeError):
    """The current frontier cannot be certified within the engineering limits."""


@dataclass(slots=True)
class Entry:
    key: bytes
    score: float
    raw_witness: str
    witness: str | None = None


def decode_witness(text):
    from src.models import Profile

    def decode(node):
        name, value, *children = node
        if name == 'Static':
            return Static(Profile(*node[1:]))
        constructor = {'If': If, 'Sequence': Sequence, 'Delay': Delay,
                       'ValidFor': ValidFor, 'Offload': Offload}[name]
        return constructor(tuple(value) if name=='ValidFor' else value,
                           *(decode(child) for child in children))

    return decode(json.loads(text))


def _score(violation, margin, quality, cost, groups):
    """Preserve the original FLAT operation order and binary64 roundings."""
    value = violation - 0.025 * margin + 0.02 * cost + 0.08 * (1. - quality)
    return value + 0.01 * groups


class FlatPublicScore:
    """Original FLAT proxy, factoring out only request-independent arithmetic."""

    def __init__(self, public):
        params = public.resource_parameters
        self.quality = tuple(float(p.quality) for p in public.b2_profiles)
        self.demand = tuple(
            ((float(p.quality), float(p.rate) * params['fh_rate_factor'], 0.),
             (float(p.quality) * params['offload_ran_factor'],
              (float(p.rate) * params['fh_rate_factor']) * params['offload_fh_factor'],
              float(p.quality) * params['offload_edge_factor']))
            for p in public.b2_profiles
        )
        raw = {(t,s):(float(a),float(b),float(c)) for t,s,a,b,c in public.capacity}
        self.capacity = tuple(raw[t,s] for t in range(public.horizon) for s in public.states)
        if len(self.capacity) != 6 or any(not isfinite(x) or x < 0 for cell in self.capacity for x in cell):
            raise ValueError('expected six cells with finite nonnegative capacities')
        self.denominator = tuple(tuple(max(x,1e-9) for x in cell) for cell in self.capacity)
        roles = tuple(sorted(default_registry()))
        self.role_index = {role:i for i,role in enumerate(roles)}
        self.groups = tuple(tuple(self.role_index[r] for r in g) for g in (
            ('apply_conditional_policy',), ('schedule_start',),
            ('apply_phased_policy','set_validity_interval'), ('enable_edge_offload',),
        ))
        reg = public.registry

        @lru_cache(maxsize=4096)
        def cost_total(mask):
            active = [reg[r] for i,r in enumerate(roles) if mask & (1 << i)]
            execution = sum(float(r['execution_cost']) for r in active)
            a,b,c = (sum(float(r['resource_cost'].get(resource,0.)) for r in active)
                     for resource in ('RAN','FH','EDGE'))
            return execution + ((a + b) + c)

        self.cost_total = cost_total
        self.terms = tuple(
            tuple(tuple(self._terms(j,self.demand[i][level]) for level in (0,1))
                  for i in range(len(self.quality)))
            for j in range(6)
        )
        self.idle = tuple(self._terms(j,(0.,0.,0.)) for j in range(6))
        self.bound_terms = lru_cache(maxsize=4096)(self._terms)
        self.cell_values = tuple(
            tuple(tuple(self._cell_value(self.terms[j][i][level],self.quality[i])
                        for i in range(len(self.quality))) for level in (0,1))
            for j in range(6)
        )
        self.cell_idle = tuple(self._cell_value(terms,0.) for terms in self.idle)
        self.cell_joint_min = lru_cache(maxsize=4096)(self._cell_joint_min)
        largest_violation = max(max(terms[0]) for cell in self.terms for levels in cell for terms in levels)
        # Both evaluation trees have fewer than 128 rounded operations, with
        # this scale dominating their absolute coefficient-weighted inputs.
        # A factor of 2^-38 is much larger than 2*gamma_128 in binary64.
        max_role_cost = cost_total((1 << len(roles))-1)
        self.joint_roundoff = 2.**-38 * (32. + 32.*largest_violation + 12.*max_role_cost)
        if not isfinite(self.joint_roundoff):
            raise ValueError('unsupported score scale for finite joint bound')

    @staticmethod
    def _cell_value(terms, quality):
        v,m = terms
        return (((v[0]+v[1])+v[2])/18. - 0.025*((m[0]+m[1])+m[2])/18.
                - 0.08*quality/6.)

    def _cell_joint_min(self, j, local, edge, idle):
        lo = self.cell_idle[j] if idle else float('inf')
        for mask, values in zip((local,edge), self.cell_values[j]):
            while mask:
                bit = mask & -mask
                lo = min(lo, values[bit.bit_length()-1])
                mask ^= bit
        return lo

    def group_count(self, key):
        return sum(any(key[1+2*i] != 255 for i in group) for group in self.groups)

    def _terms(self, j, demand):
        excess = tuple((x-cap)/den for x,cap,den in zip(demand,self.capacity[j],self.denominator[j]))
        return tuple(max(z,0.) for z in excess), tuple(max(-1.,min(-z,1.)) for z in excess)

    def score(self, key, groups):
        violation = margin = quality = cost = 0.
        for j in range(6):
            pos = 25 + 4*j
            i,level = key[pos],key[pos+1]
            if i == 255:
                v,m = self.idle[j]
            else:
                v,m = self.terms[j][i][level]
                quality += self.quality[i]
                cost += self.cost_total((key[pos+2] << 8) | key[pos+3])
            for term in v:
                violation += term
            for term in m:
                margin += term
        return _score(violation/18., margin/18., quality/6., cost/6., groups)

    def lower_bound(self, envelope):
        violation = margin = quality = cost = joint = 0.
        for j,cell in enumerate(envelope.cells):
            v,m = self.bound_terms(j,cell.demand_min)
            for term in v:
                violation += term
            for term in m:
                margin += term
            quality += cell.quality_max
            cost += cell.min_cost
            joint += self.cell_joint_min(j,cell.local_profiles,cell.edge_profiles,cell.may_idle)
        bound = _score(violation/18., margin/18., quality/6., cost/6., envelope.min_groups)
        joint += 0.02*(cost/6.) + 0.08 + 0.01*envelope.min_groups
        bound = max(bound, joint-self.joint_roundoff)
        if not isfinite(bound):
            raise ValueError('nonfinite partial-contract score bound')
        return bound


class Cursor:
    """Yield certified unique signatures plus their canonical public witnesses."""

    def __init__(self, view, depth, limits, sample=None):
        self.started = perf_counter()
        self.limits = limits
        self.public = view
        self.grammar = AbstractSemantics(view,depth)
        self.scorer = FlatPublicScore(view)
        self.encoder = self.grammar.encoder
        self.key = self.grammar.encoded
        self.partial = []
        self.complete = []
        self.seen = {}
        self.serial = count()
        self.stats = dict(partial_generated=0, partial_expanded=0, frontier_peak=0, complete_syntax=0,
                          unique_semantics=0, scores=0, duplicates=0, emitted=0,
                          structural_domain_rejects=0, pruned_illegal=0, peak_working_set_bytes=0)
        self.sample = sample
        self.next_sample_at = 0
        self.last_emitted_score = None
        self._push(self.grammar.root)

    def _push(self, node):
        env = self.grammar.envelope(node)
        if env.min_groups > 2 or env.max_groups == 0:
            self.stats['pruned_illegal'] += 1
            return
        bound = self.scorer.lower_bound(env)
        heappush(self.partial, (bound, next(self.serial), node, env.complete))
        self.stats['partial_generated'] += 1
        self.stats['frontier_peak'] = max(self.stats['frontier_peak'],len(self.partial))

    def _check_limits(self, force=False):
        if len(self.partial) > self.limits.frontier:
            raise SearchLimit('frontier_limit')
        if self.stats['partial_expanded'] >= self.limits.expanded:
            raise SearchLimit('expanded_limit')
        if perf_counter()-self.started >= self.limits.wall_seconds:
            raise SearchLimit('wall_time_limit')
        popped = self.stats['partial_expanded'] + self.stats['complete_syntax']
        if self.sample is not None and (force or popped >= self.next_sample_at):
            self.stats['peak_working_set_bytes'] = max(self.stats['peak_working_set_bytes'],self.sample())
            self.next_sample_at = popped + 512

    def static_entries(self):
        return sorted((Entry(self.encoder.encode(node),0.,syntax_key(node),syntax_key(node))
                       for node in map(Static,self.public.b2_profiles)), key=lambda entry:entry.key)

    def _insert(self, node, bound):
        self.stats['complete_syntax'] += 1
        key = self.key(node)
        groups = self.scorer.group_count(key)
        if not 1 <= groups <= 2:
            self.stats['structural_domain_rejects'] += 1
            return
        previous = self.seen.get(key)
        if previous is not None:
            self.stats['duplicates'] += 1
            if previous.witness is not None:
                raise AssertionError('semantic duplicate discovered after certified emission')
            if bound > previous.score:
                raise AssertionError('duplicate lower bound exceeds its exact score')
        raw = syntax_key(node)
        if previous is not None:
            if raw < previous.raw_witness:
                previous.raw_witness = raw
            return
        self.stats['unique_semantics'] += 1
        score = self.scorer.score(key,groups)
        if not isfinite(score):
            raise ValueError('nonfinite exact score')
        if bound > score:
            raise AssertionError('leaf lower bound exceeds exact FLAT score')
        self.stats['scores'] += 1
        entry = Entry(key,score,raw)
        self.seen[key] = entry
        heappush(self.complete, (score,key,entry))

    def next_contract(self):
        # Strict comparison drains *all* possibly equal-scoring syntax. This
        # also closes potential lexically smaller witnesses for a known key.
        while self.partial and (not self.complete or self.partial[0][0] <= self.complete[0][0]):
            self._check_limits()
            bound,_,node,complete = heappop(self.partial)
            if complete:
                self._insert(node,bound)
            else:
                self.stats['partial_expanded'] += 1
                for child in self.grammar.expand(node):
                    self._push(child)
        if not self.complete:
            return None
        self._check_limits(force=True)
        _,_,entry = heappop(self.complete)
        raw = decode_witness(entry.raw_witness)
        canonical = normalize(raw,self.public)
        if self.key(canonical) != entry.key:
            raise AssertionError('complete transfer differs from frozen public normalization')
        entry.witness = syntax_key(canonical)
        self.stats['emitted'] += 1
        self.last_emitted_score = entry.score
        return entry

    def metrics(self):
        elapsed = perf_counter()-self.started
        deferred = None
        if self.last_emitted_score is not None:
            deferred = sum(not complete and bound > self.last_emitted_score
                           for bound,_,_,complete in self.partial)
        return dict(self.stats, frontier_remaining=len(self.partial),
                    frontier_min_lb=self.partial[0][0] if self.partial else None,
                    bound_deferred_subtrees=deferred, last_emitted_score=self.last_emitted_score,
                    buffered_complete=len(self.complete), wall_s=elapsed)

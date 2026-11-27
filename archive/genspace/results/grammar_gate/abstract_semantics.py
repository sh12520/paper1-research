"""Typed holes and public abstract transfers over the benchmark contract DSL."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import isfinite
from types import MappingProxyType

from src.compact_semantics import CompactEncoder
from src.engine import BASE, STRUCTURAL
from src.instances import registry_from_public
from src.models import Delay, If, Offload, Sequence, Static, ValidFor
from src.state_machine import _role_costs, bind_capabilities


@dataclass(frozen=True, slots=True, eq=False)
class GrammarDomain:
    profiles: tuple
    productions: tuple
    available_roles: frozenset


@dataclass(frozen=True, slots=True)
class ClauseHole:
    remaining_depth: int
    domain: GrammarDomain = field(repr=False)
    nonterminal = 'Clause'


@dataclass(frozen=True, slots=True)
class ProfileHole:
    domain: GrammarDomain = field(repr=False)
    allowed_mask: int
    remaining_depth = 0
    nonterminal = 'Profile'


@dataclass(frozen=True, slots=True)
class CellEnvelope:
    local_profiles: int
    edge_profiles: int
    may_idle: bool
    mandatory_roles: int
    possible_roles: int
    demand_min: tuple
    demand_max: tuple
    quality_min: float
    quality_max: float
    deadline_min: float
    deadline_max: float
    rate_min: float
    rate_max: float
    min_cost: float

    @property
    def may_active(self):
        return bool(self.local_profiles or self.edge_profiles)

    @property
    def must_active(self):
        return not self.may_idle

    @property
    def possible_offload(self):
        return frozenset(state for state, possible in (
            ('idle', self.may_idle), ('none', self.local_profiles), ('edge', self.edge_profiles)) if possible)


@dataclass(frozen=True, slots=True)
class Envelope:
    cells: tuple
    mandatory_roles: int
    possible_roles: int
    min_groups: int
    max_groups: int
    quality_max: float
    min_cost: float
    complete: bool


def groups_from_roles(roles, role_masks):
    return sum(bool(roles & mask) for mask in role_masks)


def sum_ordered(values):
    """Mirror FLAT's sequential binary64 accumulator, not Python 3.12 sum."""
    total = 0.0
    for value in values:
        total += value
    return total


class AbstractSemantics:
    """Finite grammar summaries. The query never consumes acceptance or a graph."""

    def __init__(self, public, max_depth, *, cache_size=16_384):
        if type(max_depth) is not int or not 0 <= max_depth <= 3:
            raise ValueError('supported grammar depth is 0..3')
        if int(public.horizon) != 3 or tuple(public.states) != ('still', 'moving'):
            raise ValueError('unsupported public cell grid')
        profiles = tuple(public.b2_profiles)
        if not profiles or len(profiles) > 254 or len(set(profiles)) != len(profiles):
            raise ValueError('invalid public profile domain')
        if any(not all(isfinite(x) for x in (p.quality, p.deadline, p.rate)) or
               not (0 <= p.quality <= 1 and p.deadline > 0 and p.rate > 0) for p in profiles):
            raise ValueError('invalid public scalar profile')
        self.public = public
        self.profiles = profiles
        self.profile_index = MappingProxyType({profile: i for i, profile in enumerate(profiles)})
        self.all_profiles = (1 << len(profiles)) - 1
        self.encoder = CompactEncoder(public)
        registry = registry_from_public(public)
        self.roles = self.encoder.roles
        self.role_bits = {role: 1 << i for i, role in enumerate(self.roles)}
        available = frozenset(role for role in self.roles
                              if bind_capabilities({role}, public.capabilities, registry) is not None)
        if not BASE <= available:
            raise ValueError('benchmark mandatory Static capabilities are unavailable')
        self.base_mask = self.mask(BASE)
        self.op_masks = {op: self.mask(roles) for op, roles in STRUCTURAL.items()}
        self.group_masks = (
            self.mask(('apply_conditional_policy',)), self.mask(('schedule_start',)),
            self.mask(('apply_phased_policy', 'set_validity_interval')),
            self.mask(('enable_edge_offload',)),
        )
        productions = ((If, tuple(public.conditions)), (Sequence, tuple(public.durations)),
                       (Delay, tuple(public.offsets)), (ValidFor, tuple(public.intervals)),
                       (Offload, tuple(public.offload_levels)))
        for cls, vals in productions:
            if len(set(vals)) != len(vals) or any(not self.valid_parameter(cls, v) for v in vals):
                raise ValueError(f'invalid public {cls.__name__} parameter domain')
        self.domain = GrammarDomain(profiles, tuple((cls, vals) for cls, vals in productions
                                                     if STRUCTURAL[cls] <= available), available)
        self.productions = dict(self.domain.productions)
        self.clause_holes = tuple(ClauseHole(depth, self.domain) for depth in range(max_depth+1))
        self.profile_hole = ProfileHole(self.domain,self.all_profiles)
        self.root = self.clause_holes[-1]
        parameters = dict(public.resource_parameters)
        self.demand_basis = tuple(tuple(self.demand(p, offload, parameters) for p in profiles)
                                  for offload in (False, True))
        # Exact scalar proxy cost for every runtime-role mask; the lattice min
        # then guarantees a binary64-safe lower bound for any mandatory mask.
        costs = []
        for mask in range(1 << len(self.roles)):
            resource, execution = _role_costs(tuple(r for r in self.roles if mask & self.role_bits[r]), registry)
            costs.append(execution + sum_ordered(resource))
        self.role_cost = tuple(costs)
        for bit in self.role_bits.values():
            for mask in range(len(costs)):
                if not mask & bit:
                    costs[mask] = min(costs[mask], costs[mask | bit])
        self.role_superset_min_cost = tuple(costs)
        self._cached_cell = lru_cache(maxsize=8192)(self._make_cell)
        self._cached_numeric = lru_cache(maxsize=8192)(self._numeric)
        self._cached_envelope = lru_cache(maxsize=cache_size)(self._envelope)
        self.encoded = lru_cache(maxsize=cache_size)(self._complete_key)
        self.idle = self._cached_cell(0, 0, True, 0, 0)
        self.static_any = self._static(self.all_profiles, False)
        self.by_depth = [self.static_any]
        for depth in range(1, max_depth+1):
            child = self.by_depth[depth-1]
            modes = [self.static_any]
            for cls, vals in self.domain.productions:
                for value in vals:
                    modes.append(self._transfer(cls, value, child,
                                                child if cls in (If, Sequence) else None))
            self.by_depth.append(self._union(modes, False))

    def _complete_key(self, node):
        if isinstance(node, Static):
            return self.encoder.encode(node)
        if isinstance(node, If):
            return self.encoder.apply_if(node.condition,self.encoded(node.then_clause),self.encoded(node.else_clause))
        if isinstance(node, Sequence):
            return self.encoder.apply_sequence(node.duration,self.encoded(node.first),self.encoded(node.second))
        if isinstance(node, Delay):
            return self.encoder.apply_delay(node.offset,self.encoded(node.clause))
        if isinstance(node, ValidFor):
            return self.encoder.apply_valid_for(node.interval,self.encoded(node.clause))
        if isinstance(node, Offload):
            return self.encoder.apply_offload(node.level,self.encoded(node.clause))
        raise TypeError('compact transfer requires a complete Clause')

    def mask(self, roles):
        return sum(self.role_bits[role] for role in roles)

    @staticmethod
    def demand(profile, offload, parameters):
        q, rate = float(profile.quality), float(profile.rate)
        if offload:
            loads = (q*parameters['offload_ran_factor'],
                     rate*parameters['fh_rate_factor']*parameters['offload_fh_factor'],
                     q*parameters['offload_edge_factor'])
        else:
            loads = (q, rate*parameters['fh_rate_factor'], 0.0)
        if any(not isfinite(x) or x < 0 for x in loads):
            raise ValueError('unsupported public demand basis')
        return loads

    @staticmethod
    def valid_parameter(cls, value):
        if cls is If:
            return value == 'moving'
        if cls in (Sequence, Delay):
            return type(value) is int and 0 < value < 3
        if cls is ValidFor:
            return (type(value) is tuple and len(value) == 2 and all(type(x) is int for x in value)
                    and 0 <= value[0] < value[1] <= 3)
        return cls is Offload and value == 'edge'

    @staticmethod
    def is_complete(node):
        if isinstance(node, (ClauseHole, ProfileHole)):
            return False
        if isinstance(node, Static):
            return not isinstance(node.profile, ProfileHole)
        if isinstance(node, If):
            return AbstractSemantics.is_complete(node.then_clause) and AbstractSemantics.is_complete(node.else_clause)
        if isinstance(node, Sequence):
            return AbstractSemantics.is_complete(node.first) and AbstractSemantics.is_complete(node.second)
        return AbstractSemantics.is_complete(node.clause)

    def expand(self, node):
        """Replace just the first unresolved typed hole in preorder."""
        if isinstance(node, ClauseHole):
            if node.domain is not self.domain:
                raise ValueError('foreign clause hole')
            choices = [Static(self.profile_hole)]
            if node.remaining_depth:
                hole = self.clause_holes[node.remaining_depth-1]
                for cls, vals in self.domain.productions:
                    choices.extend(cls(value, hole, hole) if cls in (If, Sequence) else cls(value, hole)
                                   for value in vals)
            return tuple(choices)
        if isinstance(node, Static):
            if isinstance(node.profile, ProfileHole):
                if node.profile.domain is not self.domain:
                    raise ValueError('foreign profile hole')
                allowed = tuple(self._ids(node.profile.allowed_mask))
                if len(allowed) <= 3:
                    return tuple(Static(self.profiles[i]) for i in allowed)
                for field in ('quality','rate','deadline'):
                    partitions = {}
                    for i in allowed:
                        value = getattr(self.profiles[i],field)
                        partitions[value] = partitions.get(value,0) | (1 << i)
                    if len(partitions) > 1:
                        return tuple(Static(ProfileHole(self.domain,mask)) for mask in partitions.values())
                raise AssertionError('profile partition did not split unique profiles')
            return ()
        if isinstance(node, (If, Sequence)):
            cls = type(node)
            if cls is If:
                parameter, left, right = node.condition, node.then_clause, node.else_clause
            else:
                parameter, left, right = node.duration, node.first, node.second
            if not self.is_complete(left):
                return tuple(cls(parameter, choice, right) for choice in self.expand(left))
            return tuple(cls(parameter, left, choice) for choice in self.expand(right))
        cls = type(node)
        parameter = node.offset if cls is Delay else node.interval if cls is ValidFor else node.level
        return tuple(cls(parameter, choice) for choice in self.expand(node.clause))

    def envelope(self, node):
        return self._cached_envelope(node)

    @staticmethod
    def _ids(mask):
        while mask:
            bit = mask & -mask
            yield bit.bit_length()-1
            mask ^= bit

    def _numeric(self, local, edge, may_idle):
        states = tuple((i, level) for level, mask in enumerate((local, edge)) for i in self._ids(mask))
        demand = [self.demand_basis[level][i] for i, level in states]
        scalars = [(self.profiles[i].quality, self.profiles[i].deadline, self.profiles[i].rate)
                   for i, _ in states]
        if may_idle:
            demand.append((0., 0., 0.))
            scalars.append((0., 0., 0.))
        minima = tuple(min(column) for column in zip(*demand))
        maxima = tuple(max(column) for column in zip(*demand))
        stats = tuple(bound for column in zip(*scalars) for bound in (min(column), max(column)))
        return minima, maxima, stats

    def _make_cell(self, local, edge, may_idle, mandatory, possible):
        low, high, scalar = self._cached_numeric(local, edge, may_idle)
        if may_idle:
            mandatory, cost = 0, 0.
        else:
            cost = self.role_superset_min_cost[mandatory]
        return CellEnvelope(local, edge, may_idle, mandatory, possible, low, high, *scalar, cost)

    def _env(self, cells, mandatory, possible, complete):
        return Envelope(tuple(cells), mandatory, possible, groups_from_roles(mandatory, self.group_masks),
                        groups_from_roles(possible, self.group_masks),
                        sum_ordered(c.quality_max for c in cells)/6.,
                        sum_ordered(c.min_cost for c in cells)/6., complete)

    def _static(self, profile_mask, complete):
        c = self._cached_cell(profile_mask, 0, False, self.base_mask, self.base_mask)
        return self._env((c,)*6, self.base_mask, self.base_mask, complete)

    def _or_cell(self, a, b):
        if a is b:
            return a
        return self._cached_cell(a.local_profiles | b.local_profiles, a.edge_profiles | b.edge_profiles,
                                 a.may_idle or b.may_idle, a.mandatory_roles & b.mandatory_roles,
                                 a.possible_roles | b.possible_roles)

    def _union(self, envelopes, complete):
        first, *rest = envelopes
        cells, mandatory, possible = first.cells, first.mandatory_roles, first.possible_roles
        for option in rest:
            cells = tuple(self._or_cell(a, b) for a,b in zip(cells,option.cells))
            mandatory &= option.mandatory_roles
            possible |= option.possible_roles
        return self._env(cells, mandatory, possible, complete)

    def _forced_if_collapse(self, left, right, complete):
        """Intersect summaries under the assumption the normalized keys tie."""
        mandatory = left.mandatory_roles | right.mandatory_roles
        possible = left.possible_roles & right.possible_roles
        if mandatory & ~possible:
            return None
        cells = []
        for a,b in zip(left.cells,right.cells):
            cell_must = a.mandatory_roles | b.mandatory_roles
            cell_may = a.possible_roles & b.possible_roles
            local, edge = a.local_profiles & b.local_profiles, a.edge_profiles & b.edge_profiles
            if cell_must & ~cell_may:
                local = edge = 0
            idle = a.may_idle and b.may_idle
            if not (local or edge or idle):
                return None
            cells.append(self._cached_cell(local, edge, idle, cell_must, cell_may) if local or edge else self.idle)
        return self._env(cells, mandatory, possible, complete)

    def _transfer(self, cls, val, left, right=None, *, exact_equal=None):
        if cls is If:
            collapse = self._forced_if_collapse(left, right, left.complete and right.complete)
            if exact_equal is True:
                if collapse is None:
                    raise AssertionError('identical branch semantics have disjoint envelopes')
                return collapse
            if exact_equal is False:
                collapse = None
        else:
            collapse = None
        own = self.op_masks[cls]
        cells = []
        for t in range(3):
            for state in range(2):
                local, child = t, left
                if cls is If:
                    child = left if state == 1 else right
                elif cls is Sequence and t >= val:
                    local, child = t-val, right
                elif cls is Delay:
                    if t < val:
                        cells.append(self.idle)
                        continue
                    local = t-val
                elif cls is ValidFor:
                    start, end = val
                    if not start <= t < end:
                        cells.append(self.idle)
                        continue
                    local = t-start
                cell = child.cells[2*local+state]
                if not cell.may_active:
                    cells.append(self.idle)
                    continue
                local_profiles, edge_profiles = cell.local_profiles, cell.edge_profiles
                if cls is Offload:
                    local_profiles, edge_profiles = 0, local_profiles | edge_profiles
                cells.append(self._cached_cell(local_profiles, edge_profiles, cell.may_idle,
                                               cell.mandatory_roles | own, cell.possible_roles | own))
        merged = self._env(cells, own | left.mandatory_roles | (right.mandatory_roles if right else 0),
                           own | left.possible_roles | (right.possible_roles if right else 0),
                           left.complete and (right is None or right.complete))
        return self._union((merged, collapse), merged.complete) if collapse is not None else merged

    def _envelope(self, node):
        if isinstance(node, ClauseHole):
            if node.domain is not self.domain:
                raise ValueError('foreign clause hole')
            return self.by_depth[node.remaining_depth]
        cls = type(node)
        if cls is Static:
            if isinstance(node.profile, ProfileHole):
                if node.profile.domain is not self.domain:
                    raise ValueError('foreign profile hole')
                return self._static(node.profile.allowed_mask,False)
            return self._static(1 << self.profile_index[node.profile], True)
        if cls is If:
            parameter, parent_left, parent_right = node.condition, node.then_clause, node.else_clause
        elif cls is Sequence:
            parameter, parent_left, parent_right = node.duration, node.first, node.second
        elif cls in (Delay, ValidFor, Offload):
            parameter = node.offset if cls is Delay else node.interval if cls is ValidFor else node.level
            parent_left, parent_right = node.clause, None
        else:
            raise TypeError('expected a typed contract or a Clause hole')
        if parameter not in self.productions.get(cls, ()):
            raise ValueError('unavailable operator or parameter outside public domain')
        left = self.envelope(parent_left)
        right = None if parent_right is None else self.envelope(parent_right)
        equal = None
        if cls is If and left.complete and right.complete:
            equal = parent_left == parent_right
            if not equal and self._forced_if_collapse(left, right, True) is not None:
                equal = self.encoded(parent_left) == self.encoded(parent_right)
        return self._transfer(cls, parameter, left, right, exact_equal=equal)

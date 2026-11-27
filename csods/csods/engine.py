"""Finite-domain diagnostic enumeration and a deliberately explicit validator.

No utility, acceptance threshold, or private agent object is accepted by the
enumerator. Depth counts operators, so Static has depth zero. Enumeration is
lazy: the full depth-three Cartesian grammar can be extremely large.
"""
from dataclasses import dataclass
from itertools import product
from math import isfinite
from typing import Callable, Mapping

from .models import Profile, Static, If, Sequence, Delay, ValidFor, Offload
from .registry import default_registry


@dataclass(frozen=True)
class Domain:
    profiles: tuple[Profile, ...]
    conditions: tuple[str, ...] = ()
    durations: tuple[int, ...] = ()
    offsets: tuple[int, ...] = ()
    intervals: tuple[tuple[int, int], ...] = ()
    offload_levels: tuple[str, ...] = ()


STRUCTURAL = {
    If: frozenset(('observe_motion_state', 'apply_conditional_policy')),
    Sequence: frozenset(('apply_phased_policy',)),
    Delay: frozenset(('schedule_start',)),
    ValidFor: frozenset(('set_validity_interval',)),
    Offload: frozenset(('enable_edge_offload', 'reserve_edge_compute')),
}
BASE = frozenset(('set_quality', 'select_latency_profile', 'set_rate',
                  'reserve_ran_resource', 'reserve_fh_resource'))


def enumerate_fixed(profiles):
    """Enumerate the supplied finite profile Cartesian domain without pruning."""
    for profile in profiles:
        yield Static(profile)


def enumerate_compositions(domain: Domain, max_depth: int, available_capabilities):
    """Enumerate every syntactically typed tree over *exactly* this domain.

    Children may have any depth below the configured bound; ordered branches
    and semantically redundant trees are retained. Capability availability is
    public; preconditions, semantics and private acceptance are not used.
    Static profiles must include B2 values for nested comparison. Inputs should
    be unique for distinct syntactic trees; duplicates do not affect existence.
    """
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError('max_depth must be a nonnegative integer')
    available = frozenset(available_capabilities)
    def trees(depth):
        yield from enumerate_fixed(domain.profiles)
        if not depth:
            return
        if STRUCTURAL[If] <= available:
            for condition in domain.conditions:
                for left in trees(depth - 1):
                    for right in trees(depth - 1):
                        yield If(condition, left, right)
        if STRUCTURAL[Sequence] <= available:
            for duration in domain.durations:
                for left in trees(depth - 1):
                    for right in trees(depth - 1):
                        yield Sequence(duration, left, right)
        for cls, values in ((Delay, domain.offsets), (ValidFor, domain.intervals),
                            (Offload, domain.offload_levels)):
            if STRUCTURAL[cls] <= available:
                for value in values:
                    for child in trees(depth - 1):
                        yield cls(value, child)
    yield from trees(max_depth)


def required_capabilities(node):
    if isinstance(node, Static):
        return BASE
    if isinstance(node, If):
        return STRUCTURAL[If] | required_capabilities(node.then_clause) | required_capabilities(node.else_clause)
    if isinstance(node, Sequence):
        return STRUCTURAL[Sequence] | required_capabilities(node.first) | required_capabilities(node.second)
    if isinstance(node, (Delay, ValidFor, Offload)):
        return STRUCTURAL[type(node)] | required_capabilities(node.clause)
    raise TypeError('unknown AST node')


def ast_depth(node):
    if isinstance(node, Static):
        return 0
    if isinstance(node, If):
        return 1 + max(ast_depth(node.then_clause), ast_depth(node.else_clause))
    if isinstance(node, Sequence):
        return 1 + max(ast_depth(node.first), ast_depth(node.second))
    return 1 + ast_depth(node.clause)


def _required_scopes(node, enclosing=frozenset()):
    """Track scopes in which each operation is used, including nesting."""
    if isinstance(node, Static):
        scopes = enclosing or frozenset(('static',))
        return {cap: set(scopes) for cap in BASE}
    scope = {If: 'conditional', Sequence: 'phased', Delay: 'delayed',
             ValidFor: 'validity', Offload: 'offload'}[type(node)]
    result = {cap: {scope} for cap in STRUCTURAL[type(node)]}
    children = ((node.then_clause, node.else_clause) if isinstance(node, If) else
                (node.first, node.second) if isinstance(node, Sequence) else (node.clause,))
    for child in children:
        for cap, uses in _required_scopes(child, enclosing | {scope}).items():
            result.setdefault(cap, set()).update(uses)
    return result


def _typed(node):
    if type(node) is Static:
        p = node.profile
        return (type(p) is Profile and all(type(x) in (int, float) and isfinite(x)
                for x in (p.quality, p.deadline, p.rate)))
    if type(node) is If:
        return type(node.condition) is str and _typed(node.then_clause) and _typed(node.else_clause)
    if type(node) is Sequence:
        return type(node.duration) is int and _typed(node.first) and _typed(node.second)
    if type(node) is Delay:
        return type(node.offset) is int and _typed(node.clause)
    if type(node) is ValidFor:
        return (type(node.interval) is tuple and len(node.interval) == 2 and
                all(type(x) is int for x in node.interval) and _typed(node.clause))
    if type(node) is Offload:
        return type(node.level) is str and _typed(node.clause)
    return False


@dataclass(frozen=True)
class PublicContext:
    horizon: int
    states: tuple[str, ...]
    conditions: Mapping[str, Callable[[str], bool]]
    offload_levels: tuple[str, ...]
    capabilities: frozenset[str]
    # Every required capability must have an explicit successful precondition.
    preconditions: Mapping[str, Callable[[object], bool]]
    capacity: Mapping[tuple[int, str], Mapping[str, float]]
    # demand(profile, offload level, time, state) -> RAN/FH/EDGE loads
    demand: Callable
    # Additional hard constraints over a complete compiled action sequence.
    hard_constraints: Callable
    # None chooses the reference registry; explicit registry supports audits.
    registry: Mapping | None = None


@dataclass(frozen=True)
class PrivateAcceptance:
    application_utility: Callable
    network_utility: Callable
    application_reservation: float
    network_reservation: float


@dataclass(frozen=True)
class Result:
    verified: bool
    failed_layer: str | None
    reason: str
    actions: tuple = ()
    application_utility: float | None = None
    network_utility: float | None = None
    compiled_actions: tuple = ()


def _semantic(node, ctx):
    if isinstance(node, Static):
        p = node.profile
        return 0 <= p.quality <= 1 and p.deadline > 0 and p.rate > 0
    if isinstance(node, If):
        return node.condition in ctx.conditions and _semantic(node.then_clause, ctx) and _semantic(node.else_clause, ctx)
    if isinstance(node, Sequence):
        return 0 < node.duration < ctx.horizon and _semantic(node.first, ctx) and _semantic(node.second, ctx)
    if isinstance(node, Delay):
        return 0 < node.offset < ctx.horizon and _semantic(node.clause, ctx)
    if isinstance(node, ValidFor):
        start, end = node.interval
        return 0 <= start < end <= ctx.horizon and _semantic(node.clause, ctx)
    if isinstance(node, Offload):
        return node.level in ctx.offload_levels and _semantic(node.clause, ctx)
    return False


def _at(node, t, state, ctx, level='none'):
    if isinstance(node, Static):
        return node.profile, level
    if isinstance(node, If):
        return _at(node.then_clause if ctx.conditions[node.condition](state) else node.else_clause, t, state, ctx, level)
    if isinstance(node, Sequence):
        return _at(node.first, t, state, ctx, level) if t < node.duration else _at(node.second, t - node.duration, state, ctx, level)
    if isinstance(node, Delay):
        return None if t < node.offset else _at(node.clause, t - node.offset, state, ctx, level)
    if isinstance(node, ValidFor):
        start, end = node.interval
        return _at(node.clause, t - start, state, ctx, level) if start <= t < end else None
    if isinstance(node, Offload):
        return _at(node.clause, t, state, ctx, node.level)
    raise TypeError('unknown AST node')


def verify(node, ctx: PublicContext, private: PrivateAcceptance, max_depth: int):
    """Return first failing layer; compiled actions enumerate time/state cases.

    The demand and utility functions are explicit experimental model inputs;
    the engine is not a real-network control or resource reservation system.
    """
    if not _typed(node) or ast_depth(node) > max_depth:
        return Result(False, 'V1', 'invalid AST type or depth')
    required = required_capabilities(node)
    if not required <= ctx.capabilities:
        return Result(False, 'V2', 'missing capabilities: ' + ', '.join(sorted(required - ctx.capabilities)))
    registry = default_registry() if ctx.registry is None else ctx.registry
    reference = default_registry()
    required_scopes = _required_scopes(node)
    for cap in sorted(required):
        if cap not in registry or cap not in reference:
            return Result(False, 'V2', 'missing capability registry entry: ' + cap)
        item, expected = registry[cap], reference[cap]
        if (item.id != cap or item.input_types != expected.input_types or
                item.output_types != expected.output_types or
                not required_scopes[cap] <= set(item.supported_scope)):
            return Result(False, 'V2', 'capability type or scope mismatch: ' + cap)
        if not set(expected.preconditions) <= set(item.preconditions):
            return Result(False, 'V2', 'missing declared precondition: ' + cap)
        for predicate in item.preconditions:
            if predicate not in ctx.preconditions or not ctx.preconditions[predicate](node):
                return Result(False, 'V2', 'capability precondition missing or false: ' + predicate)
    if ctx.horizon <= 0 or not ctx.states or not _semantic(node, ctx):
        return Result(False, 'V3', 'semantic constraint failed')
    actions = []
    compiled = []
    for t, state in product(range(ctx.horizon), ctx.states):
        resolved = _at(node, t, state, ctx)
        if resolved is None:
            continue
        profile, level = resolved
        action = (t, state, profile, level)
        demand = ctx.demand(profile, level, t, state)
        capacity = ctx.capacity.get((t, state), {})
        if any(k not in capacity or k not in demand or not isfinite(demand[k]) or
               demand[k] < 0 or not isfinite(capacity[k]) or capacity[k] < 0 or
               demand[k] > capacity[k] for k in ('RAN', 'FH', 'EDGE')):
            return Result(False, 'V4', 'capacity exceeded or incomplete resource data')
        if level == 'none' and demand['EDGE'] != 0:
            return Result(False, 'V4', 'EDGE demand requires an offload reservation')
        actions.append(action)
        # Abstract adapter instructions: guards bind each instruction to a
        # time/state cell. Adapters and atomic reservation are not implemented.
        guard = {'time': t, 'state': state}
        for resource in ('RAN', 'FH'):
            compiled.append({'guard': guard, 'op': 'reserve_' + resource.lower(), 'amount': demand[resource]})
        if level != 'none':
            compiled.append({'guard': guard, 'op': 'reserve_edge', 'amount': demand['EDGE']})
            compiled.append({'guard': guard, 'op': 'enable_edge_offload', 'level': level})
        compiled.extend(({'guard': guard, 'op': 'set_quality', 'value': profile.quality},
                         {'guard': guard, 'op': 'select_latency_profile', 'value': profile.deadline},
                         {'guard': guard, 'op': 'set_rate', 'value': profile.rate}))
    actions = tuple(actions)
    if not ctx.hard_constraints(actions):
        return Result(False, 'V4', 'hard constraint failed')
    a, n = private.application_utility(actions), private.network_utility(actions)
    if not all(isfinite(x) and 0 <= x <= 1 for x in (a, n, private.application_reservation, private.network_reservation)):
        return Result(False, 'V5', 'utility or reservation outside [0,1]')
    if a < private.application_reservation or n < private.network_reservation:
        return Result(False, 'V5', 'private acceptance failed', actions, a, n)
    return Result(True, None, 'verified in abstract model', actions, a, n, tuple(compiled))

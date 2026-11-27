"""Finite benchmark state machine; never calls external networks or services.

Each (time, exogenous-state) guard denotes an alternative world, not concurrent
traffic. Resources are reset to that world's capacity each slot, then reserved
atomically by the schedule. Results are benchmark-only verification.
"""
from dataclasses import dataclass
from itertools import product
from math import isfinite
from .engine import (Result, _typed, ast_depth, required_capabilities,
                     _required_scopes, _semantic, _at, PublicContext, BASE, STRUCTURAL)
from .registry import default_registry


@dataclass(frozen=True)
class Transition:
    time: int
    state: str
    operation: str
    arguments: tuple
    before: tuple
    after: tuple


def _signature(cap):
    """Provider/ID are identities, not semantics. Everything else matters."""
    return (cap.input_types, cap.output_types, tuple(sorted(cap.preconditions)),
            tuple(sorted(cap.effects)), tuple(sorted(cap.resource_cost.items())),
            cap.execution_cost, tuple(sorted(cap.supported_scope)))


def bind_capabilities(required, available, registry):
    """Resolve semantic equivalents deterministically; never inspect preferences."""
    reference = registry
    available = sorted(available)
    found = {}
    for name in sorted(required):
        if name not in reference:
            return None
        wanted = _signature(reference[name])
        choices = [cid for cid in available if cid in registry and _signature(registry[cid]) == wanted]
        if not choices:
            return None
        found[name] = choices[0]
    return found


def _nodes(node):
    from .models import Static, If, Sequence
    yield node
    if isinstance(node, Static):
        return
    if isinstance(node, If):
        children = (node.then_clause, node.else_clause)
    elif isinstance(node, Sequence):
        children = (node.first, node.second)
    else:
        children = (node.clause,)
    for child in children:
        yield from _nodes(child)


def normalize(node, public=None):
    """Normalize conditionals with equal branch semantics using public inputs.

    Children are normalized before comparison; all recursion descends to a
    smaller tree. Without public, only identical normalized ASTs are merged.
    """
    from .models import Static, If, Sequence, Delay, ValidFor, Offload
    if isinstance(node, Static): return node
    if isinstance(node, If):
        left, right = normalize(node.then_clause, public), normalize(node.else_clause, public)
        equal = left == right
        if not equal and public is not None and node.condition == 'moving':
            equal = semantic_key(left, public) == semantic_key(right, public)
        if node.condition == 'moving' and equal:
            from .enumeration import syntax_key
            return min((left,right), key=syntax_key)
        return If(node.condition, left, right)
    if isinstance(node, Sequence): return Sequence(node.duration, normalize(node.first, public), normalize(node.second, public))
    if isinstance(node, Delay): return Delay(node.offset, normalize(node.clause, public))
    if isinstance(node, ValidFor): return ValidFor(node.interval, normalize(node.clause, public))
    if isinstance(node, Offload): return Offload(node.level, normalize(node.clause, public))
    raise TypeError('unknown AST')


def _active_roles(node, t, state):
    """Return (profile, level, runtime role set); idle returns None.

    Wrappers cost only on active descendant paths. Sets make repeated use of a
    role in one cell a single invocation by definition of this benchmark.
    """
    from .models import Static, If, Sequence, Delay, ValidFor, Offload
    if isinstance(node, Static): return node.profile, 'none', set(BASE)
    if isinstance(node, If):
        child = node.then_clause if state == 'moving' else node.else_clause
        v = _active_roles(child, t, state)
    elif isinstance(node, Sequence):
        v = _active_roles(node.first, t, state) if t < node.duration else _active_roles(node.second, t - node.duration, state)
    elif isinstance(node, Delay):
        v = None if t < node.offset else _active_roles(node.clause, t - node.offset, state)
    elif isinstance(node, ValidFor):
        start, end = node.interval
        v = _active_roles(node.clause, t - start, state) if start <= t < end else None
    elif isinstance(node, Offload):
        v = _active_roles(node.clause, t, state)
    else: raise TypeError('unknown AST')
    if v is None: return None
    profile, level, roles = v
    if isinstance(node, Offload): level = node.level
    return profile, level, roles | set(STRUCTURAL[type(node)])


def _role_costs(roles, registry):
    return (tuple(sum(registry[r].resource_cost.get(k, 0.0) for r in sorted(roles))
                  for k in ('RAN', 'FH', 'EDGE')),
            sum(registry[r].execution_cost for r in sorted(roles)))


def _predicate(name, node, public):
    """Closed predicate vocabulary; unknown predicate always fails closed."""
    from .models import Static, If, Sequence, Delay, ValidFor, Offload
    nodes = tuple(_nodes(node))
    constraints = public.public_constraints
    profiles = {p for p in public.b2_profiles}
    checks = {
        'motion_observable': lambda: set(public.states) >= {'still', 'moving'},
        'quality_supported': lambda: all(n.profile in profiles for n in nodes if isinstance(n, Static)),
        'deadline_supported': lambda: all(n.profile in profiles for n in nodes if isinstance(n, Static)),
        'rate_supported': lambda: all(n.profile in profiles for n in nodes if isinstance(n, Static)),
        'scheduling_supported': lambda: all(0 < n.offset < public.horizon for n in nodes if isinstance(n, Delay)),
        'validity_supported': lambda: all(0 <= n.interval[0] < n.interval[1] <= public.horizon for n in nodes if isinstance(n, ValidFor)),
        'conditional_supported': lambda: all(n.condition == 'moving' for n in nodes if isinstance(n, If)),
        'phasing_supported': lambda: all(0 < n.duration < public.horizon for n in nodes if isinstance(n, Sequence)),
        'offload_supported': lambda: all(n.level == 'edge' for n in nodes if isinstance(n, Offload)),
        'ran_reservation_supported': lambda: bool(constraints.get('reservation_supported', False)),
        'fh_reservation_supported': lambda: bool(constraints.get('reservation_supported', False)),
        'edge_reservation_supported': lambda: bool(constraints.get('reservation_supported', False)),
    }
    return name in checks and checks[name]()


def verify_instance(node, instance, max_depth, registry=None):
    """Validate and execute a single AST against a serialized benchmark instance.

    The state machine's compiled trace is finite and executable in this model;
    its verification is not a proof of real-network machine execution.
    """
    from .instances import demand, utilities, hard_check, registry_from_public
    public, private = instance.public, instance.private
    if not _typed(node) or ast_depth(node) > max_depth:
        return Result(False, 'V1', 'invalid AST type or depth')
    node = normalize(node, public)
    reg = registry_from_public(public)
    if registry is not None and registry != reg:
        raise ValueError('registry does not match serialized public instance')
    req = required_capabilities(node)
    # The interpreter implements this versioned closed role vocabulary. Reject
    # changed declarations rather than silently executing a different effect.
    implemented = default_registry()
    if any(role not in reg or _signature(reg[role]) != _signature(implemented[role]) for role in req):
        return Result(False, 'V2', 'serialized role declaration incompatible with interpreter')
    bindings = bind_capabilities(req, public.capabilities, reg)
    if bindings is None:
        return Result(False, 'V2', 'no available equivalent capability')
    scopes = _required_scopes(node)
    for expected, actual in bindings.items():
        cap = reg[actual]
        if not scopes[expected] <= set(cap.supported_scope):
            return Result(False, 'V2', 'unsupported scope')
        if any(not _predicate(p, node, public) for p in cap.preconditions):
            return Result(False, 'V2', 'false or unknown capability precondition')
    capacities = {(t, s): {'RAN': ran, 'FH': fh, 'EDGE': edge}
                  for t, s, ran, fh, edge in public.capacity}
    ctx = PublicContext(public.horizon, public.states, {'moving': lambda s: s == 'moving'},
                        ('edge',), frozenset(public.capabilities), {}, capacities,
                        lambda p, l, t, s: demand(public, p, l, t, s), lambda _: True)
    if not public.states or public.horizon <= 0 or not _semantic(node, ctx):
        return Result(False, 'V3', 'semantic constraint failed')
    actions, trace = [], []
    cell_surcharges, cell_execution_costs = {}, {}
    for t, state in product(range(public.horizon), public.states):
        resolved = _active_roles(node, t, state)
        capacity = capacities.get((t, state))
        if capacity is None or any(not isfinite(capacity[x]) or capacity[x] < 0 for x in ('RAN', 'FH', 'EDGE')):
            return Result(False, 'V4', 'missing or invalid public capacity')
        if resolved is None:
            # The idle transition is explicit and leaves capacity unchanged.
            before = tuple(capacity[x] for x in ('RAN', 'FH', 'EDGE'))
            trace.append(Transition(t, state, 'idle', (), before, before))
            continue
        profile, level, runtime_roles = resolved
        surcharge, execution = _role_costs(runtime_roles, reg)
        resource_surcharge = dict(zip(('RAN', 'FH', 'EDGE'), surcharge))
        cell_surcharges[(t, state)] = resource_surcharge
        cell_execution_costs[(t, state)] = execution
        base_loads = demand(public, profile, level, t, state)
        loads = {k: base_loads[k] + resource_surcharge[k] for k in ('RAN', 'FH', 'EDGE')}
        if any(k not in loads or not isfinite(loads[k]) or loads[k] < 0 or loads[k] > capacity[k]
               for k in ('RAN', 'FH', 'EDGE')):
            return Result(False, 'V4', 'capacity exceeded or invalid demand')
        if 'reserve_edge_compute' not in runtime_roles and loads['EDGE'] != 0:
            return Result(False, 'V4', 'EDGE use without offload')
        actions.append((t, state, profile, level))
        remaining = [capacity[x] for x in ('RAN', 'FH', 'EDGE')]
        for i, k in enumerate(('RAN', 'FH', 'EDGE')):
            if k == 'EDGE' and 'reserve_edge_compute' not in runtime_roles:
                continue
            before = tuple(remaining)
            remaining[i] -= loads[k]
            trace.append(Transition(t, state, 'reserve_' + k.lower(), (loads[k],), before, tuple(remaining)))
        before = tuple(remaining)
        # Set operations and guard selection affect service state, not resources.
        operations = [('set_quality', (profile.quality,)), ('select_latency_profile', (profile.deadline,)),
                      ('set_rate', (profile.rate,))]
        if level != 'none':
            operations.append(('enable_edge_offload', (level,)))
        for op, args in operations:
            trace.append(Transition(t, state, op, args, before, before))
    actions = tuple(actions)
    if not hard_check(public, actions):
        return Result(False, 'V4', 'public hard constraint failed')
    a, n = utilities(public, private, actions, cell_surcharges=cell_surcharges, cell_execution_costs=cell_execution_costs)
    ar, nr = private.application['reservation'], private.network['reservation']
    if not all(isfinite(x) and 0 <= x <= 1 for x in (a, n, ar, nr)):
        return Result(False, 'V5', 'invalid utility or reservation')
    if a < ar or n < nr:
        return Result(False, 'V5', 'private acceptance failed', actions, a, n, tuple(trace))
    return Result(True, None, 'benchmark_verified', actions, a, n, tuple(trace))


def semantic_key(node, public):
    """Public-only ContractSemanticSignature for a V1-legal AST.

    Its scope is one fixed public instance and the finite benchmark interpreter;
    equality alone does not assert equivalence across different instances.
    """
    from .instances import registry_from_public
    if not _typed(node): raise ValueError('invalid AST')
    node = normalize(node, public)
    registry = registry_from_public(public)
    roles = required_capabilities(node)
    scopes = _required_scopes(node)
    footprint = []
    for role in sorted(roles):
        if role not in registry:
            footprint.append((role, None, tuple(sorted(scopes[role])), None))
            continue
        cap = registry[role]
        footprint.append((role, _signature(cap), tuple(sorted(scopes[role])),
                          tuple((p, _predicate(p, node, public)) for p in sorted(cap.preconditions))))
    ctx = PublicContext(public.horizon, public.states, {'moving': lambda s: s == 'moving'},
                        ('edge',), frozenset(public.capabilities), {}, {}, None, None)
    valid = bool(public.states and public.horizon > 0 and _semantic(node, ctx))
    if not valid:
        return (tuple(footprint), False, ())
    cells = []
    for t, state in product(range(public.horizon), public.states):
        resolved = _active_roles(node, t, state)
        if resolved is None:
            cells.append((t, state, None))
        else:
            p, level, active = resolved
            if not active <= registry.keys():
                # Missing role descriptor is already in footprint. No execution
                # is possible, but an explicit sentinel keeps key deterministic.
                costs = None
            else:
                costs = _role_costs(active, registry)
            cells.append((t, state, (p.quality, p.deadline, p.rate, level, tuple(sorted(active)), costs)))
    return (tuple(footprint), True, tuple(cells))


def safe_public_dedup_key(node, public):
    """Refine schedule by public capability and scope requirements.

    This is a conservative key, not a complete semantic quotient. Include
    structural reporting features so their statistics do not change when
    selecting a representative. Private acceptance is never inspected.
    """
    from .models import If, Sequence, Delay, Offload
    node = normalize(node, public)
    req = tuple(sorted(required_capabilities(node)))
    scopes = tuple((k, tuple(sorted(v))) for k, v in sorted(_required_scopes(node).items()))
    structural = any(isinstance(n, (If, Sequence, Delay, Offload)) for n in _nodes(node))
    return semantic_key(node, public), req, scopes, ast_depth(node), structural



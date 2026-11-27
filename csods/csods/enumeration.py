"""Public-only finite contract spaces and independently structured reference.

Canonical keys here deliberately retain all syntax. They are safe for removing
identical ASTs, but do not claim equivalence of different ASTs. Cost and action
semantics must be proven congruent before more aggressive deduplication.
"""
from itertools import product
import json
from .models import Static, If, Sequence, Delay, ValidFor, Offload
from .engine import Domain, STRUCTURAL, enumerate_compositions

METHODS = ('B0', 'B1', 'B2', 'O1')


def public_domain(public):
    return Domain(tuple(public.b2_profiles), tuple(public.conditions),
                  tuple(public.durations), tuple(public.offsets),
                  tuple(public.intervals), tuple(public.offload_levels))


def candidates(method, public, max_depth, registry=None):
    """Generate candidates using public data only; no acceptance or utility."""
    if method not in METHODS:
        raise ValueError('unknown method')
    if method != 'O1':
        profiles = {'B0': public.m0_profiles, 'B1': public.mr_profiles,
                    'B2': public.b2_profiles}[method]
        yield from (Static(p) for p in profiles)
    else:
        from .registry import default_registry
        from .state_machine import bind_capabilities
        from .instances import registry_from_public
        reg = registry_from_public(public)
        if registry is not None and registry != reg:
            raise ValueError('registry override differs from hashed public registry')
        roles = {role for role in default_registry()
                 if bind_capabilities({role}, public.capabilities, reg) is not None}
        yield from enumerate_compositions(public_domain(public), max_depth, roles)


def syntax_key(node):
    """Lossless canonical AST key; no cross-AST semantic equivalence claimed."""
    def encode(x):
        if isinstance(x, Static):
            p = x.profile
            return ['Static', p.quality, p.deadline, p.rate]
        if isinstance(x, If): return ['If', x.condition, encode(x.then_clause), encode(x.else_clause)]
        if isinstance(x, Sequence): return ['Sequence', x.duration, encode(x.first), encode(x.second)]
        if isinstance(x, Delay): return ['Delay', x.offset, encode(x.clause)]
        if isinstance(x, ValidFor): return ['ValidFor', list(x.interval), encode(x.clause)]
        if isinstance(x, Offload): return ['Offload', x.level, encode(x.clause)]
        raise TypeError('unknown contract node')
    return json.dumps(encode(node), separators=(',', ':'), allow_nan=False)


def independent_reference(domain, depth, capabilities):
    """Bottom-up independent reference for small depths; materializes all ASTs."""
    if not 0 <= depth <= 2:
        raise ValueError('reference enumeration limited to depth 2')
    caps = set(capabilities)
    base = {Static(p) for p in domain.profiles}
    previous = base
    for _ in range(depth):
        current = set(base)
        if STRUCTURAL[If] <= caps:
            current.update(If(c, a, b) for c, a, b in product(domain.conditions, previous, previous))
        if STRUCTURAL[Sequence] <= caps:
            current.update(Sequence(d, a, b) for d, a, b in product(domain.durations, previous, previous))
        for cls, params in ((Delay, domain.offsets), (ValidFor, domain.intervals), (Offload, domain.offload_levels)):
            if STRUCTURAL[cls] <= caps:
                current.update(cls(v, c) for v, c in product(params, previous))
        previous = current
    return previous


def exact_syntax_count(domain, depth, capabilities):
    """Count unique syntactic ASTs by recurrence, requiring unique domain values."""
    fields = (domain.profiles, domain.conditions, domain.durations,
              domain.offsets, domain.intervals, domain.offload_levels)
    if any(len(x) != len(set(x)) for x in fields):
        raise ValueError('domain values must be unique')
    if type(depth) is not int or depth < 0: raise ValueError('invalid depth')
    caps = set(capabilities)
    n0 = len(domain.profiles)
    binary = (len(domain.conditions) if STRUCTURAL[If] <= caps else 0) + (len(domain.durations) if STRUCTURAL[Sequence] <= caps else 0)
    unary = sum(len(values) for cls, values in ((Delay, domain.offsets), (ValidFor, domain.intervals), (Offload, domain.offload_levels)) if STRUCTURAL[cls] <= caps)
    n = n0
    for _ in range(depth): n = n0 + unary*n + binary*n*n
    return n

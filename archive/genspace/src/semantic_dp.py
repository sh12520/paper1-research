"""Experimental public-only bottom-up semantic enumerator.

This is not yet the authorized exact O1: contextual congruence and global
lexical minimality must be independently established. It never reads utility.
"""
from dataclasses import dataclass
from itertools import product
from .engine import STRUCTURAL, ast_depth
from .enumeration import syntax_key
from .models import Static, If, Sequence, Delay, ValidFor, Offload
from .state_machine import normalize, semantic_key

@dataclass
class Entry:
    witness: object
    compose_witness: object


def library(public, depth, capabilities=None):
    """Return key -> Entry. No private inputs. Static has depth 0.

    Keeps a shallow normalized witness for composition and a lexical witness
    for reporting. Until contextual completeness is proven this is experimental.
    """
    if depth not in (0, 1, 2):
        raise ValueError('only depth 0, 1, 2 in this draft')
    from .instances import registry_from_public
    from .registry import default_registry
    from .state_machine import bind_capabilities
    registry = registry_from_public(public)
    available = public.capabilities if capabilities is None else capabilities
    caps = {role for role in default_registry() if bind_capabilities({role}, available, registry) is not None}
    previous = {}
    def insert(table, node):
        key = semantic_key(node, public)
        normalized = normalize(node, public)
        current = table.get(key)
        if current is None:
            table[key] = Entry(node, normalized)
        else:
            if syntax_key(node) < syntax_key(current.witness): current.witness = node
            if (ast_depth(normalized), syntax_key(normalized)) < (ast_depth(current.compose_witness), syntax_key(current.compose_witness)):
                current.compose_witness = normalized
    for p in public.b2_profiles:
        insert(previous, Static(p))
    for _ in range(depth):
        current = dict((k, Entry(v.witness, v.compose_witness)) for k, v in previous.items())
        # Keep both lexical-best and minimum-depth witnesses: lexical winners
        # can be deeper due to normalizable redundant wrappers.
        children = tuple(dict.fromkeys(x for v in previous.values() for x in (v.compose_witness, v.witness)))
        if STRUCTURAL[If] <= caps:
            for c, a, b in product(public.conditions, children, children): insert(current, If(c,a,b))
        if STRUCTURAL[Sequence] <= caps:
            for d, a, b in product(public.durations, children, children): insert(current, Sequence(d,a,b))
        for cls, vals in ((Delay, public.offsets), (ValidFor, public.intervals), (Offload, public.offload_levels)):
            if STRUCTURAL[cls] <= caps:
                for v, child in product(vals, children): insert(current, cls(v,child))
        previous = current
    return previous


def streaming_reference(public, depth):
    """Exact syntax-stream reference: holds semantic keys only, never ASTs.

    This independent generator is exponential; caller is responsible for a
    feasibility audit. No truncation or private utility filtering occurs.
    """
    from .engine import Domain, enumerate_compositions
    domain = Domain(tuple(public.b2_profiles), tuple(public.conditions),
        tuple(public.durations), tuple(public.offsets), tuple(public.intervals),
        tuple(public.offload_levels))
    return {semantic_key(node, public) for node in
            enumerate_compositions(domain, depth, public.capabilities)}

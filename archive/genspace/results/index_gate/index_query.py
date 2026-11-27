"""Exact lazy retrieval of the frozen FLAT public score order."""
from __future__ import annotations

import heapq
import operator
from time import perf_counter
from types import SimpleNamespace

import numpy as np

from public_search import (
    COST_WEIGHT,
    GROUP_COMPLEXITY_WEIGHT,
    MARGIN_WEIGHT,
    QUALITY_WEIGHT,
    PublicView,
    _capacities,
    _proxy,
)
from src.availability_index import AvailabilityBundle
from src.engine import BASE
from src.registry import default_registry


_ROLE_NAMES = tuple(sorted(default_registry()))


def _availability_pattern(view):
    present = frozenset(view.capabilities)
    if not BASE <= present or not present <= set(_ROLE_NAMES):
        raise ValueError('query capabilities differ from the supported canonical role domain')
    # The frozen basis admits canonical registry roles only. Reuse the same
    # public projection as FastLibrary for the conditioned derivability masks.
    reference = SimpleNamespace(roles=_ROLE_NAMES, available=tuple(role in present for role in _ROLE_NAMES))
    return AvailabilityBundle.pattern(SimpleNamespace(reference=reference))


def _combine(violation, margin, quality, cost, group_count):
    """Use the frozen scorer's binary64 sequence, including its last +=."""
    score = (violation - MARGIN_WEIGHT * margin + COST_WEIGHT * cost
             + QUALITY_WEIGHT * (1. - quality))
    score += GROUP_COMPLEXITY_WEIGHT * group_count
    return score


def flat_scores(view, library, ids, group_bits):
    """Original _proxy in the FLAT reference lane, independent of index data."""
    counts = np.array([i.bit_count() for i in range(16)], dtype=np.uint8)
    return _combine(*_proxy(view, library, ids), counts[group_bits[ids]])


def _demand_terms(demand, capacity, denominator):
    # All rows use the native order (cell0 RAN/FH/EDGE, ..., cell5 EDGE).
    # np.add.accumulate stores each sequential binary64 addition before the
    # next. In contrast, np.sum is permitted to use pairwise accumulation.
    normalized = ((demand - capacity) / denominator).reshape(len(demand), 18)
    violation = np.maximum(normalized, 0.)
    margin = np.clip(-normalized, -1., 1.)
    margin[:, 0] += 0.
    np.add.accumulate(violation, axis=1, out=violation)
    np.add.accumulate(margin, axis=1, out=margin)
    return violation[:, -1] / 18., margin[:, -1] / 18.


def scores_from_demand(demand, quality, cost, groups, capacity, denominator):
    violation, margin = _demand_terms(demand, capacity, denominator)
    return _combine(violation, margin, quality, cost, groups)


class QueryCursor:
    """A resumable public search. No full-scan fallback or acceptance access."""

    def __init__(self, index, tree_name, view, library, availability_variant):
        start = perf_counter()
        if not isinstance(view, PublicView) or view.depth not in (1, 2):
            raise TypeError('indexed query requires frozen sanitized PublicView')
        index.validate_view(view)
        self.index = index
        self.tree = index.trees[tree_name]
        self.depth = view.depth
        self.pattern = availability_variant.header['pattern']
        if (self.pattern != _availability_pattern(view)
                or library.availability.entries[self.pattern] is not availability_variant):
            raise ValueError('availability variant does not match the public capabilities and frozen graph')
        if getattr(library, 'role_costs', None) is None or getattr(library, 'execution_costs', None) is None:
            raise ValueError('FLAT scoring requires a bound public graph basis')
        self.pattern_bit = np.uint32(1 << self.pattern)
        self.rich_bit = np.uint32(1 << 31)
        self.capacity = _capacities(view)
        if self.capacity.shape != (6, 3) or not np.isfinite(self.capacity).all():
            raise ValueError('query requires finite six-cell public capacities')
        self.denominator = np.maximum(self.capacity, 1e-9)
        self.eligible = index.available1 if self.depth == 1 else index.available2
        self.node_any = self.tree.any1 if self.depth == 1 else self.tree.any2
        self.full_conditioned_count = int(index.conditioned_count(self.pattern, self.depth))
        self.frontier = []
        self.emitted_ids = []
        self.emitted_scores = []
        self.started = False
        self.internal_nodes_visited = 0
        self.leaves_visited = 0
        self.all_internal_nodes = (len(self.tree.left) - len(self.tree.roots)) // 2
        self.leaf_ids_inspected = 0
        self.complete_candidates_touched = 0
        self.exact_public_scores = 0
        self.capability_rejects = 0
        self.depth_rejects = 0
        self.node_bound_evaluations = 0
        self.node_bound_s = 0.
        self.traversal_s = 0.
        self.candidate_scoring_s = 0.
        self.query_setup_s = perf_counter() - start

    def _push_nodes(self, nodes):
        nodes = np.asarray(nodes, dtype=np.intp)
        included = (self.node_any[nodes] & self.pattern_bit) != 0
        excluded_nodes = nodes[~included]
        if len(excluded_nodes):
            sizes = self.tree.stop[excluded_nodes] - self.tree.start[excluded_nodes]
            if self.depth == 1:
                in_depth = self.tree.depth1_counts[excluded_nodes]
                self.depth_rejects += int(np.sum(sizes - in_depth, dtype=np.int64))
                self.capability_rejects += int(np.sum(in_depth, dtype=np.int64))
            else:
                self.capability_rejects += int(np.sum(sizes, dtype=np.int64))
        nodes = nodes[included]
        if not len(nodes):
            return
        start = perf_counter()
        bounds = scores_from_demand(
            self.tree.lo[nodes], self.tree.max_quality[nodes], self.tree.min_cost[nodes],
            self.tree.min_groups[nodes], self.capacity, self.denominator,
        )
        if not np.isfinite(bounds).all():
            raise ValueError('nonfinite public score lower bound')
        self.node_bound_s += perf_counter() - start
        self.node_bound_evaluations += len(nodes)
        for bound, min_id, node in zip(bounds, self.tree.min_id[nodes], nodes):
            heapq.heappush(self.frontier, (float(bound), int(min_id), 0, int(node)))

    def _push_leaf(self, node):
        members = self.tree.order[self.tree.start[node]:self.tree.stop[node]]
        self.leaf_ids_inspected += len(members)
        allowed = (self.eligible[members] & self.pattern_bit) != 0
        rejected = int(np.count_nonzero(~allowed))
        if rejected:
            if self.depth == 1:
                in_depth = (self.index.available1[members] & self.rich_bit) != 0
                depth_rejects = int(np.count_nonzero(~in_depth))
                self.depth_rejects += depth_rejects
                self.capability_rejects += rejected - depth_rejects
            else:
                self.capability_rejects += rejected
        ids = members[allowed]
        if not len(ids):
            return
        self.complete_candidates_touched += len(ids)
        start = perf_counter()
        idx = self.index
        demand = idx.demand_basis[idx.cell_code[ids]]
        scores = scores_from_demand(demand, idx.quality[ids], idx.cost[ids],
                                    idx.group_count[ids], self.capacity, self.denominator)
        if not np.isfinite(scores).all():
            raise ValueError('nonfinite exact public score')
        self.candidate_scoring_s += perf_counter() - start
        self.exact_public_scores += len(ids)
        order = np.lexsort((ids, scores))
        ids, scores = ids[order], scores[order]
        heapq.heappush(self.frontier, (float(scores[0]), int(ids[0]), 1, (ids, scores, 0)))

    def _extend(self, count):
        if len(self.emitted_ids) >= count:
            return
        start = perf_counter()
        excluded = self.node_bound_s + self.candidate_scoring_s
        if not self.started:
            self._push_nodes(self.tree.roots)
            self.started = True
        while len(self.emitted_ids) < count:
            if not self.frontier:
                raise RuntimeError('indexed frontier exhausted before the exact conditioned count')
            score, cid, kind, payload = heapq.heappop(self.frontier)
            if kind == 0:
                left = self.tree.left[payload]
                if left < 0:
                    self.leaves_visited += 1
                    self._push_leaf(payload)
                else:
                    self.internal_nodes_visited += 1
                    self._push_nodes((left, self.tree.right[payload]))
            else:
                self.emitted_ids.append(cid)
                self.emitted_scores.append(score)
                ids, scores, pos = payload
                pos += 1
                if pos < len(ids):
                    heapq.heappush(self.frontier, (float(scores[pos]), int(ids[pos]), 1,
                                                   (ids, scores, pos)))
        charged = self.node_bound_s + self.candidate_scoring_s - excluded
        self.traversal_s += perf_counter() - start - charged

    def retrieve_top_k(self, k):
        """Return cumulative prefix (IDs and binary64 scores), extending lazily."""
        upper = operator.index(k)
        if upper < 0:
            raise ValueError('negative retrieval size')
        upper = min(upper, self.full_conditioned_count)
        self._extend(upper)
        return (np.asarray(self.emitted_ids[:upper], dtype=np.int64),
                np.asarray(self.emitted_scores[:upper], dtype=np.float64))

    def take(self, n):
        """Return the next slice after the already retrieved prefix."""
        n = operator.index(n)
        if n < 0:
            raise ValueError('negative retrieval size')
        start = len(self.emitted_ids)
        stop = min(start + n, self.full_conditioned_count)
        self._extend(stop)
        return (np.asarray(self.emitted_ids[start:stop], dtype=np.int64),
                np.asarray(self.emitted_scores[start:stop], dtype=np.float64))

    def metrics(self):
        """Work performed by this cursor so far. Node visits are separate."""
        return {
            'full_conditioned_count': self.full_conditioned_count,
            'internal_nodes_visited': self.internal_nodes_visited,
            'all_internal_nodes': self.all_internal_nodes,
            'leaves_visited': self.leaves_visited,
            'leaf_ids_inspected': self.leaf_ids_inspected,
            'node_bound_evaluations': self.node_bound_evaluations,
            'complete_candidates_touched': self.complete_candidates_touched,
            'exact_public_scores': self.exact_public_scores,
            'capability_rejects': self.capability_rejects,
            'depth_rejects': self.depth_rejects,
            'bound_pruned_candidates': (self.full_conditioned_count - self.exact_public_scores
                                        if self.emitted_ids else 0),
            'node_visit_ratio': (self.internal_nodes_visited / self.all_internal_nodes
                                 if self.all_internal_nodes else 0.0),
            'touch_ratio': (self.complete_candidates_touched / self.full_conditioned_count
                            if self.full_conditioned_count else 0.0),
            'returned_k': len(self.emitted_ids),
            'query_setup_s': self.query_setup_s,
            'node_bound_s': self.node_bound_s,
            'traversal_s': self.traversal_s,
            'candidate_scoring_s': self.candidate_scoring_s,
        }

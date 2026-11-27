"""Archived graph-based competitors for the fixed depth-one/two dev panel."""

from pathlib import Path
import sys
from time import perf_counter
from types import FunctionType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "results" / "index_gate"),
                str(ROOT / "results" / "grammar_gate"),
                str(ROOT / "results" / "method_dev_v1")]

import numpy as np

from grammar_search import Entry, SearchLimit, decode_witness
from index_query import QueryCursor
from index_tree import Index
import public_search
from runtime import choose_variant, verification_public
from src.enumeration import syntax_key
from src.fast_exact import FastLibrary
from src.state_machine import normalize


GRAPH_METHODS = ("FULL_FLAT", "GENERIC_INDEX", "CONTRACT_AWARE_INDEX")
TREE_BY_METHOD = {"GENERIC_INDEX": "generic", "CONTRACT_AWARE_INDEX": "contract"}


class _RankObservation:
    """Record the exact score vector already evaluated by archived make_plan."""

    def __init__(self):
        self.scores = None

    def __getattr__(self, name):
        return getattr(np, name)

    def lexsort(self, keys):
        if self.scores is not None or len(keys) != 2:
            raise AssertionError("unexpected FLAT sorter invocation")
        order = np.lexsort(keys)
        self.scores = keys[1][order]
        return order


class _ObservedIndexCursor(QueryCursor):
    def __init__(self, *args, guard):
        self.guard = guard
        super().__init__(*args)

    def _push_nodes(self, nodes):
        self.guard()
        super()._push_nodes(nodes)
        self.guard()

    def _push_leaf(self, node):
        self.guard()
        super()._push_leaf(node)
        self.guard()


class _GraphCursor:
    def __init__(self, controls, method, public, depth, limits, sample, deadline):
        self.started = perf_counter()
        self.deadline = self.started + limits.wall_seconds if deadline is None else deadline
        self.limits = limits
        self.sample = sample
        self.peak = 0
        self.frontier_peak = 0
        self.next_sample_at = 0
        self.library = controls.library
        self.public, view, self.variant = controls.project(public, depth)
        self.depth = depth
        self.count = int(controls.index.conditioned_count(self.variant.header["pattern"], depth))
        self.emitted = 0
        self.last_emitted_score = None
        self.exhausted = False
        self._query = None
        self._ranks = None
        self._scores = None
        self._flat_examined = 0
        self.check_limits(force=True)

        if method == "FULL_FLAT":
            observer = _RankObservation()
            make_plan = FunctionType(public_search.make_plan.__code__,
                                     dict(vars(public_search), np=observer),
                                     public_search.make_plan.__name__,
                                     public_search.make_plan.__defaults__)
            plan = make_plan(view, self.library, self.variant, 0, "FLAT-FEASIBILITY",
                             budget=5000)
            if (plan.public_ranked_count != self.count or observer.scores is None
                    or len(plan.order) != len(observer.scores)):
                raise AssertionError("FLAT scoring disagrees with the frozen conditioned domain")
            self._flat_examined = self.count
            self._ranks, self._scores = plan.order, observer.scores
        else:
            self._query = _ObservedIndexCursor(
                controls.index, TREE_BY_METHOD[method], view, self.library, self.variant,
                guard=self.check_limits,
            )

    def check_limits(self, force=False):
        if perf_counter() >= self.deadline:
            raise SearchLimit("wall_time_limit")
        q = self._query
        if q is not None:
            self.frontier_peak = max(self.frontier_peak, len(q.frontier))
            if len(q.frontier) > self.limits.frontier:
                raise SearchLimit("frontier_limit")
            if q.internal_nodes_visited + q.leaves_visited >= self.limits.expanded:
                raise SearchLimit("expanded_limit")
        work = (q.internal_nodes_visited + q.leaves_visited + q.exact_public_scores
                if q is not None else self._flat_examined + self.emitted)
        if self.sample is not None and (force or work >= self.next_sample_at):
            self.peak = max(self.peak, self.sample())
            self.next_sample_at = work + 128

    def next_contract(self):
        self.check_limits()
        if self.emitted == self.count:
            self.exhausted = True
            return None
        if self._query is None:
            candidate_id, score = self._ranks[self.emitted], self._scores[self.emitted]
        else:
            self._query._extend(self.emitted + 1)
            if len(self._query.emitted_ids) != self.emitted + 1:
                raise AssertionError("index emitted a short uncertified prefix")
            candidate_id = self._query.emitted_ids[self.emitted]
            score = self._query.emitted_scores[self.emitted]
        raw = self.variant.witness(int(candidate_id), self.depth)
        witness = syntax_key(normalize(decode_witness(raw), self.public))
        self.check_limits()
        self.emitted += 1
        self.last_emitted_score = float(score)
        return Entry(self.library.keys[int(candidate_id)].tobytes(), float(score), raw, witness)

    def _key(self, item):
        return self.library.keys[item[1]].tobytes().hex() if item is not None else None

    def metrics(self):
        q = self._query
        if q is None:
            bounds = []
            head = ((float(self._scores[self.emitted]), int(self._ranks[self.emitted]))
                    if self._ranks is not None and self.emitted < self.count else None)
            buffered = self.count - self.emitted if self._ranks is not None else 0
            scores = self._flat_examined
            bound_checks = None
            nodes_visited = leaves_visited = None
            members_touched = scores
            leaf_ids_inspected = None
        else:
            bounds = [(lb, cid) for lb, cid, kind, _ in q.frontier if kind == 0]
            leaf_groups = [(score, cid, data) for score, cid, kind, data in q.frontier if kind == 1]
            head = min(((score, cid) for score, cid, _ in leaf_groups), default=None)
            buffered = sum(len(data[0]) - data[2] for _, _, data in leaf_groups)
            scores = q.exact_public_scores
            bound_checks = q.node_bound_evaluations
            nodes_visited, leaves_visited = q.internal_nodes_visited, q.leaves_visited
            members_touched, leaf_ids_inspected = q.complete_candidates_touched, q.leaf_ids_inspected
        best_bound = min(bounds, default=None)
        return {
            "wall_s": perf_counter() - self.started,
            "partial_generated": None, "partial_expanded": None,
            "unique_semantics": scores, "scores": scores,
            "witness_asts_materialized": self.emitted, "complete_syntax": self.emitted,
            "lower_bound_evaluations": bound_checks,
            "index_internal_nodes_visited": nodes_visited, "index_leaf_nodes_visited": leaves_visited,
            "complete_candidates_touched": members_touched, "index_leaf_ids_inspected": leaf_ids_inspected,
            "conditioned_candidate_count": self.count,
            "flat_metadata_records_touched": len(self.library.keys) if q is None else None,
            "frontier_peak": self.frontier_peak if q is not None else None,
            "frontier_remaining": len(bounds),
            "frontier_min_lb": best_bound[0] if best_bound is not None else None,
            "frontier_min_key": self._key(best_bound),
            "buffered_complete": buffered,
            "buffered_best_score": head[0] if head is not None else None,
            "buffered_best_key": self._key(head),
            "full_domain_exhausted": self.exhausted,
            "peak_working_set_bytes": self.peak or None,
            "last_emitted_score": self.last_emitted_score, "emitted": self.emitted,
        }


class IndexControls:
    """A persistent graph lane whose public assets never enter synthesis."""

    def __init__(self, base_public):
        started = perf_counter()
        self.library = FastLibrary.from_graph(scope="pilot-execution")
        bind_start = perf_counter()
        self.library.bind_public_basis(verification_public(base_public))
        bind_seconds = perf_counter() - bind_start
        self.index = Index.load(library=self.library)
        self.load_metrics = {
            **self.library.load_timings,
            **self.index.load_timings,
            "public_basis_bind_s": bind_seconds,
            "index_load_s": self.index.load_s,
            "resident_asset_setup_s": perf_counter() - started,
        }

    @staticmethod
    def _check_depth(depth):
        if depth not in (1, 2):
            raise ValueError("the graph controls only cover the archived depth≤2 domain")

    def project(self, public, depth):
        self._check_depth(depth)
        clean = verification_public(public)
        view = public_search.sanitize_public(SimpleNamespace(
            **vars(clean), configuration={"composition_depth": depth}
        ))
        self.index.validate_view(view)
        return clean, view, choose_variant(clean, self.library)

    def conditioned_count(self, public, depth):
        _, _, variant = self.project(public, depth)
        return int(self.index.conditioned_count(variant.header["pattern"], depth))

    def make_cursor(self, label, public, depth, limits, sample=None, *, deadline=None):
        if label not in GRAPH_METHODS:
            raise ValueError(f"unknown graph comparison lane {label}")
        return _GraphCursor(self, label, public, depth, limits, sample, deadline)

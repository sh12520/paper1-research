"""Typed partial-program best-first with public abstract score bounds."""

from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from math import isfinite
from time import perf_counter

from abstract_semantics import AbstractSemantics, ClauseHole, ProfileHole
from grammar_search import Entry, FlatPublicScore, SearchLimit, _score, decode_witness
from src.enumeration import syntax_key
from src.models import Delay, If, Offload, Sequence, Static, ValidFor
from src.state_machine import normalize


def interval_score_lower_bound(scorer, envelope):
    """Evaluate the score's monotone interval corners in frozen binary64 order."""
    violation = margin = quality = cost = 0.
    for position, cell in enumerate(envelope.cells):
        lower_violation, upper_margin = scorer.bound_terms(position, cell.demand_min)
        for term in lower_violation:
            violation += term
        for term in upper_margin:
            margin += term
        quality += cell.quality_max
        cost += cell.min_cost
    return _score(violation / 18., margin / 18., quality / 6., cost / 6., envelope.min_groups)


class ProductScore(FlatPublicScore):
    """Strengthen an interval bound by minimizing each finite output factor."""

    def __init__(self, public, grammar):
        super().__init__(public)
        self.grammar = grammar
        self.factor_min = lru_cache(maxsize=8192)(self._factor_min)

    def _factor_min(self, position, local_profiles, edge_profiles, may_idle, active_min_cost):
        active = self.cell_joint_min(position, local_profiles, edge_profiles, False)
        value = active + 0.02 * (active_min_cost / 6.)
        if may_idle:
            value = min(value, self.cell_idle[position])
        return value

    def lower_bound(self, envelope):
        factors = 0.
        for position, cell in enumerate(envelope.cells):
            # Every active result needs the grammar's static roles. The
            # abstraction may also supply additional unconditional roles.
            mandatory = cell.mandatory_roles | self.grammar.base_mask
            active_min_cost = self.grammar.role_superset_min_cost[mandatory]
            factors += self.factor_min(
                position, cell.local_profiles, cell.edge_profiles, cell.may_idle, active_min_cost,
            )
        product = factors + 0.08 + 0.01 * envelope.min_groups - self.joint_roundoff
        bound = max(interval_score_lower_bound(self, envelope), product)
        if not isfinite(bound):
            raise ValueError("nonfinite abstract score bound")
        return bound


def constructor_args(term):
    if isinstance(term, If):
        return term.condition, (term.then_clause, term.else_clause)
    if isinstance(term, Sequence):
        return term.duration, (term.first, term.second)
    if isinstance(term, Delay):
        return term.offset, (term.clause,)
    if isinstance(term, ValidFor):
        return term.interval, (term.clause,)
    if isinstance(term, Offload):
        return term.level, (term.clause,)
    raise TypeError("expected a contract constructor")


class HoleRefiner:
    """Deterministically partition the most constrained typed hole's domain."""

    def __init__(self, grammar):
        self.grammar = grammar
        options = (grammar.expand(hole) for hole in grammar.clause_holes)
        self.clause_options = tuple(options)
        cardinalities = [len(grammar.profiles)]
        for _ in grammar.clause_holes[1:]:
            children = cardinalities[-1]
            count_at_depth = len(grammar.profiles)
            for constructor, parameters in grammar.domain.productions:
                arity = 2 if constructor in (If, Sequence) else 1
                count_at_depth += len(parameters) * children ** arity
            cardinalities.append(count_at_depth)
        self.clause_cardinalities = tuple(cardinalities)
        self.profile_splits = lru_cache(maxsize=256)(self._profile_splits)
        self.smallest = lru_cache(maxsize=16384)(self._smallest)

    def _profile_splits(self, mask):
        ids = tuple(self.grammar._ids(mask))
        if len(ids) <= 3:
            return tuple(Static(self.grammar.profiles[i]) for i in ids)
        all_partitions = []
        for name in ("quality", "rate", "deadline"):
            partition = {}
            for i in ids:
                value = getattr(self.grammar.profiles[i], name)
                partition[value] = partition.get(value, 0) | (1 << i)
            if len(partition) > 1:
                masks = tuple(partition[value] for value in sorted(partition))
                all_partitions.append(masks)
        # Minimize the largest bucket; ties prefer fewer buckets and the
        # stable public coordinate order. Every split is disjoint and total.
        chosen = min(all_partitions, key=lambda masks: (
            max(mask.bit_count() for mask in masks), len(masks),
        ))
        return tuple(Static(ProfileHole(self.grammar.domain, subset)) for subset in chosen)

    def _smallest(self, node):
        if isinstance(node, ClauseHole):
            return self.clause_cardinalities[node.remaining_depth], ()
        if isinstance(node, Static):
            if isinstance(node.profile, ProfileHole):
                return node.profile.allowed_mask.bit_count(), ()
            return None
        _, children = constructor_args(node)
        candidates = []
        for index, child in enumerate(children):
            choice = self.smallest(child)
            if choice is not None:
                size, path = choice
                candidates.append((size, (index, *path)))
        return min(candidates, default=None)

    def _replace(self, node, path):
        if not path:
            if isinstance(node, ClauseHole):
                return self.clause_options[node.remaining_depth]
            return self.profile_splits(node.profile.allowed_mask)
        index = path[0]
        parameter, children = constructor_args(node)
        return tuple(type(node)(parameter, *children[:index], refined, *children[index + 1:])
                     for refined in self._replace(children[index], path[1:]))

    def expand(self, node):
        choice = self.smallest(node)
        if choice is None:
            raise AssertionError("cannot refine a complete derivation")
        return self._replace(node, choice[1])


class GenericCursor:
    """Stream all unique eligible signatures certified by a strict frontier."""

    def __init__(self, public, depth, limits, sample=None, *, deadline=None, strategy="mrv"):
        self.started = perf_counter()
        self.deadline = self.started + limits.wall_seconds
        if deadline is not None:
            self.deadline = min(self.deadline, deadline)
        self.public, self.depth, self.limits, self.sample = public, depth, limits, sample
        self.group_limit = 2 if depth <= 2 else 4
        self.grammar = AbstractSemantics(public, depth)
        if not self.grammar.encoder.all_predicates_true:
            raise ValueError("unsupported public predicate basis")
        self.encoder = self.grammar.encoder
        self.scorer = ProductScore(public, self.grammar)
        if strategy not in ("mrv", "preorder"):
            raise ValueError("unknown typed-hole refinement strategy")
        self.refine = HoleRefiner(self.grammar).expand if strategy == "mrv" else self.grammar.expand
        self.partial, self.complete = [], []
        self.seen = {}
        self.serial = count()
        self.exhausted = False
        self.next_sample_at = 0
        self.stats = dict(partial_generated=0, partial_expanded=0, frontier_peak=0,
                          complete_syntax=0, unique_semantics=0, scores=0, duplicates=0,
                          emitted=0, peak_working_set_bytes=0, witness_asts_materialized=0,
                          normalized_witnesses=0, lower_bound_evaluations=0,
                          structural_domain_rejects=0, pruned_empty=0)
        self._push(self.grammar.root)

    def _frontier_size(self):
        return len(self.partial) + len(self.complete)

    def _observe_frontier(self):
        self.stats["frontier_peak"] = max(self.stats["frontier_peak"], self._frontier_size())

    def check_limits(self, force=False):
        if self._frontier_size() > self.limits.frontier:
            raise SearchLimit("frontier_limit")
        if self.stats["partial_expanded"] >= self.limits.expanded:
            raise SearchLimit("expanded_limit")
        if perf_counter() >= self.deadline:
            raise SearchLimit("wall_time_limit")
        work = self.stats["partial_expanded"] + self.stats["complete_syntax"]
        if self.sample is not None and (force or work >= self.next_sample_at):
            self.stats["peak_working_set_bytes"] = max(self.stats["peak_working_set_bytes"], self.sample())
            self.next_sample_at = work + 128

    def assess(self, node):
        env = self.grammar.envelope(node)
        if env.min_groups > self.group_limit or env.max_groups == 0:
            self.stats["pruned_empty"] += 1
            return env, None
        self.stats["lower_bound_evaluations"] += 1
        return env, self.scorer.lower_bound(env)

    def _push(self, node, parent_bound=float("-inf")):
        envelope, bound = self.assess(node)
        if envelope.complete:
            self.stats["witness_asts_materialized"] += 1
        if bound is None:
            return
        # The parent's bound also holds on every refinement. Taking its
        # maximum with the new bound never risks dropping a true optimum.
        heappush(self.partial, (max(parent_bound, bound), next(self.serial), node, envelope.complete))
        self.stats["partial_generated"] += 1
        self._observe_frontier()

    def _score_leaf(self, node, bound):
        self.stats["complete_syntax"] += 1
        key = self.grammar.encoded(node)
        groups = self.scorer.group_count(key)
        if not 1 <= groups <= self.group_limit:
            self.stats["structural_domain_rejects"] += 1
            return
        previous = self.seen.get(key)
        if previous is None:
            score = self.scorer.score(key, groups)
            if not isfinite(score):
                raise ValueError("nonfinite exact public score")
            self.stats["unique_semantics"] += 1
            self.stats["scores"] += 1
            entry = Entry(key, score, syntax_key(node))
            self.seen[key] = entry
            heappush(self.complete, (score, key, entry))
            self._observe_frontier()
        else:
            self.stats["duplicates"] += 1
            if previous.witness is not None:
                raise AssertionError("previously emitted signature had an unresolved derivation")
            previous.raw_witness = min(previous.raw_witness, syntax_key(node))
            score = previous.score
        if bound > score:
            raise AssertionError("abstract score bound exceeds a descendant's exact score")

    def next_contract(self):
        while self.partial and (not self.complete or self.partial[0][0] <= self.complete[0][0]):
            self.check_limits()
            bound, _, node, complete = heappop(self.partial)
            if complete:
                self._score_leaf(node, bound)
            else:
                self.stats["partial_expanded"] += 1
                for child in self.refine(node):
                    self._push(child, bound)
        if not self.complete:
            self.exhausted = not self.partial
            self.check_limits(force=True)
            return None
        self.check_limits(force=True)
        _, _, entry = heappop(self.complete)
        representative = normalize(decode_witness(entry.raw_witness), self.public)
        if self.encoder.encode(representative) != entry.key:
            raise AssertionError("the frozen interpreter disagrees with the terminal semantic signature")
        entry.witness = syntax_key(representative)
        self.stats["emitted"] += 1
        self.stats["normalized_witnesses"] += 1
        return entry

    def metrics(self):
        boundary = self.complete[0] if self.complete else None
        return dict(self.stats, wall_s=perf_counter() - self.started,
                    frontier_remaining=len(self.partial),
                    frontier_min_lb=self.partial[0][0] if self.partial else None,
                    buffered_complete=len(self.complete),
                    buffered_best_score=boundary[0] if boundary else None,
                    buffered_best_key=boundary[1].hex() if boundary else None,
                    full_domain_exhausted=self.exhausted,
                    duplicate_states_eliminated=0)

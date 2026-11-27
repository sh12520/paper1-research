"""Exact research controls over the same frozen DepthCursor contract domain."""

from dataclasses import dataclass, replace
from functools import partial, reduce
from heapq import heappop, heappush
from itertools import count
from math import isfinite
from time import perf_counter

from .abstract_semantics import ClauseHole, GrammarDomain, ProfileHole
from .dedup_search import BoundInput, Recipe, partitions
from .depth_search import (
    DepthCursor, Template, observed_slots, recipe_text, rewrite_statics, shape_children, shape_ready,
)
from .grammar_search import Entry, SearchLimit, decode_witness
from .engine import ast_depth, required_capabilities
from .enumeration import syntax_key
from .models import Delay, If, Offload, Sequence, ValidFor
from .state_machine import normalize


NO_EARLY_SEMANTIC_DEDUP = "NO_EARLY_SEMANTIC_DEDUP"
GENERIC_BOUND_ONLY = "GENERIC_BOUND_ONLY"
DEFER_CAPABILITY_PRUNING = "DEFER_CAPABILITY_PRUNING"
WEAK_STATE_TIME_RESOURCE_ENVELOPE = "WEAK_STATE_TIME_RESOURCE_ENVELOPE"
NO_LAZY_STOP = "NO_LAZY_STOP"
NO_SEARCH_TIME_DOMAIN_NORMALIZATION = "NO_SEARCH_TIME_DOMAIN_NORMALIZATION"
ABLATIONS = (
    NO_EARLY_SEMANTIC_DEDUP,
    GENERIC_BOUND_ONLY,
    DEFER_CAPABILITY_PRUNING,
    WEAK_STATE_TIME_RESOURCE_ENVELOPE,
    NO_LAZY_STOP,
    NO_SEARCH_TIME_DOMAIN_NORMALIZATION,
)


class DeferredCapabilityCursor(DepthCursor):
    """Reject unavailable raw structures after profile assignment."""

    def _push_shape(self, shape):
        # The inherited constructor pushes exactly one root into an empty queue.
        if not hasattr(self, "allowed_raw_roles"):
            grammar = self.grammar
            self.allowed_raw_roles = grammar.domain.available_roles
            typed_productions = (
                (If, tuple(self.public.conditions)),
                (Sequence, tuple(self.public.durations)),
                (Delay, tuple(self.public.offsets)),
                (ValidFor, tuple(self.public.intervals)),
                (Offload, tuple(self.public.offload_levels)),
            )
            domain = GrammarDomain(grammar.profiles, typed_productions, self.allowed_raw_roles)
            grammar.domain = domain
            grammar.productions = dict(typed_productions)
            grammar.clause_holes = tuple(ClauseHole(d, domain) for d in range(self.depth + 1))
            grammar.profile_hole = ProfileHole(domain, grammar.all_profiles)
            grammar.root = grammar.clause_holes[-1]
            grammar.by_depth = [grammar.static_any]
            for _ in range(self.depth):
                child = grammar.by_depth[-1]
                modes = [grammar.static_any]
                for operator, parameters in typed_productions:
                    for parameter in parameters:
                        sibling = child if operator in (If, Sequence) else None
                        modes.append(grammar._transfer(operator, parameter, child, sibling))
                grammar.by_depth.append(grammar._union(modes, False))
            shape = grammar.root
            self.stats["deferred_capability_rejects"] = 0
            self.ineligible_templates = {}
            self.ineligible_ids = set()
            self.compiling_ineligible = False
        super()._push_shape(shape)

    def _compile(self, shape):
        if required_capabilities(shape) <= self.allowed_raw_roles:
            return super()._compile(shape)
        # Keep all pending assignments, but keep their raw witness recipes
        # separate from equally normalized, legally produced templates.
        eligible = self.template_keys
        self.template_keys = self.ineligible_templates
        self.compiling_ineligible = True
        try:
            return super()._compile(shape)
        finally:
            self.compiling_ineligible = False
            self.template_keys = eligible

    def _enqueue(self, template_id, values, current_mask, used):
        if self.compiling_ineligible:
            self.ineligible_ids.add(template_id)
        if template_id in self.ineligible_ids and len(values) == self.templates[template_id].visible:
            self.stats["deferred_capability_rejects"] += 1
            self.stats["complete_syntax"] += 1
            self.stats["partial_generated"] += 1
            self.stats["exact_state_keys"] += 1
            return
        super()._enqueue(template_id, values, current_mask, used)


class AlternateBoundCursor(DepthCursor):
    """Switch only the bound mapping (A2) or the bound input (A4)."""

    def __init__(self, view, depth, limits, sample=None, *, deadline=None, arm):
        self.arm = arm
        super().__init__(view, depth, limits, sample, deadline=deadline)

    def _push_shape(self, shape):
        if self.arm == GENERIC_BOUND_ONLY:
            if shape is self.grammar.root:
                from .generic_search import interval_score_lower_bound

                self.scorer.lower_bound = partial(interval_score_lower_bound, self.scorer)
            return super()._push_shape(shape)
        env = self.grammar.envelope(shape)
        if env.min_groups > self.group_limit or env.max_groups == 0:
            return
        if self.arm == WEAK_STATE_TIME_RESOURCE_ENVELOPE:
            env = replace(env, cells=self._uniform_cells(env.cells))
        bound = self.scorer.lower_bound(env)
        self.bound_evaluations += 1
        heappush(self.shapes, (bound, next(self.serial), shape))
        self.stats["shape_nodes_generated"] += 1
        self.stats["partial_generated"] += 1
        self._observe_frontier()

    def _uniform_cells(self, cells):
        self.stats["coarsened_envelopes"] = self.stats.get("coarsened_envelopes", 0) + 1
        cell = reduce(self.grammar._or_cell, cells)
        return (cell,) * len(cells)

    def _bound(self, template, values, current_mask, used):
        if self.arm == GENERIC_BOUND_ONLY:
            return super()._bound(template, values, current_mask, used)
        self.bound_evaluations += 1
        future = self.all_profiles & ~used
        next_slot = len(values)
        cells = []
        for label, level, roles in template.cells:
            if label < 0:
                cells.append(self.grammar.idle)
                continue
            if label < next_slot:
                mask = 1 << values[label]
            elif label == next_slot:
                mask = current_mask
            else:
                mask = future
            cells.append(self.grammar._cached_cell(mask if not level else 0,
                                                    mask if level else 0, False, roles, roles))
        return self.scorer.lower_bound(BoundInput(self._uniform_cells(cells), template.groups))


@dataclass(frozen=True, slots=True)
class RawTemplate:
    label_shape: object
    text: str
    visible: int


class LateKeyCursor(DepthCursor):
    """Defer exact key merging (A1) or normalization (A6) until assignments close."""

    def __init__(self, view, depth, limits, sample=None, *, deadline=None, arm):
        self.arm = arm
        self.emitted_keys = set()
        self.terminal_witnesses = {}
        super().__init__(view, depth, limits, sample, deadline=deadline)
        self.stats.update(terminal_duplicates=0, raw_template_merges=0, raw_asts_materialized=0)

    def _compile(self, shape):
        self.stats["symbolic_shapes_compiled"] += 1
        slot_ids = count()
        labelled = rewrite_statics(shape, lambda _profile: next(slot_ids))
        size = next(slot_ids)
        positions = (
            tuple(range(size)) if self.arm == NO_SEARCH_TIME_DOMAIN_NORMALIZATION
            else observed_slots(labelled, self.public)
        )
        self.stats["max_observed_profile_slots"] = max(
            self.stats["max_observed_profile_slots"], len(positions),
        )
        minimum = self.static_text[self.lex_profiles[0]]
        for partition in partitions(len(positions)) if positions else ((),):
            blocks = max(partition, default=-1) + 1
            if blocks > len(self.grammar.profiles):
                continue
            self.check_limits()
            self.stats["partial_expanded"] += 1
            self.stats["partition_probes"] += 1
            if self.arm == NO_SEARCH_TIME_DOMAIN_NORMALIZATION:
                text = recipe_text(labelled, tuple("{" + str(i) + "}" for i in partition))
                if text in self.template_keys:
                    self.stats["raw_template_merges"] += 1
                    continue
                shape_pattern = rewrite_statics(labelled, partition.__getitem__)
                template = RawTemplate(shape_pattern, text, blocks)
                self.template_keys[text] = len(self.templates)
            else:
                template = self._normal_template(labelled, positions, partition, blocks, size, minimum)
                if template is None:
                    continue
            template_id = len(self.templates)
            self.templates.append(template)
            self._enqueue(template_id, (), self.all_profiles, 0)

    def _normal_template(self, labelled, positions, partition, blocks, size, minimum):
        by_position = dict(zip(positions, partition))
        dummy = rewrite_statics(labelled, lambda pos: self.grammar.profiles[by_position.get(pos, 0)])
        key = self.grammar.encoded(dummy)
        groups = self.scorer.group_count(key)
        if key[0] != 1 or not 1 <= groups <= self.group_limit:
            return None
        visible = {}
        cells = []
        for pos in range(25, 49, 4):
            profile, level, high, low = key[pos:pos + 4]
            if profile == 255:
                cells.append((-1, 0, 0))
                continue
            if profile >= blocks:
                raise AssertionError("executed profile omitted from symbolic relevance")
            cells.append((visible.setdefault(profile, len(visible)), level, (high << 8) | low))
        labels = dict(visible)
        for profile in range(blocks):
            labels.setdefault(profile, len(labels))
        terms = tuple(
            "{" + str(labels[by_position[pos]]) + "}" if pos in by_position else minimum
            for pos in range(size)
        )
        recipe = Recipe(recipe_text(labelled, terms), blocks - len(visible))
        return Template(key[:25], tuple(cells), len(visible), groups, {recipe})

    def _bound(self, template, values, current_mask, used):
        if self.arm == NO_EARLY_SEMANTIC_DEDUP:
            return super()._bound(template, values, current_mask, used)
        self.bound_evaluations += 1
        assigned = len(values)
        future = self.all_profiles & ~used

        def profile_domain(slot):
            if slot < assigned:
                mask = 1 << values[slot]
            else:
                mask = current_mask if slot == assigned else future
            # Even singleton holes use the ordinary abstract transfer. The
            # search does not normalize the partial symbolic input.
            return ProfileHole(self.grammar.domain, mask)

        partial = rewrite_statics(template.label_shape, profile_domain)
        return self.scorer.lower_bound(self.grammar.envelope(partial))

    def _enqueue(self, template_id, values, current_mask, used):
        template = self.templates[template_id]
        if len(values) != template.visible:
            bound = self._bound(template, values, current_mask, used)
            heappush(self.partial, (bound, next(self.serial), template_id, values, current_mask, used))
        else:
            self.stats["complete_syntax"] += 1
            key, groups, witness_source = self._complete_assignment(template, values, used)
            if key is not None:
                self._keep_terminal(key, groups, witness_source)
        self.stats["partial_generated"] += 1
        self.stats["exact_state_keys"] += 1
        self._observe_frontier()

    def _complete_assignment(self, template, values, used):
        if self.arm == NO_EARLY_SEMANTIC_DEDUP:
            return self._key(template, values), template.groups, (template, values, used)
        texts = tuple(self.static_text[i] for i in values)
        raw = template.text.format(*texts)
        self.stats["raw_asts_materialized"] += 1
        self.stats["witness_recipe_evaluations"] += 1
        node = decode_witness(raw)
        key = self.grammar.encoded(node)
        groups = self.scorer.group_count(key)
        if key[0] != 1 or not 1 <= groups <= self.group_limit:
            return None, groups, raw
        return key, groups, raw

    def _keep_terminal(self, key, groups, source):
        if key in self.emitted_keys:
            raise AssertionError("a complete semantic duplicate survived beyond its cutoff")
        earlier = self.terminal_witnesses.get(key)
        if earlier is not None:
            self.stats["duplicates"] += 1
            self.stats["terminal_duplicates"] += 1
            if self.arm == NO_EARLY_SEMANTIC_DEDUP:
                earlier.append(source)
            elif source < earlier:
                self.terminal_witnesses[key] = source
            return
        score = self.scorer.score(key, groups)
        if not isfinite(score):
            raise ValueError("nonfinite precise leaf score")
        self.stats["unique_semantics"] += 1
        self.stats["scores"] += 1
        self.terminal_witnesses[key] = [source] if self.arm == NO_EARLY_SEMANTIC_DEDUP else source
        heappush(self.complete, (score, key))

    def _lexical_witness(self, key):
        source = self.terminal_witnesses.pop(key)
        if self.arm == NO_SEARCH_TIME_DOMAIN_NORMALIZATION:
            return source
        witnesses = []
        for template, values, used in source:
            recipe, = template.recipes
            texts = tuple(self.static_text[i] for i in values)
            hidden = tuple(self.static_text[i] for i in self.lex_profiles if not used & (1 << i))[:recipe.hidden]
            if recipe.hidden > len(hidden):
                raise AssertionError("hidden variables have no all-different extension")
            witnesses.append(recipe.text.format(*texts, *hidden))
        self.stats["witness_recipe_evaluations"] += len(witnesses)
        return min(witnesses)

    def next_contract(self):
        if self.inflight_lb is not None:
            raise SearchLimit("search was interrupted inside a bounded expansion")
        lower = self._frontier_lb()
        while lower is not None and (not self.complete or lower <= self.complete[0][0]):
            self.check_limits()
            self.stats["partial_expanded"] += 1
            shape_bound, assignment_bound = self._shape_lb(), self._assignment_lb()
            if shape_bound is not None and (assignment_bound is None or shape_bound <= assignment_bound):
                self.inflight_lb, _, shape = heappop(self.shapes)
                self.stats["shape_nodes_expanded"] += 1
                self._expand_shape(shape)
            else:
                self.inflight_lb, _, template_id, values, mask, used = heappop(self.partial)
                self.stats["assignment_nodes_expanded"] += 1
                self._expand(template_id, values, mask, used)
            self.inflight_lb = None
            lower = self._frontier_lb()
        if not self.complete:
            self.exhausted = lower is None
            return None
        self.check_limits(force=True)
        score, key = heappop(self.complete)
        raw = self._lexical_witness(key)
        witness = normalize(decode_witness(raw), self.public)
        if ast_depth(witness) > self.depth or self.grammar.encoded(witness) != key:
            raise AssertionError("a deferred witness differs from the exact key")
        self.stats["witness_asts_materialized"] += 1
        self.emitted_keys.add(key)
        self.stats["emitted"] += 1
        self.last_emitted_score = score
        return Entry(key, score, raw, syntax_key(witness))

    def _expand_shape(self, shape):
        if shape_ready(shape):
            self._compile(shape)
        else:
            for child in shape_children(shape, self.grammar):
                self._push_shape(child)

    def metrics(self):
        if self.arm == NO_SEARCH_TIME_DOMAIN_NORMALIZATION:
            # Raw templates carry one raw recipe and no normalized recipe set.
            return dict(
                self.stats, wall_s=perf_counter() - self.started, frontier_remaining=len(self.shapes) + len(self.partial)
                + (self.inflight_lb is not None), frontier_min_lb=self._frontier_lb(),
                buffered_complete=len(self.complete),
                buffered_best_score=self.complete[0][0] if self.complete else None,
                buffered_best_key=self.complete[0][1].hex() if self.complete else None,
                full_domain_exhausted=self.exhausted, template_count=len(self.templates),
                template_recipes=len(self.templates), lower_bound_evaluations=self.bound_evaluations,
                duplicate_states_eliminated=self.stats["raw_template_merges"],
            )
        return super().metrics()

def make_ablated(label, public, depth, limits, sample=None, *, deadline=None):
    if label in (NO_EARLY_SEMANTIC_DEDUP, NO_SEARCH_TIME_DOMAIN_NORMALIZATION):
        return LateKeyCursor(public, depth, limits, sample, deadline=deadline, arm=label)
    if label in (GENERIC_BOUND_ONLY, WEAK_STATE_TIME_RESOURCE_ENVELOPE):
        return AlternateBoundCursor(public, depth, limits, sample, deadline=deadline, arm=label)
    if label == DEFER_CAPABILITY_PRUNING:
        return DeferredCapabilityCursor(public, depth, limits, sample, deadline=deadline)
    if label == NO_LAZY_STOP:
        # The experiment driver requests exhaustive delivery using the same
        # cursor, preserving the exact prefix certificate as a checkpoint.
        return DepthCursor(public, depth, limits, sample, deadline=deadline)
    raise ValueError(f"unknown ablation {label!r}")

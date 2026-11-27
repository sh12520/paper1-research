"""Contextual quotient of the frozen depth-one and depth-two public grammar.

Only parameter-free operator shapes and restricted-growth profile equality
patterns are compiled. Remaining visible profile values are filled on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count, product
import json
from math import isfinite
import sys
from time import perf_counter

from abstract_semantics import AbstractSemantics
from grammar_search import Entry, FlatPublicScore, SearchLimit, decode_witness
from src.enumeration import syntax_key
from src.models import If, Sequence, Static
from src.state_machine import normalize


@dataclass(frozen=True,slots=True)
class Shape:
    constructor: object
    value: object
    children: tuple
    slots: int


@dataclass(frozen=True,slots=True)
class Recipe:
    text: str
    hidden: int


@dataclass(frozen=True,slots=True)
class Template:
    prefix: bytes
    cells: tuple
    visible: int
    groups: int
    recipes: tuple[Recipe,...]


@dataclass(frozen=True,slots=True)
class BoundInput:
    cells: tuple
    min_groups: int


def shape_domain(grammar, depth):
    leaf = Shape(Static,None,(),1)
    shapes = (leaf,)
    for _ in range(depth):
        previous = shapes
        current = [leaf]
        for op, domain in grammar.domain.productions:
            arity = 2 if op in (If,Sequence) else 1
            for parameter in domain:
                for children in product(previous,repeat=arity):
                    current.append(Shape(op,parameter,children,sum(node.slots for node in children)))
        shapes = tuple(current)
    return shapes


@lru_cache(maxsize=4)
def partitions(n):
    """One sequence of equality labels per set partition of n raw occurrences."""
    if n == 1:
        return ((0,),)
    return tuple(p+(block,) for p in partitions(n-1) for block in range(max(p)+2))


def dummy_ast(shape, values):
    if shape.constructor is Static:
        return Static(next(values))
    return shape.constructor(shape.value,*(dummy_ast(child,values) for child in shape.children))


def recipe_text(shape, labels):
    if shape.constructor is Static:
        return '{'+str(next(labels))+'}'
    op = json.dumps(shape.constructor.__name__,separators=(',',':'))
    value = json.dumps(shape.value,separators=(',',':'))
    return '['+op+','+value+','+','.join(recipe_text(child,labels) for child in shape.children)+']'


def compile_templates(grammar, scorer, depth):
    shapes = shape_domain(grammar,depth)
    by_quotient = {}
    symbolic_cases = 0
    for shape in shapes:
        for partition in partitions(shape.slots):
            blocks = max(partition)+1
            if blocks>len(grammar.profiles):
                continue
            symbolic_cases += 1
            # All representatives are from the existing public domain. They
            # stand only for equality labels; no query score is evaluated here.
            dummy = dummy_ast(shape,(grammar.profiles[i] for i in partition))
            key = grammar.encoded(dummy)
            if key[0]!=1:
                raise ValueError('frozen grammar must produce valid packed signatures')
            groups = scorer.group_count(key)
            if not 1<=groups<=2:
                continue
            visible = {}
            cells = []
            for j in range(25,49,4):
                i,level,hi,lo = key[j:j+4]
                if i==255:
                    cells.append((-1,0,0))
                else:
                    if not 0<=i<blocks:
                        raise AssertionError('transfer returned a profile not in symbolic assignment')
                    ordinal = visible.setdefault(i,len(visible))
                    cells.append((ordinal,level,(hi << 8)|lo))
            labels = dict(visible)
            for i in range(blocks):
                labels.setdefault(i,len(labels))
            text = recipe_text(shape,iter(labels[i] for i in partition))
            recipe = Recipe(text,blocks-len(visible))
            by_quotient.setdefault((key[:25],tuple(cells),len(visible),groups),set()).add(recipe)
    compiled = tuple(Template(prefix,cells,n,groups,tuple(sorted(recipes,key=lambda r:(r.text,r.hidden))))
                     for (prefix,cells,n,groups),recipes in sorted(by_quotient.items()))
    return compiled, len(shapes), symbolic_cases


class DedupCursor:
    def __init__(self, view, depth, limits, sample=None):
        if depth not in (1,2):
            raise ValueError('one scoped deduplication trial supports only original depths 1 and 2')
        self.started = perf_counter()
        self.public = view
        self.limits = limits
        self.sample = sample
        self.grammar = AbstractSemantics(view,depth)
        self.scorer = FlatPublicScore(view)
        built = perf_counter()
        self.templates,self.shape_count,self.symbolic_cases = compile_templates(self.grammar,self.scorer,depth)
        self.template_build_s = perf_counter()-built
        self.static_text = tuple(syntax_key(Static(p)) for p in self.grammar.profiles)
        self.lex_profiles = tuple(sorted(range(len(self.static_text)),key=self.static_text.__getitem__))
        self.all_profiles = self.grammar.all_profiles
        splits = []
        for field in ('quality','rate','deadline'):
            groups = {}
            for i,profile in enumerate(self.grammar.profiles):
                value = getattr(profile,field)
                groups[value] = groups.get(value,0) | (1 << i)
            splits.append(tuple(groups.values()))
        self.profile_splits = tuple(splits)
        self.partial, self.complete = [], []
        self.seen = set()
        self.serial = count()
        self.next_sample_at = 0
        self.last_emitted_score = None
        self.stats = dict(partial_generated=0,partial_expanded=0,frontier_peak=0,complete_syntax=0,
                          unique_semantics=0,scores=0,duplicates=0,emitted=0,peak_working_set_bytes=0,
                          exact_state_keys=0,witness_recipe_evaluations=0,witness_asts_materialized=0)
        self.template_recipes = sum(len(t.recipes) for t in self.templates)
        # Sum shallow objects and their owned payloads, excluding interpreter,
        # original public basis and reference data. OS working set is separate.
        self.template_payload_bytes = (sys.getsizeof(self.templates)+sum(
            sys.getsizeof(t)+sys.getsizeof(t.prefix)+sys.getsizeof(t.cells)
            +sum(sys.getsizeof(cell) for cell in t.cells)
            +sys.getsizeof(t.recipes)+sum(sys.getsizeof(r)+sys.getsizeof(r.text) for r in t.recipes)
            for t in self.templates))
        for template_id in range(len(self.templates)):
            self._enqueue(template_id,(),self.all_profiles,0)

    def _bound(self, template, values, current_mask, used):
        slots = len(values)
        future = self.all_profiles & ~used
        cell_bounds = []
        for label,level,roles in template.cells:
            if label < 0:
                cell_bounds.append(self.grammar.idle)
                continue
            mask = (1 << values[label]) if label<slots else (current_mask if label==slots else future)
            cell_bounds.append(self.grammar._cached_cell(mask if not level else 0,
                                                         mask if level else 0,False,roles,roles))
        return self.scorer.lower_bound(BoundInput(tuple(cell_bounds),template.groups))

    @staticmethod
    def _key(template,values):
        unpacked = bytearray(template.prefix)
        for label,level,roles in template.cells:
            if label<0:
                unpacked.extend((255,0,0,0))
            else:
                unpacked.extend((values[label],level,roles >> 8,roles & 255))
        return bytes(unpacked)

    def _enqueue(self, template_id, values, current_mask, used):
        template = self.templates[template_id]
        if len(values)==template.visible:
            key = self._key(template,values)
            if key in self.seen:
                raise AssertionError('disjoint canonical states produced a repeated signature')
            self.seen.add(key)
            score = self.scorer.score(key,template.groups)
            if not isfinite(score):
                raise ValueError('nonfinite public score')
            self.stats['complete_syntax'] += 1
            self.stats['unique_semantics'] += 1
            self.stats['scores'] += 1
            heappush(self.complete,(score,key,template_id,values,used))
        else:
            if not current_mask or current_mask & used:
                raise AssertionError('invalid all-different profile subdomain')
            bound = self._bound(template,values,current_mask,used)
            heappush(self.partial,(bound,next(self.serial),template_id,values,current_mask,used))
        self.stats['partial_generated'] += 1
        self.stats['exact_state_keys'] += 1
        self.stats['frontier_peak'] = max(self.stats['frontier_peak'],len(self.partial))

    def _expand(self, template_id, values, mask, used):
        if mask.bit_count()>3:
            for split in self.profile_splits:
                refinements = tuple(mask & group for group in split if mask & group)
                if len(refinements)>1:
                    for subset in refinements:
                        self._enqueue(template_id,values,subset,used)
                    return
        while mask:
            choice = mask & -mask
            mask ^= choice
            assigned = used | choice
            self._enqueue(template_id,values+(choice.bit_length()-1,),self.all_profiles & ~assigned,assigned)

    def _check_limits(self, force=False):
        if len(self.partial)>self.limits.frontier:
            raise SearchLimit('frontier_limit')
        if self.stats['partial_expanded']>=self.limits.expanded:
            raise SearchLimit('expanded_limit')
        if perf_counter()-self.started>=self.limits.wall_seconds:
            raise SearchLimit('wall_time_limit')
        popped = self.stats['partial_expanded']+self.stats['scores']
        if self.sample is not None and (force or popped>=self.next_sample_at):
            self.stats['peak_working_set_bytes'] = max(self.stats['peak_working_set_bytes'],self.sample())
            self.next_sample_at = popped+512

    def _witness(self, template, values, used):
        visible = tuple(self.static_text[i] for i in values)
        available = tuple(self.static_text[i] for i in self.lex_profiles if not used & (1 << i))
        strings = []
        for recipe in template.recipes:
            if recipe.hidden>len(available):
                raise AssertionError('hidden variables have no all-different extension')
            strings.append(recipe.text.format(*visible,*available[:recipe.hidden]))
        self.stats['witness_recipe_evaluations'] += len(strings)
        raw = min(strings)
        node = normalize(decode_witness(raw),self.public)
        self.stats['witness_asts_materialized'] += 1
        return raw,node

    def next_contract(self):
        while self.partial and (not self.complete or self.partial[0][0]<=self.complete[0][0]):
            self._check_limits()
            _,_,template_id,values,mask,used = heappop(self.partial)
            self.stats['partial_expanded'] += 1
            self._expand(template_id,values,mask,used)
        if not self.complete:
            return None
        self._check_limits(force=True)
        score,key,template_id,values,used = heappop(self.complete)
        raw,node = self._witness(self.templates[template_id],values,used)
        if self.grammar.encoded(node)!=key:
            raise AssertionError('symbolic candidate and canonical witness differ')
        self.stats['emitted'] += 1
        self.last_emitted_score = score
        return Entry(key,score,raw,syntax_key(node))

    def metrics(self):
        elapsed = perf_counter()-self.started
        deferred = (sum(bound>self.last_emitted_score for bound,*_ in self.partial)
                    if self.last_emitted_score is not None else None)
        return dict(self.stats,wall_s=elapsed,frontier_remaining=len(self.partial),
                    frontier_min_lb=self.partial[0][0] if self.partial else None,
                    bound_deferred_subtrees=deferred,last_emitted_score=self.last_emitted_score,
                    buffered_complete=len(self.complete),template_count=len(self.templates),
                    symbolic_shapes=self.shape_count,symbolic_cases=self.symbolic_cases,
                    template_recipes=self.template_recipes,template_payload_bytes=self.template_payload_bytes,
                    template_build_s=self.template_build_s,complete_key_memo_size=self.grammar.encoded.cache_info().currsize,
                    cell_memo_size=self.grammar._cached_cell.cache_info().currsize)

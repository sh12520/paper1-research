"""Lazy contextual quotient over the unchanged contract DSL."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
import json
from time import perf_counter

from abstract_semantics import AbstractSemantics, ClauseHole
from dedup_search import DedupCursor, Recipe, partitions
from grammar_search import Entry, FlatPublicScore, SearchLimit
from src.engine import ast_depth
from src.enumeration import syntax_key
from src.models import Delay, If, Offload, Sequence, Static, ValidFor
from src.state_machine import _active_roles


@dataclass(slots=True)
class Template:
    prefix: bytes
    cells: tuple
    visible: int
    groups: int
    recipes: set[Recipe]


def children_and_parameter(node):
    if isinstance(node,If):
        return (node.then_clause,node.else_clause),node.condition
    if isinstance(node,Sequence):
        return (node.first,node.second),node.duration
    if isinstance(node,Static):
        return (),None
    if isinstance(node,Delay):
        return (node.clause,),node.offset
    if isinstance(node,ValidFor):
        return (node.clause,),node.interval
    if isinstance(node,Offload):
        return (node.clause,),node.level
    raise TypeError('unknown skeleton constructor')


@lru_cache(maxsize=16384)
def shape_ready(node):
    if isinstance(node,ClauseHole):
        return False
    return all(shape_ready(child) for child in children_and_parameter(node)[0])


def shape_children(node, grammar):
    """Expand one clause hole. A symbolic Static never expands here."""
    if isinstance(node,ClauseHole):
        return grammar.expand(node)
    nodes, value = children_and_parameter(node)
    for i,child in enumerate(nodes):
        if not shape_ready(child):
            return tuple(type(node)(value,*nodes[:i],new_child,*nodes[i+1:])
                         for new_child in shape_children(child,grammar))
    return ()


def rewrite_statics(node, replace):
    if isinstance(node,Static):
        return Static(replace(node.profile))
    nodes, value = children_and_parameter(node)
    return type(node)(value,*(rewrite_statics(child,replace) for child in nodes))


def observed_slots(labelled, public):
    """Positions read at the root or by any child-key equality in normalize."""
    relevant = set()

    def observe(node):
        for t in range(public.horizon):
            for state in public.states:
                resolved = _active_roles(node,t,state)
                if resolved is not None:
                    relevant.add(resolved[0])

    def visit(node):
        nodes,_ = children_and_parameter(node)
        if isinstance(node,If):
            for child in nodes:
                observe(child)
        for child in nodes:
            visit(child)

    observe(labelled)
    visit(labelled)
    return tuple(sorted(relevant))


def recipe_text(node, terms):
    if isinstance(node,Static):
        return terms[node.profile]
    nodes,value = children_and_parameter(node)
    op = json.dumps(type(node).__name__,separators=(',',':'))
    parameter = json.dumps(value,separators=(',',':'))
    return '['+op+','+parameter+','+','.join(recipe_text(child,terms) for child in nodes)+']'


class DepthCursor(DedupCursor):
    """The depth-two quotient, instantiated only for live symbolic shapes.

    Open shape and assignment heaps jointly bound everything not yet scored.
    An in-flight expansion retains its predecessor bound until fully installed.
    """

    def __init__(self, view, depth, limits, sample=None, *, deadline=None):
        if depth not in (1,2,3):
            raise ValueError('supported depths are 1, 2 and 3')
        self.started = perf_counter()
        self.deadline = min(self.started+limits.wall_seconds,deadline) if deadline is not None else self.started+limits.wall_seconds
        self.public, self.limits, self.sample = view,limits,sample
        self.depth = depth
        self.group_limit = 2 if depth<=2 else 4
        self.grammar = AbstractSemantics(view,depth)
        if not self.grammar.encoder.all_predicates_true:
            raise ValueError('unsupported public predicate basis')
        self.scorer = FlatPublicScore(view)
        self.templates = []
        self.template_keys = {}
        self.emitted_templates = set()
        self.static_text = tuple(syntax_key(Static(p)) for p in self.grammar.profiles)
        self.lex_profiles = tuple(sorted(range(len(self.static_text)),key=self.static_text.__getitem__))
        self.all_profiles = self.grammar.all_profiles
        splits = []
        for field in ('quality','rate','deadline'):
            groups = {}
            for i,profile in enumerate(self.grammar.profiles):
                value = getattr(profile,field)
                groups[value] = groups.get(value,0)|(1 << i)
            splits.append(tuple(groups.values()))
        self.profile_splits = tuple(splits)
        self.shapes, self.partial, self.complete = [],[],[]
        self.seen = set()
        self.inflight_lb = None
        self.serial = count()
        self.next_sample_at = 0
        self.last_emitted_score = None
        self.exhausted = False
        self.bound_evaluations = 0
        self.stats = dict(partial_generated=0,partial_expanded=0,frontier_peak=0,complete_syntax=0,
                          unique_semantics=0,scores=0,duplicates=0,emitted=0,peak_working_set_bytes=0,
                          exact_state_keys=0,witness_recipe_evaluations=0,witness_asts_materialized=0,
                          shape_nodes_generated=0,shape_nodes_expanded=0,assignment_nodes_expanded=0,
                          symbolic_shapes_compiled=0,partition_probes=0,merged_template_states=0,
                          max_observed_profile_slots=0)
        self._push_shape(self.grammar.root)

    def _frontier_size(self):
        return len(self.shapes)+len(self.partial)+len(self.complete)+(self.inflight_lb is not None)

    def _observe_frontier(self):
        self.stats['frontier_peak'] = max(self.stats['frontier_peak'],self._frontier_size())

    def check_limits(self, force=False):
        if self._frontier_size()>self.limits.frontier:
            raise SearchLimit('frontier_limit')
        if self.stats['partial_expanded']>=self.limits.expanded:
            raise SearchLimit('expanded_limit')
        if perf_counter()>=self.deadline:
            raise SearchLimit('wall_time_limit')
        work = self.stats['partial_expanded']+self.stats['scores']
        if self.sample is not None and (force or work>=self.next_sample_at):
            self.stats['peak_working_set_bytes'] = max(self.stats['peak_working_set_bytes'],self.sample())
            self.next_sample_at = work+128

    def _bound(self, template, values, current_mask, used):
        self.bound_evaluations += 1
        return super()._bound(template,values,current_mask,used)

    def _enqueue(self, template_id, values, current_mask, used):
        super()._enqueue(template_id,values,current_mask,used)
        self._observe_frontier()

    def _push_shape(self, shape):
        e = self.grammar.envelope(shape)
        if e.min_groups>self.group_limit or e.max_groups==0:
            return
        bound = self.scorer.lower_bound(e)
        self.bound_evaluations += 1
        heappush(self.shapes,(bound,next(self.serial),shape))
        self.stats['shape_nodes_generated'] += 1
        self.stats['partial_generated'] += 1
        self._observe_frontier()

    def _compile(self, shape):
        self.stats['symbolic_shapes_compiled'] += 1
        idx = count()
        labelled = rewrite_statics(shape,lambda _profile:next(idx))
        size = next(idx)
        positions = observed_slots(labelled,self.public)
        self.stats['max_observed_profile_slots'] = max(self.stats['max_observed_profile_slots'],len(positions))
        n_profiles = len(self.grammar.profiles)
        cheap_partitions = partitions(len(positions)) if positions else ((),)
        min_text = self.static_text[self.lex_profiles[0]]
        for partition in cheap_partitions:
            blocks = max(partition,default=-1)+1
            if blocks>n_profiles:
                continue
            self.check_limits()
            self.stats['partial_expanded'] += 1
            self.stats['partition_probes'] += 1
            by_position = dict(zip(positions,partition))
            dummy = rewrite_statics(labelled,lambda i:self.grammar.profiles[by_position.get(i,0)])
            key = self.grammar.encoded(dummy)
            groups = self.scorer.group_count(key)
            if key[0]!=1 or not 1<=groups<=self.group_limit:
                continue
            visible = {}
            cells = []
            for j in range(25,49,4):
                i,level,hi,lo = key[j:j+4]
                if i==255:
                    cells.append((-1,0,0))
                else:
                    if not 0<=i<blocks:
                        raise AssertionError('executed profile omitted from symbolic relevance')
                    cells.append((visible.setdefault(i,len(visible)),level,(hi<<8)|lo))
            labels = dict(visible)
            for i in range(blocks):
                labels.setdefault(i,len(labels))
            terms = tuple('{'+str(labels[by_position[i]])+'}' if i in by_position else min_text for i in range(size))
            recipe = Recipe(recipe_text(labelled,terms),blocks-len(visible))
            identity = (key[:25],tuple(cells),len(visible),groups)
            template_id = self.template_keys.get(identity)
            if template_id is None:
                template_id = len(self.templates)
                self.template_keys[identity] = template_id
                self.templates.append(Template(*identity,{recipe}))
                self._enqueue(template_id,(),self.all_profiles,0)
            else:
                if template_id in self.emitted_templates:
                    raise AssertionError('an emitted contextual class still had a pending derivation')
                self.templates[template_id].recipes.add(recipe)
                self.stats['merged_template_states'] += 1

    def _shape_lb(self):
        return self.shapes[0][0] if self.shapes else None

    def _assignment_lb(self):
        return self.partial[0][0] if self.partial else None

    def _frontier_lb(self):
        observed = [x for x in (self._shape_lb(),self._assignment_lb(),self.inflight_lb) if x is not None]
        return min(observed,default=None)

    def next_contract(self):
        if self.inflight_lb is not None:
            raise SearchLimit('search was interrupted inside a bounded expansion')
        lower = self._frontier_lb()
        while lower is not None and (not self.complete or lower<=self.complete[0][0]):
            self.check_limits()
            self.stats['partial_expanded'] += 1
            s,a = self._shape_lb(),self._assignment_lb()
            if s is not None and (a is None or s<=a):
                self.inflight_lb,_,shape = heappop(self.shapes)
                self.stats['shape_nodes_expanded'] += 1
                if shape_ready(shape):
                    self._compile(shape)
                else:
                    for child in shape_children(shape,self.grammar):
                        self._push_shape(child)
            else:
                self.inflight_lb,_,template_id,values,mask,used = heappop(self.partial)
                self.stats['assignment_nodes_expanded'] += 1
                self._expand(template_id,values,mask,used)
            self.inflight_lb = None
            lower = self._frontier_lb()
        if not self.complete:
            self.exhausted = lower is None
            return None
        self.check_limits(force=True)
        score,key,template_id,values,used = heappop(self.complete)
        raw,node = self._witness(self.templates[template_id],values,used)
        if ast_depth(node)>self.depth or self.grammar.encoded(node)!=key:
            raise AssertionError('a recovered representative differs from the certified class')
        self.emitted_templates.add(template_id)
        self.stats['emitted'] += 1
        self.last_emitted_score = score
        return Entry(key,score,raw,syntax_key(node))

    def metrics(self):
        return dict(self.stats,wall_s=perf_counter()-self.started,frontier_remaining=len(self.shapes)+len(self.partial)+(self.inflight_lb is not None),
                    frontier_min_lb=self._frontier_lb(),buffered_complete=len(self.complete),
                    buffered_best_score=self.complete[0][0] if self.complete else None,
                    buffered_best_key=self.complete[0][1].hex() if self.complete else None,
                    full_domain_exhausted=self.exhausted,template_count=len(self.templates),
                    template_recipes=sum(len(x.recipes) for x in self.templates),
                    lower_bound_evaluations=self.bound_evaluations,
                    duplicate_states_eliminated=self.stats['merged_template_states'])

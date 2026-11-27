"""Verify a symbolic partition of the entire public DSL independently of queue order."""

from collections import Counter, defaultdict
from functools import lru_cache
from math import isfinite
from time import perf_counter
from types import SimpleNamespace
import json

from symbolic_format import (FORMAT, K_VALUES, ClauseHole, If,
                             Sequence, Static, descriptor, digest, parts, template_descriptor)
from abstract_semantics import AbstractSemantics
from cover_verifier import bound_checker
from grammar_search import decode_witness
from src.enumeration import syntax_key
from src.state_machine import _active_roles, normalize
from unseen_verifier import PublicReference, exact_cut, score_bits


class ProofRejected(ValueError):
    pass


def require(test, reason):
    if not test:
        raise ProofRejected(reason)


@lru_cache(maxsize=9)
def equality_patterns(count):
    """Canonical restricted growth strings partition all equality relations."""
    if count == 0:
        return ((),)
    return tuple(prefix + (name,) for prefix in equality_patterns(count-1)
                 for name in range(max(prefix, default=-1)+2))


def replace_profiles(tree, value):
    if isinstance(tree, Static):
        return Static(value(tree.profile))
    parameter, children = parts(tree)
    return type(tree)(parameter, *(replace_profiles(child, value) for child in children))


def iter_nodes(tree):
    yield tree
    for child in parts(tree)[1]:
        yield from iter_nodes(child)


def active_indices(tree, public):
    contexts = [tree]
    for node in iter_nodes(tree):
        if isinstance(node, If):
            contexts.extend(parts(node)[1])
    return sorted({active[0] for term in contexts for t in range(public.horizon) for s in public.states
                   if (active := _active_roles(term,t,s)) is not None})


def key_template(raw, groups):
    names = {}
    cells = []
    for offset in range(25,49,4):
        profile, level, a, b = raw[offset:offset+4]
        label = -1 if profile == 255 else names.setdefault(profile,len(names))
        cells.append((label, level, (a<<8)|b))
    return template_descriptor(raw[:25], cells, len(names), groups), names


def substitute(tree, terms):
    if isinstance(tree, Static):
        return terms[tree.profile]
    parameter, children = parts(tree)
    fields = [json.dumps(type(tree).__name__), json.dumps(parameter,separators=(",",":"))]
    fields.extend(substitute(child,terms) for child in children)
    return "[" + ",".join(fields) + "]"


class RootCoverage:
    def __init__(self, public, sample):
        self.public = public
        self.reference = PublicReference(public)
        self.semantics = AbstractSemantics(public,3)
        self.bound = bound_checker(self.reference,self.semantics)
        names = self.reference.encoder.roles
        self.group_indices = tuple(tuple(names.index(r) for r in group) for group in (
            ("apply_conditional_policy",), ("schedule_start",),
            ("apply_phased_policy","set_validity_interval"), ("enable_edge_offload",),
        ))
        self.text = tuple(syntax_key(Static(p)) for p in self.semantics.profiles)
        self.lexical = tuple(sorted(range(len(self.text)), key=self.text.__getitem__))
        self.recipe_bank = {}
        self.compiled = set()
        self.partition_count = 0
        self.merges = 0
        self.checked_bounds = 0
        self.coverage_visits = 0
        self.sample = sample
        self.all_profiles = self.semantics.all_profiles

    def group_count(self,key):
        return sum(any(key[1+2*i]!=255 for i in group) for group in self.group_indices)

    def expand_first_clause(self, node):
        """Reconstruct all ordered constructor/parameter branches, independently."""
        if isinstance(node, ClauseHole):
            out = [Static(self.semantics.profile_hole)]
            if node.remaining_depth:
                hole = self.semantics.clause_holes[node.remaining_depth-1]
                for cls, domain in self.reference.productions.items():
                    args = (hole,hole) if cls in (If,Sequence) else (hole,)
                    out.extend(cls(param,*args) for param in domain)
            return out
        if isinstance(node, Static):
            return ()
        value, children = parts(node)
        for pos, child in enumerate(children):
            choices = self.expand_first_clause(child)
            if choices:
                return tuple(type(node)(value,*children[:pos],choice,*children[pos+1:])
                             for choice in choices)
        return ()

    def check_bound(self, claimed, envelope, threshold):
        value = float.fromhex(claimed)
        require(isfinite(value), "Nonfinite lower bound")
        bound = self.bound.envelope(envelope)
        require(value <= bound, "Claimed bound exceeds recomputed lower bound")
        require(threshold is not None and value > threshold, "Undischarged region can tie or beat cutoff")
        self.checked_bounds += 1

    def compile_complete_shape(self, node):
        count = 0

        def number(_):
            nonlocal count
            count += 1
            return count-1

        labelled = replace_profiles(node,number)
        locations = active_indices(labelled,self.public)
        minimum = self.text[self.lexical[0]]
        for pattern in equality_patterns(len(locations)):
            self.partition_count += 1
            if self.partition_count % 256 == 0:
                self.sample()
            labels = max(pattern,default=-1)+1
            if labels > len(self.semantics.profiles):
                continue
            by_id = dict(zip(locations,pattern))
            assigned = replace_profiles(labelled,lambda i:self.semantics.profiles[by_id.get(i,0)])
            packed = self.semantics.encoded(assigned)
            groups = self.group_count(packed)
            if packed[0] != 1 or not 1 <= groups <= 4:
                continue
            identity, visible = key_template(packed,groups)
            require(all(i < labels for i in visible), "Observed profile missing from symbolic partition")
            map_ = dict(visible)
            for i in range(labels):
                map_.setdefault(i,len(map_))
            terms = [("{"+str(map_[by_id[i]])+"}") if i in by_id else minimum for i in range(count)]
            node_id = digest(("TEMPLATE", *identity))
            recipe = substitute(labelled,terms), labels-len(visible)
            if node_id in self.recipe_bank:
                self.merges += 1
                require(self.recipe_bank[node_id][0] == identity, "Symbolic context mismatch")
                self.recipe_bank[node_id][1].add(recipe)
            else:
                self.recipe_bank[node_id] = (identity,{recipe})

    def skeletons(self, open_shapes, closed_shapes, threshold):
        covered_open, covered_closed = set(), set()

        def walk(node):
            self.coverage_visits += 1
            if self.coverage_visits % 128 == 0:
                self.sample()
            name = digest(descriptor(node))
            envelope = self.semantics.envelope(node)
            if envelope.max_groups == 0 or envelope.min_groups > 4:
                require(name not in open_shapes and name not in closed_shapes,
                        "A structurally empty branch was represented as eligible")
                return
            if name in open_shapes:
                self.check_bound(open_shapes[name],envelope,threshold)
                covered_open.add(name)
                return
            choices = self.expand_first_clause(node)
            if not choices:
                require(name in closed_shapes, "Missing legal constructor or parameter branch")
                covered_closed.add(name)
                if name not in self.compiled:
                    self.compile_complete_shape(node)
                return
            for child in choices:
                walk(child)

        require(not (set(open_shapes) & closed_shapes), "Overlapping skeleton terminals")
        walk(self.semantics.root)
        require(covered_open == set(open_shapes) and covered_closed == closed_shapes, "Unreachable skeleton evidence")
        require(self.compiled <= closed_shapes, "A processed skeleton regressed between checkpoints")
        self.compiled = closed_shapes

    def assignment_key(self, identity, assigned):
        prefix, cells, visible, _ = identity
        require(len(assigned) == visible, "Completed assignment has wrong arity")
        data = bytearray.fromhex(prefix)
        for label,level,roles in cells:
            data.extend((255,0,0,0) if label < 0 else (assigned[label],level,roles>>8,roles&255))
        return bytes(data)

    def assignment_envelope(self, identity, assigned, mask):
        _, cells, visible, groups = identity
        require(len(assigned) < visible, "An assignment terminal cannot be an open node")
        unused = self.all_profiles & ~sum(1 << p for p in assigned)
        require(mask > 0 and mask & ~unused == 0, "Profile mask omits typed all-different context")
        bounds = []
        for label,level,roles in cells:
            if label < 0:
                bounds.append(self.semantics.idle)
            else:
                candidates = (1 << assigned[label] if label < len(assigned)
                              else mask if label == len(assigned) else unused)
                bounds.append(self.semantics._cached_cell(candidates if level == 0 else 0,
                                                         candidates if level == 1 else 0,False,roles,roles))
        return SimpleNamespace(cells=bounds,min_groups=groups)

    def canonical_witness(self, template_id, values):
        recipes = self.recipe_bank[template_id][1]
        visible = tuple(self.text[p] for p in values)
        free = tuple(self.text[p] for p in self.lexical if p not in values)
        require(all(count <= len(free) for _,count in recipes), "Hidden classes lack an all-different extension")
        raw = min(text.format(*visible,*free[:count]) for text,count in recipes)
        return syntax_key(normalize(decode_witness(raw),self.public))

    def assign(self, pending, completed):
        """Audit disjoint cover of every template's all-different assignment domain."""
        require(set(pending) | set(completed) == set(self.recipe_bank), "Missing or foreign template assignment root")
        for name,(identity,_) in self.recipe_bank.items():
            open_by_prefix = pending.get(name,{})
            scored = completed.get(name,set())
            branches = defaultdict(set)
            for sequence in (*open_by_prefix,*scored):
                require(len(set(sequence))==len(sequence) and all(0 <= p < len(self.text) for p in sequence),
                        "Profile assignment violates injectivity")
                for n,p in enumerate(sequence):
                    branches[sequence[:n]].add(p)
            touched_open,touched_complete = set(),set()

            def descend(prefix, available):
                self.coverage_visits += 1
                refines = branches.get(prefix,())
                mask = open_by_prefix.get(prefix,0)
                if len(prefix) == identity[2]:
                    require(prefix in scored and not refines and not mask, "Uncovered concrete assignment")
                    touched_complete.add(prefix)
                    return
                if mask:
                    require(not mask & ~available, "Open mask adds disallowed profile")
                    touched_open.add(prefix)
                childmask = sum(1<<p for p in refines)
                require(mask & childmask == 0, "Assignment subpartitions overlap")
                require(mask | childmask == available, "Missing profile partition or frontier assignment")
                for p in refines:
                    descend((*prefix,p),available & ~(1<<p))

            descend((),self.all_profiles)
            require(touched_open == set(open_by_prefix) and touched_complete == scored, "Unreachable assignment state")


def verify_symbolic(public, proof, binding, sealed_prefix, sealed_cuts, sample):
    started = perf_counter()
    require(set(proof) == {"format", "binding", "nodes", "checkpoints"} and
            proof.get("format") == FORMAT and proof["binding"] == binding, "Proof query or snapshot binding mismatch")
    pool = proof["nodes"]
    require(len(pool) <= 200_000, "Proof has too many pooled node identities")
    for key, node in pool.items():
        require(digest(node) == key, "Content identity mismatch")
    oracle = RootCoverage(public,sample)
    archived = oracle.reference.validated_prefix(sealed_prefix,3)
    used = Counter()
    verdicts = {}

    def get(key, kind):
        entry = pool.get(key)
        require(isinstance(entry,(tuple,list)) and entry and entry[0] == kind, "Unknown or wrong proof node kind")
        used[key] += 1
        return entry[1:]

    def template(key):
        entry = get(key,"TEMPLATE")
        expected = oracle.recipe_bank.get(key)
        require(expected is not None and digest(entry) == digest(expected[0]), "Unsafe contextual merge/template reference")
        return expected[0]

    prior_k = 0
    for k in K_VALUES:
        cut = proof["checkpoints"].get(str(k))
        if cut is None:
            break
        prior_k = k
        require(set(cut) == {"compiled","open_shapes","open_assignments","buffered","prefix","exhausted"},
                "Malformed cutoff partition")
        rows = [get(id_,"EMITTED")[0] for id_ in cut["prefix"]]
        claim = sealed_cuts[str(k)]
        require(claim["status"] in ("EXACT_TOPK_CERTIFIED","EXACT_TOPK_FULL_LENGTH","EXACT_DOMAIN_EXHAUSTED_SHORT"),
                "A resource-limited or unsound source cut cannot become certified")
        expected, _ = exact_cut(k,claim,archived)
        require(len(rows) == len(expected) and digest(rows) == digest(sealed_prefix[:len(expected)]),
                "Emitted IDs, score bits, witnesses or ordering differ from sealed prefix")
        verified = oracle.reference.validated_prefix(rows,3)
        threshold = verified[-1][1] if verified else None
        require(type(cut["exhausted"]) is bool, "Exhaustion assertion is malformed")
        if len(rows) < k or cut["exhausted"]:
            require(cut["exhausted"] and not any(cut[x] for x in ("open_shapes","open_assignments","buffered")),
                    "A short result has retained frontier regions")

        shapes = {}
        for id_ in cut["open_shapes"]:
            shape,val = get(id_,"OPEN_SHAPE")
            tag = digest(shape)
            require(tag not in shapes, "Repeated skeleton frontier node")
            shapes[tag] = val
        closed = {digest(get(id_,"COMPILED_SHAPE")[0]) for id_ in cut["compiled"]}
        require(len(closed)==len(cut["compiled"]), "Repeated processed skeleton")
        oracle.skeletons(shapes,closed,threshold)

        pending = defaultdict(dict)
        for id_ in cut["open_assignments"]:
            z, labels, mask, claimed = get(id_,"OPEN_ASSIGNMENT")
            labels = tuple(labels)
            require(type(mask) is int and mask > 0 and all(type(p) is int for p in labels),
                    "Malformed profile frontier assignment")
            identity = template(z)
            current = pending[z].get(labels,0)
            require(current & mask == 0, "Overlapping profile-mask frontier nodes")
            env = oracle.assignment_envelope(identity,labels,mask)
            oracle.check_bound(claimed,env,threshold)
            pending[z][labels] = current | mask

        completed = defaultdict(set)
        scores_to_check = []
        for id_ in cut["buffered"]:
            z, labels, key, score = get(id_,"COMPLETE_CANDIDATE")
            labels, key, score = tuple(labels), bytes.fromhex(key), float.fromhex(score)
            require(all(type(p) is int for p in labels), "Malformed buffered profile assignment")
            require(oracle.assignment_key(template(z),labels)==key, "Buffered assignment semantic key mismatch")
            require(labels not in completed[z], "Duplicate buffered completion")
            require(verified and (score,key) > (threshold,verified[-1][0]), "Buffered candidate beats cutoff")
            completed[z].add(labels)
            scores_to_check.append((key,score))
        for (key,actual),(recomputed,_) in zip(scores_to_check,oracle.reference.score_keys([k for k,_ in scores_to_check])):
            require(score_bits(actual)==score_bits(recomputed),"Buffered binary64 score mismatch")
        for key, _, witness in verified:
            identity, profiles = key_template(key,oracle.group_count(key))
            z = digest(("TEMPLATE",*identity))
            labels = tuple(profiles)
            require(z in oracle.recipe_bank and labels not in completed[z], "Missing or repeated canonical completion")
            require(oracle.canonical_witness(z,labels)==witness, "Canonical merged witness mismatch")
            completed[z].add(labels)
        oracle.assign(pending,completed)
        verdicts[str(k)] = ("EXACT_DOMAIN_EXHAUSTED_SHORT" if len(rows) < k else "EXACT_TOPK_FULL_LENGTH")

    require(set(proof["checkpoints"]) == set(verdicts), "Non-prefix checkpoint coverage")
    require(set(used)==set(pool), "Unreachable pooled proof records")
    return {
        "status": "VERIFIED" if prior_k == 500 else "VERIFIED_PARTIAL",
        "checkpoints": verdicts,
        "wall_s": perf_counter()-started,
        "unique_nodes":len(pool),
        "shared_nodes":sum(n>1 for n in used.values()),
        "partition_checks":oracle.partition_count,
        "coverage_visits":oracle.coverage_visits,
        "merge_recipe_checks":oracle.merges,
        "lower_bounds_checked":oracle.checked_bounds,
    }

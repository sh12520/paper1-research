"""Instrument the unchanged graph-free Cursor in a dedicated audit process."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from functools import lru_cache, wraps
import hashlib
import json
from pathlib import Path
import struct
import sys
from time import perf_counter_ns

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'results/grammar_gate'
sys.path[:0] = [str(OLD), str(ROOT / 'results/method_dev_v1'), str(ROOT)]

import grammar_search as old
from abstract_semantics import AbstractSemantics
from guard import graph_guard
from run_search import MemoryProbe, memory_status
from runtime import verification_public
from src.instances import deserialize_instance
from src.models import Delay, If, Offload, Sequence, Static, ValidFor


IDS = (
    'F1__medium__medium__rich__d2__s0',
    'F4__low__medium__sparse__d2__s0',
    'F1__low__medium__rich__d2__s0',
    'F1__low__medium__sparse__d1__s0',
)
LIMITS = old.Limits(12.0, 300000, 180000)
K = 500
ROOT_ORDERS = ('ClauseHole', 'Static', 'If', 'Sequence', 'Delay', 'ValidFor', 'Offload')
MIB = 1 << 20


class Clock:
    """Assign disjoint measured intervals to the innermost active phase."""

    def __init__(self):
        self.elapsed = Counter()
        self.calls = Counter()
        self.phase = 'other'
        self.last = perf_counter_ns()
        self.started = self.last
        self.running = True

    @contextmanager
    def measure(self, phase):
        if not self.running:
            yield
            return
        now = perf_counter_ns()
        self.elapsed[self.phase] += now - self.last
        previous = self.phase
        self.phase, self.last = phase, now
        self.calls[phase] += 1
        try:
            yield
        finally:
            now = perf_counter_ns()
            self.elapsed[phase] += now - self.last
            self.phase, self.last = previous, now

    def stop(self):
        now = perf_counter_ns()
        self.elapsed[self.phase] += now-self.last
        assert sum(self.elapsed.values()) == now-self.started
        self.running = False
        return now-self.started


class Observer:
    def __init__(self, clock):
        self.clock = clock
        self.by_root = {}
        self.pairs = []
        self.capture = None
        self.originals = []
        self.created = 1  # initial ClauseHole
        self.expand_depth = 0

    def tally(self, node, name, count=1):
        self.by_root.setdefault(type(node).__name__, Counter())[name] += count

    def patch(self, obj, attr, replacement):
        original = getattr(obj, attr)
        self.originals.append((obj, attr, original))
        setattr(obj, attr, replacement)
        return original

    def phase_wrapper(self, fn, phase):
        @wraps(fn)
        def measured(*args, **kwargs):
            with self.clock.measure(phase):
                return fn(*args, **kwargs)
        return measured

    def install(self):
        self.patch(AbstractSemantics, 'envelope', self.phase_wrapper(AbstractSemantics.envelope, 'envelope_lookup'))
        self.patch(AbstractSemantics, '_envelope', self.phase_wrapper(AbstractSemantics._envelope, 'abstract_envelope_construction'))
        self.patch(AbstractSemantics, '_transfer', self.phase_wrapper(AbstractSemantics._transfer, 'abstract_transformer'))
        self.patch(AbstractSemantics, '_complete_key', self.phase_wrapper(AbstractSemantics._complete_key, 'signature_transfer_cache_miss'))
        self.patch(old.FlatPublicScore, 'lower_bound', self.phase_wrapper(old.FlatPublicScore.lower_bound, 'lower_bound'))
        self.patch(old.FlatPublicScore, 'score', self.phase_wrapper(old.FlatPublicScore.score, 'exact_public_score'))
        self.patch(old, 'heappush', self.phase_wrapper(old.heappush, 'priority_queue_push'))
        self.patch(old, 'heappop', self.phase_wrapper(old.heappop, 'priority_queue_pop'))
        self.patch(old, 'normalize', self.phase_wrapper(old.normalize, 'emitted_witness_normalization'))
        self.patch(old, 'decode_witness', self.phase_wrapper(old.decode_witness, 'emitted_witness_parse'))
        raw_syntax_key = old.syntax_key
        def syntax(node):
            with self.clock.measure('witness_serialization'):
                value = raw_syntax_key(node)
            if self.capture is not None:
                with self.clock.measure('observer'):
                    self.capture['raw'] = value
            return value
        self.patch(old, 'syntax_key', syntax)

        expand = AbstractSemantics.expand
        def expand_once(grammar, node):
            self.expand_depth += 1
            try:
                with self.clock.measure('partial_child_creation'):
                    children = expand(grammar, node)
                if self.expand_depth == 1:
                    with self.clock.measure('observer'):
                        self.tally(node, 'hole_pops')
                        self.created += len(children)
                        for child in children:
                            self.tally(child, 'created')
                return children
            finally:
                self.expand_depth -= 1
        self.patch(AbstractSemantics, 'expand', expand_once)

        push = old.Cursor._push
        def push_measured(cursor, node):
            prior = cursor.stats['partial_generated']
            result = push(cursor, node)
            if cursor.stats['partial_generated'] != prior:
                with self.clock.measure('observer'):
                    self.tally(node, 'bound_frontier_admitted')
            return result
        self.patch(old.Cursor, '_push', push_measured)

        insert = old.Cursor._insert
        def insert_measured(cursor, node, bound):
            state = self.capture = {}
            prior = cursor.stats['duplicates'], cursor.stats['scores']
            try:
                with self.clock.measure('complete_leaf_bookkeeping'):
                    insert(cursor, node, bound)
            finally:
                self.capture = None
            with self.clock.measure('observer'):
                self.tally(node, 'complete_leaf')
                if cursor.stats['duplicates'] != prior[0]:
                    self.tally(node, 'duplicates')
                    self.pairs.append((state['raw'], state['incumbent_raw']))
                if cursor.stats['scores'] != prior[1]:
                    self.tally(node, 'unique_scored_first_seen')
        self.patch(old.Cursor, '_insert', insert_measured)

    def observe_cursor(self, cursor):
        raw_cache = cursor.grammar.encoded
        measured_cache = self.phase_wrapper(raw_cache, 'signature_lookup')
        cursor.grammar.encoded = measured_cache

        def key(node):
            result = measured_cache(node)
            if self.capture is not None:
                with self.clock.measure('observer'):
                    entry = cursor.seen.get(result)
                    self.capture['incumbent_raw'] = None if entry is None else entry.raw_witness
            return result
        cursor.key = key
        return raw_cache

    def restore(self):
        for obj, attr, original in reversed(self.originals):
            setattr(obj, attr, original)


def classify_pairs(pairs, grammar):
    """Flag observed AST patterns in equal-signature pairs after timing."""
    key = grammar.encoded

    @lru_cache(maxsize=8192)
    def inspection(node):
        if isinstance(node, Static):
            return frozenset()
        if isinstance(node, If):
            left, right = node.then_clause, node.else_clause
            own = {'redundant IF'} if key(left) == key(right) else set()
            return inspection(left) | inspection(right) | own
        if isinstance(node, Sequence):
            own = {'nested Sequence'} if any(isinstance(x, Sequence) for x in (node.first,node.second)) else set()
            return inspection(node.first) | inspection(node.second) | own
        child = node.clause
        own = set()
        if isinstance(node,(Delay,ValidFor)) and isinstance(child,(Delay,ValidFor)):
            own.add('nested Delay/ValidFor')
        if isinstance(node,Offload) and isinstance(child,Offload):
            own.add('repeated Offload')
        return inspection(child) | own

    @lru_cache(maxsize=2048)
    def ast(text):
        return old.decode_witness(text)

    @lru_cache(maxsize=8192)
    def projected_slots(node):
        slots = {}
        cells = tuple((t,s) for t in range(grammar.public.horizon) for s in grammar.public.states)

        def walk(part, points, path, hidden_reason=None):
            if isinstance(part, Static):
                slots[path] = (part.profile, hidden_reason)
                return ('Static',)
            if isinstance(part, If):
                then = tuple(x for x in points if x[1]=='moving')
                other = tuple(x for x in points if x[1]!='moving')
                label = 'state-shadowed IF profile variation'
                return ('If',part.condition,
                        walk(part.then_clause,then,path+(0,),hidden_reason or (None if then else label)),
                        walk(part.else_clause,other,path+(1,),hidden_reason or (None if other else label)))
            if isinstance(part, Sequence):
                first = tuple((t,s) for t,s in points if t<part.duration)
                second = tuple((t-part.duration,s) for t,s in points if t>=part.duration)
                label = 'time-cropped Sequence profile variation'
                return ('Sequence',part.duration,
                        walk(part.first,first,path+(0,),hidden_reason or (None if first else label)),
                        walk(part.second,second,path+(1,),hidden_reason or (None if second else label)))
            if isinstance(part, Delay):
                child = tuple((t-part.offset,s) for t,s in points if t>=part.offset)
                parameter = part.offset
            elif isinstance(part, ValidFor):
                start,end = part.interval
                child = tuple((t-start,s) for t,s in points if start<=t<end)
                parameter = part.interval
            else:
                child = points
                parameter = part.level
            label = 'time-cropped Delay/ValidFor profile variation'
            return (type(part).__name__,parameter,
                    walk(part.clause,child,path+(0,),hidden_reason or (None if child else label)))

        shape = walk(node,cells,())
        return shape, slots

    counts, by_pair, primary, examples = Counter(), Counter(), Counter(), {}
    priority = ('redundant IF','state-shadowed IF profile variation','time-cropped Sequence profile variation',
                'time-cropped Delay/ValidFor profile variation','nested Delay/ValidFor','nested Sequence','repeated Offload')
    for new, incumbent in pairs:
        left, right = ast(new), ast(incumbent)
        by_pair[(type(left).__name__,type(right).__name__)] += 1
        if new == incumbent:
            flags = {'same raw syntax'}
        else:
            flags = inspection(left) | inspection(right)
            left_shape,left_slots = projected_slots(left)
            right_shape,right_slots = projected_slots(right)
            if left_shape == right_shape:
                changed = [path for path,(profile,_) in left_slots.items() if profile!=right_slots[path][0]]
                if changed and all(left_slots[path][1] is not None for path in changed):
                    flags |= {left_slots[path][1] for path in changed}
            if not flags:
                flags = {'different syntax same signature (unassigned)'}
        main = next((x for x in priority if x in flags), sorted(flags)[0])
        primary[main] += 1
        counts.update(flags)
        examples.setdefault(main, (new,incumbent))
    return dict(overlapping_tags=dict(counts), exclusive_priority=dict(primary),
                root_pairs={f'{a} → {b}': n for (a,b), n in by_pair.items()}, examples=examples)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit_case(instance):
    public = verification_public(instance.public)
    depth = int(instance.public.configuration['composition_depth'])
    clock = Clock()
    observer = Observer(clock)
    observer.install()
    emitted = []
    status = 'COMPLETE'
    try:
        with clock.measure('cursor_setup'):
            cursor = old.Cursor(public,depth,LIMITS,MemoryProbe(768*MIB))
            raw_cache = observer.observe_cursor(cursor)
        while len(emitted) < K:
            item = cursor.next_contract()
            if item is None:
                break
            emitted.append(dict(key=item.key.hex(),score=item.score,witness=item.witness))
    except old.SearchLimit as exc:
        status = str(exc)
    finally:
        observer.restore()
    elapsed = clock.stop()
    metrics = cursor.metrics()
    signature_cache = raw_cache.cache_info()._asdict()
    cursor.grammar.encoded = raw_cache
    classified = classify_pairs(observer.pairs,cursor.grammar)
    assert len(observer.pairs) == metrics['duplicates']
    assert sum(classified['exclusive_priority'].values()) == metrics['duplicates']
    assert observer.created == metrics['partial_generated'] + metrics['pruned_illegal']
    phases = {p:dict(calls=clock.calls[p], seconds=seconds/1e9, fraction=seconds/elapsed)
              for p, seconds in clock.elapsed.items()}
    return dict(status=status, emitted=emitted, metrics=metrics, created=observer.created,
                root_rows={op:dict(c) for op,c in observer.by_root.items()},
                signature_cache=signature_cache, phases=phases, classifications=classified,
                clock_seconds=elapsed/1e9)


def report(rows, guard):
    lines = [
        '# GRAMMAR-DUPLICATION-KILL-01 · Original traversal cost audit', '',
        'This is a diagnostic replay of the original graph-free Cursor using fixed, existing serialized development queries. '
        'The audited implementation was wrapped in memory. No original source or results were edited. '
        'The graph guard remained active during retrieval and post-hoc AST-pair inspection. The native archived '
        'prefixes were opened after the guard exited, only to check instrumented behavior.', '',
        'K=500 and the prior limits of 12 s, 300,000 expansions, 180,000 frontier nodes and a 768 MiB worker '
        'working-set ceiling apply. Timing instrumentation itself adds overhead and can shorten a '
        'wall-limited prefix. The original sealed runtime and the instrumented phase timings are separately listed. '
        'The timed interval includes timer/wrapper overhead. No component duration is inferred from duplicate counts.', '',
        '`partial_children_created` counts the initial root and successors returned for attempted insertion, including '
        'complete successors. It excludes recursive temporary objects internal to hole replacement. Child-creation time '
        'includes the existing hole walk and constructors. Recursive wrapper counts need not equal the number of '
        'popped holes. Native `partial_generated` is the number admitted to the bound frontier. '
        'The abstract transformer, envelope/cache work, bound, queue, exact score and witness operations use '
        'exclusive timings. Queue counts include open and complete heaps. Emitted-witness normalization is the '
        'explicit normalization at emission. Internal Static packing is timed in semantic/signature work.', '',
        '| Instance | Original wall s / status | Instrumented wall s / status | Created | Expanded | Complete | Unique scored | Duplicate | Frontier peak | Certified outputs | Prefix check |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|',
    ]
    for key,row in rows.items():
        m, original = row['metrics'], row['archived']
        lines.append(f"| `{key}` | {original['wall_s']:.4f} / {original['status']} | {row['clock_seconds']:.4f} / {row['status']} | "
                     f"{row['created']} | {m['partial_expanded']} | {m['complete_syntax']} | {m['scores']} | {m['duplicates']} | "
                     f"{m['frontier_peak']} | {len(row['emitted'])} | {row['prefix_match']} ({row['common_prefix_size']}) |")
    lines.extend(['', '## Attribution interpretation', '',
                  'The diagnostic pairs each late-rejected AST with the **incumbent raw witness at the time of duplicate detection**. '
                  'Identical compact signatures establish equal normalized public execution and role footprint. '
                  'Redundant IF is diagnosed by equal child signatures. The nested Delay/ValidFor, nested Sequence and repeated '
                  'Offload labels describe patterns present in either AST. They do not prove independently that that pattern '
                  'caused the collision. For pairs with identical constructor-and-parameter shapes, an additional projection '
                  'walk labels changed Static profiles only if every changed slot is never visited by any of the six '
                  'public cells. These labels record fixed-state IF shadowing or time cropping. They preserve the '
                  'distinction between an unobservable profile value and an operator that still contributes to the '
                  'whole-contract footprint. Per-pair tags can overlap. The exclusive descriptive count puts equal '
                  'IF collapse first, projected profile variation second, wrapper shape tags third, and equal raw syntax '
                  'or other equal-signature pairs last. '
                  'This avoids double-counting while keeping the residual category explicit.', '',
                  'Signature-cache counters are captured before post-hoc pair inspection. Analysis of the pairs is outside the '
                  'phase clock. A reported `0` in an exclusive bucket means the trace did not expose that tagged collision.', ''])
    for key,row in rows.items():
        lines.extend([f'## `{key}`','',
                      '| Phase | Calls | Exclusive s | Share |','|---|---:|---:|---:|'])
        for phase,data in sorted(row['phases'].items(), key=lambda kv:-kv[1]['seconds']):
            lines.append(f"| {phase} | {data['calls']} | {data['seconds']:.6f} | {data['fraction']:.2%} |")
        lines.extend(['', '| Incoming root | Successors created | Admitted | Expanded | Complete transfers | First-seen scores | Duplicates |',
                      '|---|---:|---:|---:|---:|---:|---:|'])
        for op in ROOT_ORDERS:
            d = row['root_rows'].get(op,{})
            counts = [d.get(k,0) for k in ('created','bound_frontier_admitted','hole_pops','complete_leaf','unique_scored_first_seen','duplicates')]
            if op == 'ClauseHole':
                counts[0] += 1
            lines.append(f"| {op} | " + ' | '.join(map(str,counts)) + ' |')
        c = row['classifications']
        lines.extend(['', 'Duplicate root pairs (incoming → incumbent): `'+json.dumps(c['root_pairs'],ensure_ascii=False)+'`', '',
                      'Exclusive pattern counts: `'+json.dumps(c['exclusive_priority'],ensure_ascii=False)+'`', '',
                      'Overlapping pattern tags: `'+json.dumps(c['overlapping_tags'],ensure_ascii=False)+'`', '',
                      'Representative equal-signature pairs (incoming, incumbent): `'+json.dumps(c['examples'],ensure_ascii=False)+'`', '',
                      'Compact signature cache: `'+json.dumps(row['signature_cache'])+'`', ''])
    lines.extend(['## Independence', '', 'Guard snapshot: `'+json.dumps(guard)+'`', ''])
    (ROOT/'GRAMMAR_DUPLICATION_COST_AUDIT.md').write_text('\n'.join(lines),encoding='utf8')


def main():
    authorization = json.loads((ROOT/'PILOT_AUTHORIZATION_STATE.json').read_text(encoding='utf8'))
    if ((ROOT/'FROZEN_CONFIG.yaml').exists() or
            authorization['namespace_authorizations']['CONFIRM']['allowed'] is not False):
        raise ValueError('unexpected confirmation state')
    if memory_status()[1] < 1280*MIB:
        raise MemoryError('original engineering memory floor, 1,280 MiB')
    inputs = [ROOT/'results/pilot/instances'/(iid+'.json') for iid in IDS]
    manifest = json.loads((ROOT/'results/pilot/instances_manifest.json').read_text(encoding='utf8'))
    rows = {}
    with graph_guard(ROOT,allowed_inputs=inputs,output_dir=OLD/'virtual_cost_trace_no_files') as guard:
        for iid,path in zip(IDS,inputs):
            data = path.read_bytes()
            instance = deserialize_instance(data.decode('utf8'))
            expected = manifest[iid]
            if (sha(data) != expected['sha256'] or instance.instance_hash != expected['instance_hash'] or
                    instance.namespace != 'GENSPACE-FAIL-01-PILOT'):
                raise ValueError(f'changed or unauthorized serialized instance: {iid}')
            rows[iid] = audit_case(instance)
            m = rows[iid]['metrics']
            print(f'{iid} complete={m["complete_syntax"]} duplicates={m["duplicates"]} outputs={m["emitted"]}',flush=True)
        evidence = guard.snapshot()
    for iid,row in rows.items():
        source = json.loads((OLD/'fixed_depth2'/(iid+'.json')).read_text(encoding='utf8'))
        n = min(len(row['emitted']),len(source['topk']))
        common = all(a['key']==b['key'] and a['witness']==b['witness'] and
                     struct.pack('>d',a['score'])==struct.pack('>d',b['score'])
                     for a,b in zip(row['emitted'][:n],source['topk'][:n]))
        row.update(archived=dict(wall_s=source['topk_metrics']['wall_s'],status=source['topk_status']),
                   prefix_match='PASS' if n and common else 'NO OVERLAP' if not n else 'FAIL',common_prefix_size=n)
    report(rows,evidence)
    if not evidence['pass'] or any(row['prefix_match']=='FAIL' for row in rows.values()):
        raise ValueError('cost-audit graph independence or prefix comparison failed')


if __name__=='__main__':
    main()

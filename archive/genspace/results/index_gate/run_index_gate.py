"""Development-only replay over existing serialized instances and fixed V1.

The indexed execution substitutes only the B2 ID lookup and structural order
provider. The original run loop, verifier, agents and protocol are called as-is.
Historical outputs stay with the audit harness and are never query inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import threading
from time import perf_counter, sleep
from types import FunctionType, SimpleNamespace

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DEV = ROOT / 'results/method_dev_v1'
sys.path[:0] = [str(ROOT), str(DEV)]

import numpy as np

import private_protocol as protocol
import public_search as search
import runtime
import src.instances as instances
from src.fast_exact import FastLibrary
from src.fast_runner import _decode_witness
from src.state_machine import verify_instance
from tools.smoke_01 import memory_status, process_memory

from index_tree import Index
from index_query import QueryCursor

CHECKPOINTS = (100, 500, 5000)
TOP_K = (10, 50, 100, 500)
MIB = 1 << 20
NO_NEW_INPUT_CALLS = {'derive_seed': 0, 'generate_instance': 0}


def forbid_generation(name):
    def forbidden(*args, **kwargs):
        NO_NEW_INPUT_CALLS[name] += 1
        raise RuntimeError(f'{name} is forbidden in this audit')
    return forbidden


instances.derive_seed = forbid_generation('derive_seed')
instances.generate_instance = forbid_generation('generate_instance')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


class MemoryProbe:
    """Observation of the worker's RSS during the designated call windows."""

    def __init__(self):
        self.stop = threading.Event()
        self.active = False
        self.peak = 0
        self.minimum_available = memory_status()[1]
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def watch(self):
        while not self.stop.wait(.025):
            available = memory_status()[1]
            self.minimum_available = min(self.minimum_available, available)
            if available < 768 * MIB:
                print('PAUSED_MEMORY: system available <768 MiB', flush=True)
                os._exit(75)
            if self.active:
                self.peak = max(self.peak, process_memory(os.getpid())[0])

    def reset(self):
        self.peak = 0

    def __enter__(self):
        self.peak = max(self.peak, process_memory(os.getpid())[0])
        self.active = True
        return self

    def __exit__(self, *exc):
        self.active = False
        self.peak = max(self.peak, process_memory(os.getpid())[0])

    def close(self):
        self.stop.set()
        self.thread.join()


def flat_scores(view, library, ids, group_bits):
    """Reference recomputation of only the returned IDs, outside timings."""
    v, margin, quality, cost = search._proxy(view, library, ids)
    score = v - search.MARGIN_WEIGHT*margin + search.COST_WEIGHT*cost + search.QUALITY_WEIGHT*(1.-quality)
    counts = np.array([i.bit_count() for i in range(16)], dtype=np.uint8)
    score += search.GROUP_COMPLEXITY_WEIGHT*counts[group_bits[ids]]
    return score


class CursorOrder:
    """Adapter from original FLAT's slices to a resumable ordered prefix."""

    def __init__(self, cursor, monitor):
        self.cursor = cursor
        self.monitor = monitor
        self.retrieval_seconds = 0.0

    def __getitem__(self, selection):
        if not isinstance(selection, slice) or selection.step is not None or selection.stop is None:
            raise ValueError('unexpected V1 order access')
        with self.monitor:
            started = perf_counter()
            prefix, _ = self.cursor.retrieve_top_k(selection.stop)
            self.retrieval_seconds += perf_counter()-started
        if len(prefix) != selection.stop:
            raise ValueError('short retrieval before end of eligible domain')
        return prefix[selection]


def compiled_runner():
    """Only the B2 domain lookup is replaced in the In-memory V1 run loop."""
    source = inspect.getsource(runtime.run)
    old = 'bits=group_bits(library); static=np.flatnonzero(variant.mask(depth)&(bits==0))'
    if source.count(old) != 1:
        raise ValueError('V1 runtime source does not match the audit adapter')
    return compile(source.replace(old, 'bits, static = lookup_static(library, variant, depth)'),
                   '<V1 run with public candidate provider>', 'exec')


def timed_method(code, view, public, variant, private, library, index, kind, monitor, setup_seconds):
    stats = dict(domain_seconds=0., plan_seconds=0., flat_feature_s=0., exact_verification_s=0., negotiation_s=0., reconstruction_s=0.)
    plans = []
    monitor.reset()

    def track(key, fn):
        def wrapped(*args, **kwargs):
            started = perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                stats[key] += perf_counter()-started
        return wrapped

    # Execute the original plan bytecode. Its identical proxy has a timed
    # wrapper for feature calculation only. Remaining planning costs stay in
    # the public-search total and include the scalar formula and full sort.
    flat_plan = FunctionType(search.make_plan.__code__, dict(search.__dict__, _proxy=track('flat_feature_s', search._proxy)),
                             search.make_plan.__name__, search.make_plan.__defaults__)

    def lookup_static(lib, availability, depth):
        with monitor:
            started = perf_counter()
            if kind == 'flat':
                bits = search.group_bits(lib)
                ids = np.flatnonzero(availability.mask(depth) & (bits==0))
            else:
                bits = index.group_bits
                static = index.static_ids
                ids = static[availability.mask(depth)[static]]
            stats['domain_seconds'] += perf_counter()-started
        return bits, ids

    def provide_plan(view, lib, availability, b2_feasible, method, budget):
        with monitor:
            started = perf_counter()
            if kind == 'flat':
                plan = flat_plan(view, lib, availability, b2_feasible, method, budget=budget)
            else:
                cursor = QueryCursor(index, 'contract', view, lib, availability)
                order = CursorOrder(cursor, monitor)
                count = index.conditioned_count(availability.header['pattern'], view.depth)
                plan = SimpleNamespace(order=order, stages=(('flat', count),), mechanism_order=(), probe_count=0,
                                       probe_seconds=0., public_ranked_count=count, b2_proxy_count=0,
                                       public_setup_seconds=0., public_ranking_seconds=0.)
            stats['plan_seconds'] += perf_counter()-started
        plans.append(plan)
        return plan

    class TimedVerifier(protocol.PublicVerifier):
        __init__ = track('exact_verification_s', protocol.PublicVerifier.__init__)
        prepare_batch = track('exact_verification_s', protocol.PublicVerifier.prepare_batch)
        verify = track('exact_verification_s', protocol.PublicVerifier.verify)
        _agreement_witness = track('reconstruction_s', protocol.PublicVerifier._agreement_witness)

    env = dict(runtime.__dict__, make_plan=provide_plan, lookup_static=lookup_static,
               PublicVerifier=TimedVerifier, negotiate=track('negotiation_s', protocol.negotiate))
    exec(code, env)
    started = perf_counter()
    app = protocol.PrivateAgent('application', public, private.application)
    net = protocol.PrivateAgent('network', public, private.network)
    records, history = env['run'](view, public, variant, app, net, library,
                                  'FLAT-FEASIBILITY', stop_budget=5000)
    stats['total_method_s'] = (perf_counter()-started)+setup_seconds
    stats['peak_working_set_bytes'] = monitor.peak
    return records, history, plans[0] if plans else None, stats


def agreement_values(instance, records, known):
    for record in records.values():
        if not record['agreement']:
            continue
        witness = record['representative']
        if witness not in known:
            verification = verify_instance(_decode_witness(json.loads(witness)), instance,
                                           instance.public.configuration['composition_depth'])
            if not verification.verified:
                raise ValueError('agreement witness failed independent verification')
            known[witness] = dict(uA=verification.application_utility, uN=verification.network_utility,
                                  nash=verification.application_utility*verification.network_utility)
        record.update(known[witness])


def cursor_metrics(cursor):
    raw = cursor.metrics()
    fields = ('full_conditioned_count', 'internal_nodes_visited', 'all_internal_nodes', 'leaves_visited',
              'leaf_ids_inspected', 'node_bound_evaluations',
              'complete_candidates_touched', 'exact_public_scores', 'capability_rejects', 'depth_rejects',
              'bound_pruned_candidates', 'touch_ratio', 'node_visit_ratio', 'query_setup_s',
              'node_bound_s', 'traversal_s', 'candidate_scoring_s')
    return {key: raw[key] for key in fields}


def audit_instance(slot, target, library, index, manifest, code, monitor, generic):
    iid = slot['instance_id']
    config = slot['configuration']
    common = {'instance_id': iid, 'family': slot['family'], 'depth': config['composition_depth'],
              'richness': config['capability_richness'], 'pressure': config['resource_pressure'],
              'conflict': config['preference_conflict'], 'target': int(target),
              'fixed_config': int(slot['seed_index']==0)}
    raw = (ROOT / 'results/pilot/instances' / f'{iid}.json').read_bytes()
    instance = instances.deserialize_instance(raw.decode('utf8'))
    identity = dict(sha256=sha256(raw), instance_hash=instance.instance_hash,
                    public_hash=instance.public_hash, private_hash=instance.private_hash)
    if identity != manifest[iid] or instance.namespace != 'GENSPACE-FAIL-01-PILOT':
        raise ValueError(f'serialized input differs from original manifest: {iid}')
    started = perf_counter()
    public = runtime.verification_public(instance.public)
    view = search.sanitize_public(instance.public)
    availability = runtime.choose_variant(public, library)
    simple_setup = perf_counter()-started
    count = index.conditioned_count(availability.header['pattern'], view.depth)

    # The selection cohort stays with this harness. Both methods and all query
    # calls run before the historical agreement file is opened.
    flat_result, flat_history, flat_plan, flat_time = timed_method(
        code, view, public, availability, instance.private, library, index, 'flat', monitor, simple_setup)
    contract_result, contract_history, contract_plan, contract_time = timed_method(
        code, view, public, availability, instance.private, library, index, 'contract', monitor, simple_setup)
    if (flat_plan is None) != (contract_plan is None):
        raise ValueError(f'B2 expansion mismatch: {iid}')
    flat_public = simple_setup+flat_time['domain_seconds']+flat_time['plan_seconds']
    flat_peak = flat_time['peak_working_set_bytes']
    if flat_plan is None:
        # Fixed-grid correctness includes B2 successes. Obtain their public
        # structural ordering separately without folding it into method time.
        monitor.reset()
        with monitor:
            started = perf_counter()
            flat_plan = search.make_plan(view, library, availability, flat_result[5000]['public_feasible_b2'],
                                         'FLAT-FEASIBILITY', budget=5000)
            flat_public += perf_counter()-started
        flat_peak = max(flat_peak, monitor.peak)
    if flat_plan.public_ranked_count != count:
        raise ValueError(f'conditioned count mismatch: {iid}')
    if contract_plan is not None:
        n = contract_result[5000]['verification_calls'] - 27
        actual_ids, _ = contract_plan.order.cursor.retrieve_top_k(n)
        verified_order_equal = np.array_equal(actual_ids, flat_plan.order[:n])
    else:
        verified_order_equal = True
    reference = np.array(flat_plan.order[:TOP_K[-1]], copy=True)
    reference_scores = flat_scores(view, library, reference, index.group_bits)
    del flat_plan

    query_rows, correctness = [], []
    flat_work = dict(full_conditioned_count=count, internal_nodes_visited=None, all_internal_nodes=None,
                     leaves_visited=None, leaf_ids_inspected=None, node_bound_evaluations=None,
                     complete_candidates_touched=count, exact_public_scores=count,
                     capability_rejects=None, depth_rejects=None, bound_pruned_candidates=0,
                     touch_ratio=1. if count else 0., node_visit_ratio=None,
                     query_setup_s=simple_setup+flat_time['domain_seconds'], node_bound_s=None,
                     traversal_s=None, candidate_scoring_s=None)
    for k in TOP_K:
        query_rows.append(dict(common, variant='flat', k=k, **flat_work, returned_k=min(k,count),
                               total_public_search_s=flat_public, peak_working_set_bytes=flat_peak,
                               metadata_records_touched=len(library.keys), metadata_passes=2,
                               flat_feature_s=flat_time['flat_feature_s'] if not flat_result[5000]['b2_agreement'] else None))
    for tree in ('contract','generic') if generic else ('contract',):
        monitor.reset()
        measured = simple_setup+contract_time['domain_seconds']
        with monitor:
            started = perf_counter()
            cursor = QueryCursor(index, tree, view, library, availability)
            measured += perf_counter()-started
        for k in TOP_K:
            with monitor:
                started = perf_counter()
                ids, scores = cursor.retrieve_top_k(k)
                measured += perf_counter()-started
            expected = reference[:k]
            eq_order = np.array_equal(ids, expected)
            eq_set = np.array_equal(np.sort(ids), np.sort(expected))
            eq_score = eq_order and np.array_equal(scores.view(np.uint64), reference_scores[:k].view(np.uint64))
            metrics = cursor_metrics(cursor)
            query_rows.append(dict(common, variant=tree, k=k, **metrics, returned_k=len(ids),
                                   total_public_search_s=measured, peak_working_set_bytes=monitor.peak,
                                   metadata_records_touched=None, metadata_passes=0, flat_feature_s=None))
            correctness.append(dict(common, variant=tree, k=k, expected_k=len(expected), returned_k=len(ids),
                                    ids_equal=int(eq_set), order_equal=int(eq_order), scores_bitwise_equal=int(eq_score)))
        del cursor

    historical = read_json(DEV / 'run_protocol_fixed' / iid / 'record.json')
    oracle = historical['oracle']
    if (oracle['recoverable'] != target or historical['instance_hash'] != instance.instance_hash
            or ((not oracle['B2_agreement']) and oracle['O1_agreement']) != target):
        raise ValueError(f'cohort/identity mismatch: {iid}')
    original = historical['methods']['FLAT-FEASIBILITY']
    offline = {}
    agreement_values(instance, flat_result, offline)
    agreement_values(instance, contract_result, offline)
    research_fields = ('agreement','class_id','representative','uA','uN','nash','verification_calls',
                       'b2_agreement','public_feasible_candidates','proposals','rounds','path',
                       'termination_reason','stages','batch_calls','batch_candidate_checks','selected_group_mask')
    agreement = []
    for kind, records, history, plan, timings in (('flat',flat_result,flat_history,None,flat_time),
                                                   ('contract',contract_result,contract_history,contract_plan,contract_time)):
        when = {key: timings[key] for key in ('total_method_s','exact_verification_s','negotiation_s','reconstruction_s')}
        when['flat_feature_s'] = timings['flat_feature_s'] if kind=='flat' else None
        query_time = timings['plan_seconds']
        work = dict(query_setup_s=simple_setup+timings['domain_seconds'], node_bound_s=None, traversal_s=None,
                    candidate_scoring_s=None, complete_candidates_touched=count if kind=='flat' and not records[5000]['b2_agreement'] else 0,
                    exact_public_scores=count if kind=='flat' and not records[5000]['b2_agreement'] else 0)
        if plan is not None:
            metrics = cursor_metrics(plan.order.cursor)
            query_time += plan.order.retrieval_seconds
            for key in ('node_bound_s','traversal_s','candidate_scoring_s','complete_candidates_touched','exact_public_scores'):
                work[key] = metrics[key]
            work['query_setup_s'] += metrics['query_setup_s']
        when['public_search_s'] = simple_setup+timings['domain_seconds']+query_time
        for budget in CHECKPOINTS:
            record, old = records[budget], original['budgets'][str(budget)]
            ok = all(record.get(field)==old.get(field) for field in research_fields)
            if kind == 'contract':
                ok = ok and verified_order_equal
            messages = 2*old['proposals']
            history_ok = history[:messages] == original['history'][:messages] and len(history)>=messages
            if budget==5000:
                history_ok = history_ok and len(history)==messages
            agreement.append(dict(common, variant=kind, budget=budget, **{field:record.get(field) for field in research_fields[:7]},
                                  original_match=int(ok), history_match=int(history_ok),
                                  **(when if budget==5000 else {key:None for key in when}),
                                  **(work if budget==5000 else {key:None for key in work})))
    return dict(query=query_rows, correctness=correctness, agreement=agreement)


def guarded_inputs():
    if (ROOT/'FROZEN_CONFIG.yaml').exists():
        raise ValueError('unexpected FROZEN_CONFIG')
    state = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    if state['namespace_authorizations']['CONFIRM']['allowed'] is not False:
        raise ValueError('CONFIRM must stay denied')
    for _ in range(3):
        if memory_status()[1] < 2048*MIB:
            raise RuntimeError('PAUSED_MEMORY: system available <2 GiB')
        sleep(.2)


def export_csv(work_path, slots, output):
    grouped = {'query': [], 'correctness': [], 'agreement': []}
    for slot in slots:
        path = work_path / (slot['instance_id']+'.json')
        if path.exists():
            record = read_json(path)['rows']
            for key in grouped:
                grouped[key].extend(record[key])
    for key, name in (('query','per_query.csv'),('correctness','topk_correctness.csv'),('agreement','agreement_paths.csv')):
        records = grouped[key]
        if not records:
            continue
        with (output/name).open('w',encoding='utf8',newline='') as sink:
            writer = csv.DictWriter(sink, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)


def cohort_slots():
    plan = read_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
    with (ROOT/'results/flat_audit/per_instance.csv').open(encoding='utf8',newline='') as f:
        targets = {row['instance_id'] for row in csv.DictReader(f) if row['target_b2_no_full_o1_yes']=='1'}
    selected = [slot for slot in plan if slot['seed_index']==0 or slot['instance_id'] in targets]
    if len(targets)!=842 or len(selected)!=901 or sum(s['seed_index']==0 for s in selected)!=96:
        raise ValueError('unexpected immutable cohort coverage')
    return selected, targets


def bind_replay(output, index_path, selected, generic):
    paths = (Path(__file__), OUT/'index_tree.py', OUT/'index_query.py', DEV/'runtime.py',
             DEV/'private_protocol.py', DEV/'public_search.py', index_path/'manifest.json',
             ROOT/'PILOT01_PLAN_TEMPLATE.json', ROOT/'results/pilot/instances_manifest.json',
             ROOT/'results/flat_audit/per_instance.csv', ROOT/'PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json')
    expected = {
        'format': 'INDEX-GATE-01-replay-v1', 'python': sys.version, 'numpy': np.__version__,
        'inputs_sha256': {p.name:sha256(p.read_bytes()) for p in paths},
        'ordered_ids': [slot['instance_id'] for slot in selected], 'generic': generic,
        'top_k': list(TOP_K), 'agreement_checkpoints': list(CHECKPOINTS),
    }
    path = output/'replay_manifest.json'
    if path.exists():
        if read_json(path) != expected:
            raise ValueError('different source/index/fixture scope from previous run')
    else:
        if any((output/'work').iterdir()):
            raise ValueError('checkpoint transactions exist without provenance manifest')
        with path.open('x',encoding='utf8') as stream:
            json.dump(expected,stream,indent=2)
    return sha256(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index',type=Path,default=OUT/'index')
    parser.add_argument('--engineering-check',action='store_true')
    parser.add_argument('--skip-generic',action='store_true')
    args = parser.parse_args()
    guarded_inputs()
    selected, targets = cohort_slots()
    if args.engineering_check:
        members = {'F1__medium__medium__rich__d2__s0','F2__low__medium__sparse__d2__s0',
                   'F3__medium__medium__rich__d1__s0','F4__low__medium__sparse__d1__s0'}
        selected = [s for s in selected if s['instance_id'] in members]
        if len(selected)!=4:
            raise ValueError('incorrect engineering fixture selection')
    output = OUT/'engineering_check_final' if args.engineering_check else OUT
    work_path = output/'work'
    work_path.mkdir(exist_ok=True,parents=True)
    provenance = bind_replay(output,args.index,selected,not args.skip_generic)
    manifest = read_json(ROOT/'results/pilot/instances_manifest.json')
    code = compiled_runner()
    monitor = MemoryProbe()
    started = perf_counter()
    try:
        library = FastLibrary.from_graph(scope='pilot-execution')
        base_slot = selected[0]['instance_id']
        base_raw = (ROOT / 'results/pilot/instances' / f'{base_slot}.json').read_bytes()
        library.bind_public_basis(runtime.verification_public(instances.deserialize_instance(base_raw.decode('utf8')).public))
        index_started = perf_counter()
        index = Index.load(args.index,library=library)
        index_load = perf_counter()-index_started
        for n, slot in enumerate(selected,1):
            iid = slot['instance_id']
            path = work_path/(iid+'.json')
            if path.exists():
                checkpoint = read_json(path)
                rows = checkpoint['rows']
                if (checkpoint['replay_manifest_sha256'] != provenance or
                        checkpoint['rows_sha256'] != sha256(json.dumps(rows,allow_nan=False,separators=(',',':')).encode()) or
                        rows['agreement'][0]['instance_id']!=iid):
                    raise ValueError('invalid or incompatible replay checkpoint')
            else:
                rows = audit_instance(slot, iid in targets, library, index, manifest, code, monitor, not args.skip_generic)
                temporary = path.with_suffix('.pending')
                payload = {'replay_manifest_sha256':provenance,'rows':rows,
                           'rows_sha256':sha256(json.dumps(rows,allow_nan=False,separators=(',',':')).encode())}
                temporary.write_text(json.dumps(payload,allow_nan=False,separators=(',',':'))+'\n',encoding='utf8')
                temporary.replace(path)
            failed = any(not r['order_equal'] or not r['scores_bitwise_equal'] for r in rows['correctness']) or any(
                not r['original_match'] or not r['history_match'] for r in rows['agreement'])
            if n%10==0 or n<=4 or failed:
                print(f'{n}/{len(selected)} {iid} elapsed={perf_counter()-started:.1f} available={monitor.minimum_available//MIB} MiB error={failed}',flush=True)
            if failed and args.engineering_check:
                raise RuntimeError(f'engineering differential failed: {iid}')
        (output/'run_metadata.json').write_text(json.dumps(dict(
            instances=len(selected), generic_enabled=not args.skip_generic, index_load_s=index_load,
            minimum_available_bytes=monitor.minimum_available, peak_worker_working_set_bytes=process_memory(os.getpid())[1],
            generation_calls=NO_NEW_INPUT_CALLS, replay_manifest_sha256=provenance,
            elapsed_s=perf_counter()-started),indent=2)+'\n',encoding='utf8')
    finally:
        monitor.close()
        export_csv(work_path,selected,output)


if __name__ == '__main__':
    main()

"""Measure native FLAT public-plan working set on one existing rich depth-2 fixture."""

import sys

sys.dont_write_bytecode = True

import hashlib
import json
import os
from pathlib import Path
import threading
from time import perf_counter, sleep

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[1]
METHOD = ROOT / 'results' / 'method_dev_v1'
PILOT = ROOT / 'results' / 'pilot'
ID = 'F1__medium__medium__rich__d2__s0'
BUDGET = 5000
MIB = 1024 ** 2
SAMPLE_INTERVAL = 0.005
sys.path[:0] = [str(ROOT), str(METHOD)]

import numpy as np
from public_search import make_plan, sanitize_public
from runtime import choose_variant, verification_public
from src.fast_exact import FastLibrary
import src.instances as instances
from tools.smoke_01 import memory_status, process_memory


def forbidden(*args, **kwargs):
    raise RuntimeError('This measurement only reads existing serialized instances.')


instances.derive_seed = forbidden
instances.generate_instance = forbidden


def measure():
    preflight = []
    for _ in range(3):
        preflight.append(memory_status()[1])
        if preflight[-1] < 2048 * MIB:
            raise RuntimeError('PAUSED_MEMORY before graph loading')
        sleep(0.2)

    path = PILOT / 'instances' / f'{ID}.json'
    raw = path.read_bytes()
    instance = instances.deserialize_instance(raw.decode('utf8'))
    manifest = json.loads((PILOT / 'instances_manifest.json').read_text(encoding='utf8'))
    raw_sha = hashlib.sha256(raw).hexdigest()
    if {'sha256': raw_sha, 'instance_hash': instance.instance_hash,
            'public_hash': instance.public_hash, 'private_hash': instance.private_hash
        } != manifest[ID]:
        raise ValueError('serialized input does not match manifest')
    reference = METHOD / 'run_protocol_fixed' / ID / 'record.json'
    original_record = json.loads(reference.read_text(encoding='utf8'))
    original = original_record['methods']['FLAT-FEASIBILITY']['budgets'][str(BUDGET)]
    if not original_record['oracle']['recoverable'] or original['b2_agreement']:
        raise ValueError('fixture does not expand the structural search space')

    pid = os.getpid()
    stop = threading.Event()
    in_plan = threading.Event()
    samples = []
    available = preflight.copy()

    def sample_memory():
        while not stop.is_set():
            free = memory_status()[1]
            available.append(free)
            if free < 768 * MIB:
                print('PAUSED_MEMORY below emergency threshold', file=sys.stderr, flush=True)
                os._exit(75)
            if in_plan.is_set():
                samples.append(process_memory(pid)[0])
            stop.wait(SAMPLE_INTERVAL)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        library = FastLibrary.from_graph(scope='pilot-execution')
        public = verification_public(instance.public)
        library.bind_public_basis(public)
        view = sanitize_public(instance.public)
        variant = choose_variant(public, library)

        warm_working_set, warm_high_water = process_memory(pid)
        in_plan.set()
        start = perf_counter()
        plan = make_plan(view, library, variant, original['public_feasible_b2'],
                         'FLAT-FEASIBILITY', budget=BUDGET)
        elapsed = perf_counter() - start
        in_plan.clear()
        final_working_set, final_high_water = process_memory(pid)
    finally:
        stop.set()
        sampler.join()

    if not samples:
        raise RuntimeError('no online working-set samples')
    ranked = plan.public_ranked_count
    if ranked != len(plan.order) or ranked != original['public_ranked_count']:
        raise ValueError('public candidate count differs from the original development result')
    selected = np.flatnonzero(plan.order == original['class_id'])
    if len(selected) != 1 or selected.item() >= original['verification_calls'] - 27:
        raise ValueError('historical selected class is absent from its verified FLAT prefix')

    return {
        'instance_id': ID,
        'serialized_sha256': raw_sha,
        'python_version': sys.version.split()[0],
        'numpy_version': np.__version__,
        'scope': 'unmodified FLAT public make_plan only, after graph load, binding, and view setup',
        'budget': BUDGET,
        'conditioned_candidates_scored_sorted': ranked,
        'historical_candidate_count_match': True,
        'historical_selected_class_rank': selected.item() + 1,
        'working_set_warm_bytes': warm_working_set,
        'process_peak_before_plan_bytes': warm_high_water,
        'working_set_max_sample_in_plan_bytes': max(samples),
        'process_peak_at_plan_return_bytes': final_high_water,
        'working_set_at_plan_return_bytes': final_working_set,
        'plan_elapsed_seconds_with_sampler': elapsed,
        'in_plan_sample_count': len(samples),
        'nominal_sample_interval_seconds': SAMPLE_INTERVAL,
        'system_min_available_bytes': min(available),
    }


if __name__ == '__main__':
    result = measure()
    report = json.dumps(result, indent=2) + '\n'
    with (OUTPUT / 'flat_scan_working_set.json').open('x', encoding='utf8') as output:
        output.write(report)
    print(report, end='')

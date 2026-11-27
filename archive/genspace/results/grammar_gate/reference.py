"""Offline-only comparison of sealed online grammar-search results with FLAT.

Validate the completed online handoff before importing or loading the semantic
library. This process never writes online results or returns reference data to
the grammar search. All instance and reference files already exist.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEV = ROOT / 'results/method_dev_v1'
DEFAULT_SEAL = HERE / 'search_seal.json'
TOP_K = (10, 50, 100, 500)
BUDGETS = (100, 500, 5000)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as sink:
        writer = csv.DictWriter(sink, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sealed_cases(seal_path):
    raw = seal_path.read_bytes()
    seal = json.loads(raw)
    if seal.get('complete_batch') is not True or not isinstance(seal.get('cases'), dict):
        raise ValueError('online process completion seal is required before offline reference load')
    cases = {}
    for instance_id, entry in seal['cases'].items():
        path = (HERE / entry['path']).resolve()
        if not path.is_relative_to(HERE) or not path.is_file():
            raise ValueError('sealed case path leaves the grammar audit folder')
        payload = path.read_bytes()
        if sha256(payload) != entry['sha256']:
            raise ValueError(f'sealed online case hash mismatch: {instance_id}')
        case = json.loads(payload)
        if case['instance_id'] != instance_id:
            raise ValueError(f'sealed case identity mismatch: {instance_id}')
        cases[instance_id] = case
    if list(cases) != seal.get('manifest', {}).get('instance_ids'):
        raise ValueError('case list differs from sealed online manifest')
    return cases, sha256(raw)


def bits(value):
    return struct.pack('>d', float(value))


def same_float(left, right):
    if left is None or right is None:
        return left is None and right is None
    return bits(left) == bits(right)


def semantic_id(library, class_id):
    return None if class_id is None else library.keys[int(class_id)].tobytes().hex()


def historical_outcome(instance_id, raw_instance):
    case_dir = DEV / 'run_protocol_fixed' / instance_id
    raw = (case_dir / 'record.json').read_bytes()
    marker = read_json(case_dir / 'COMPLETE.json')
    if (marker['instance_id'] != instance_id or marker['record_sha256'] != sha256(raw)
            or marker['input_sha256']['instance'] != sha256(raw_instance)):
        raise ValueError(f'historical FLAT record does not match fixture: {instance_id}')
    return json.loads(raw)['methods']['FLAT-FEASIBILITY']


def event_keys(events, library=None):
    for event in events:
        identifier = event['candidate_id']
        if library is not None:
            identifier = semantic_id(library, identifier)
        yield event['agent'], event['message'], identifier


def compare_protocol(case, historical, library, budget, independent_utilities):
    result = case.get('protocol', {}).get(str(budget))
    if result is None:
        return {'status': 'NOT_COMPARED', 'reason': case.get('protocol_status', 'NOT_RUN')}
    expected = historical['budgets'][str(budget)]
    expected_history = historical['history'][:2 * int(expected['proposals'])]
    actual_history = result.get('history')
    if actual_history is None:
        actual_history = case.get('history', [])[:2 * int(result['proposals'])]
    failures = []
    if result['agreement'] != expected['agreement']:
        failures.append('agreement')
    if result.get('signature', result.get('class_id')) != semantic_id(library, expected['class_id']):
        failures.append('semantic_class')
    if result.get('representative') != expected.get('representative'):
        failures.append('representative')
    utilities = independent_utilities.get(result.get('representative'), {})
    for key in ('uA', 'uN', 'nash'):
        if (not same_float(utilities.get(key), expected.get(key))
                or (key in result and not same_float(result[key], utilities.get(key)))):
            failures.append(key)
    if result['verification_calls'] != expected['verification_calls']:
        failures.append('verification_calls')
    if list(event_keys(actual_history)) != list(event_keys(expected_history, library)):
        failures.append('proposal_history')
    if budget == BUDGETS[-1] and case.get('protocol_status') == 'COMPLETE' and 'history' in case:
        if len(case['history']) != len(expected_history) and 'proposal_history' not in failures:
            failures.append('proposal_history')
    return {'status': 'MISMATCH' if failures else 'MATCH', 'reason': ','.join(failures)}


def compare_prefix(case, expected, ranked_count, k):
    planned = min(k, ranked_count)
    actual = case.get('topk', ())[:k]
    available = min(len(actual), planned)
    ids_match = [r['key'] for r in actual[:available]] == [r[0] for r in expected[:available]]
    scores_match = all(bits(a['score']) == bits(ref[1]) for a, ref in zip(actual[:available], expected))
    first_diff = next((i for i, (a, ref) in enumerate(zip(actual[:available], expected), 1)
                       if a['key'] != ref[0] or bits(a['score']) != bits(ref[1])), None)
    reason = ''
    if not ids_match or not scores_match or len(actual) > planned:
        status = 'MISMATCH'
        reason = 'certified prefix disagrees with the original FLAT score/order/domain'
    elif len(actual) == planned and (planned == k or case.get('topk_status') == 'COMPLETE'):
        status = 'MATCH'
    elif case.get('topk_status') == 'COMPLETE':
        status = 'MISMATCH'
        reason = 'certified exhaustion before the original FLAT domain was exhausted'
    else:
        status = 'NOT_COMPARED'
        reason = case.get('topk_status', 'NOT_RUN')
    return dict(status=status, reason=reason, original_count=planned,
                certified_count=len(actual), compared_prefix=available,
                ordered_signatures_equal=int(ids_match) if available else '',
                score_bits_equal=int(scores_match) if available else '',
                first_difference_rank=first_diff,
                expected_signature=None if first_diff is None else expected[first_diff-1][0],
                actual_signature=None if first_diff is None else actual[first_diff-1]['key'],
                expected_score=None if first_diff is None else expected[first_diff-1][1],
                actual_score=None if first_diff is None else actual[first_diff-1]['score'])


def compare_offline(cases, slots, availability_rows):
    chosen = [slot for slot in slots if slot['instance_id'] in cases]
    if set(cases).difference(slot['instance_id'] for slot in chosen):
        raise ValueError('online seal names a case outside the existing PILOT plan')
    checkable = any(case.get('topk') or case.get('topk_status') == 'COMPLETE' or case.get('protocol')
                    for case in cases.values())
    top_rows, agreement_rows = [], []
    library = None
    if checkable:
        # Deliberately isolated from the online executable and after seal validation.
        sys.path[:0] = [str(ROOT), str(DEV)]
        import numpy as np
        import public_search as search
        import runtime
        from src.fast_exact import FastLibrary
        from src.fast_runner import _decode_witness
        import src.instances as instance_module
        from src.state_machine import verify_instance
        from tools.smoke_01 import memory_status

        def forbidden(*_unused, **_keywords):
            raise RuntimeError('seed and instance generation are forbidden in the offline reference')

        instance_module.generate_instance = forbidden
        instance_module.derive_seed = forbidden
        if memory_status()[1] < 2 * 1024 ** 3:
            raise MemoryError('offline graph reference requires 2 GiB system memory headroom')
        library = FastLibrary.from_graph(scope='pilot-execution')
        groups = search.group_bits(library)
        group_counts = np.asarray([x.bit_count() for x in range(16)], dtype=np.uint8)
        instance_manifest = read_json(ROOT / 'results/pilot/instances_manifest.json')
    for index, slot in enumerate(slots):
        instance_id = slot['instance_id']
        case = cases.get(instance_id, {})
        public_meta = availability_rows[instance_id]
        if not case and slot['seed_index'] != 0 and public_meta['target_b2_no_full_o1_yes'] != '1':
            continue
        common = dict(instance_id=instance_id, family=slot['family'],
                      fixed_grid=int(slot['seed_index'] == 0),
                      target=int(public_meta['target_b2_no_full_o1_yes']),
                      depth=int(slot['configuration']['composition_depth']),
                      richness=slot['configuration']['capability_richness'],
                      conditioned_count=int(public_meta['conditioned_structural_method_eligible']))
        top_checkable = bool(case.get('topk')) or case.get('topk_status') == 'COMPLETE'
        protocol_checkable = bool(case.get('protocol'))
        expected_rank, historical, utilities = (), None, {}
        if library is not None and (top_checkable or protocol_checkable):
            if memory_status()[1] < 768 * 1024 ** 2:
                raise MemoryError('offline graph reference paused at system memory floor')
            raw_instance = (ROOT / 'results/pilot/instances' / (instance_id + '.json')).read_bytes()
            instance = instance_module.deserialize_instance(raw_instance.decode('utf-8'))
            if instance.namespace != 'GENSPACE-FAIL-01-PILOT' or instance_manifest[instance_id] != dict(
                    sha256=sha256(raw_instance), instance_hash=instance.instance_hash,
                    public_hash=instance.public_hash, private_hash=instance.private_hash):
                raise ValueError(f'known serialized instance differs from manifest: {instance_id}')
            if case.get('serialized_sha256') != sha256(raw_instance) or case.get('configuration') != slot['configuration']:
                raise ValueError(f'sealed case input provenance differs from original fixture: {instance_id}')
            if protocol_checkable:
                historical = historical_outcome(instance_id, raw_instance)
                for result in case['protocol'].values():
                    witness = result.get('representative')
                    if result['agreement'] and witness is not None and witness not in utilities:
                        verified = verify_instance(_decode_witness(json.loads(witness)), instance, common['depth'])
                        if verified.verified:
                            uA, uN = verified.application_utility, verified.network_utility
                            utilities[witness] = dict(uA=uA, uN=uN, nash=uA*uN)
            if top_checkable:
                public = runtime.verification_public(instance.public)
                library.bind_public_basis(public)
                view = search.sanitize_public(instance.public)
                variant = runtime.choose_variant(public, library)
                # The B2 public feasible count populates a diagnostic signature.
                # It does not enter the FLAT score or candidate domain.
                plan = search.make_plan(view, library, variant, 0, 'FLAT-FEASIBILITY', budget=5000)
                if plan.public_ranked_count != common['conditioned_count']:
                    raise ValueError(f'original FLAT conditioning conflicts with audited count: {instance_id}')
                ids = plan.order[:TOP_K[-1]]
                violation, margin, quality, cost = search._proxy(view, library, ids)
                scores = (violation - search.MARGIN_WEIGHT * margin
                          + search.COST_WEIGHT * cost + search.QUALITY_WEIGHT * (1. - quality))
                scores += search.GROUP_COMPLEXITY_WEIGHT * group_counts[groups[ids]]
                expected_rank = tuple((semantic_id(library, cid), float(score))
                                      for cid, score in zip(ids, scores))
                del plan, ids, scores, violation, margin, quality, cost
        for k in TOP_K:
            comparison = compare_prefix(case, expected_rank, common['conditioned_count'], k)
            top_rows.append(dict(common, k=k, **comparison))
        for budget in BUDGETS:
            comparison = compare_protocol(case, historical, library, budget, utilities)
            agreement_rows.append(dict(common, budget=budget, **comparison))
        if (top_checkable or protocol_checkable) and index % 25 == 0:
            print(f'offline comparison at fixture {index + 1}/{len(slots)}: {instance_id}', flush=True)
    return top_rows, agreement_rows, library is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', type=Path, default=DEFAULT_SEAL)
    parser.add_argument('--output-dir', type=Path, default=None)
    args = parser.parse_args()
    cases, seal_sha256 = sealed_cases(args.seal)
    slots = read_json(ROOT / 'PILOT01_PLAN_TEMPLATE.json')['instances']
    with (ROOT / 'results/flat_audit/per_instance.csv').open(encoding='utf-8', newline='') as file:
        availability_rows = {row['instance_id']: row for row in csv.DictReader(file)}
    top, agreement, graph_loaded = compare_offline(cases, slots, availability_rows)
    out = (args.output_dir or (HERE if args.seal.resolve() == DEFAULT_SEAL else args.seal.resolve().parent / 'offline')).resolve()
    if not out.is_relative_to(HERE):
        raise ValueError('offline comparison output leaves the grammar audit folder')
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'topk_correctness.csv', tuple(top[0]), top)
    write_csv(out / 'agreement_correctness.csv', tuple(agreement[0]), agreement)
    meta = dict(sealed_cases=len(cases), seal_sha256=seal_sha256, reference_graph_loaded=graph_loaded,
                topk_rows=len(top), agreement_rows=len(agreement),
                topk_mismatches=sum(row['status'] == 'MISMATCH' for row in top),
                agreement_mismatches=sum(row['status'] == 'MISMATCH' for row in agreement))
    (out / 'reference_metadata.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(meta), flush=True)


if __name__ == '__main__':
    main()

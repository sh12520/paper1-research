"""Offline FLAT comparison for sealed grammar-deduplication trials."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOP_K = (10, 50, 100, 500)
BUDGETS = (100, 500, 5000)
REQUIRED_GUARD_COUNTERS = frozenset((
    'semantic_graph_file', 'index_gate_artifact', 'availability_index_artifact',
    'unlisted_workspace_input', 'write_outside_current_output', 'FastLibrary.from_graph',
    'FastLibrary.__init__', 'AvailabilityBundle.load', 'read_graph', 'graph_library',
    'compact_dp.compact_library', 'compact_graph.compact_library', 'semantic_dp.library',
    'semantic_dp.streaming_reference', 'enumeration.candidates',
    'engine.enumerate_compositions', 'generate_instance', 'derive_seed',
))


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    content = json.dumps(value, indent=2, allow_nan=False) + '\n'
    pending = path.with_suffix('.pending')
    pending.write_text(content, encoding='utf-8')
    pending.replace(path)


def guarded_seal(path):
    path = path.resolve()
    if not path.is_relative_to(HERE):
        raise ValueError('seal path leaves the grammar-deduplication audit directory')
    raw = path.read_bytes()
    seal = json.loads(raw)
    if seal.get('complete_batch') is not True or not isinstance(seal.get('cases'), dict):
        raise ValueError('online batch seal is required')
    guard = seal.get('guard', {})
    counters = guard.get('forbidden_call_counts', {})
    if (guard.get('pass') is not True or not REQUIRED_GUARD_COUNTERS <= set(counters)
            or any(v != 0 for v in counters.values())
            or guard.get('blocked')):
        raise ValueError('online guard counters did not pass')
    cases = {}
    for instance_id, info in seal['cases'].items():
        case_file = (HERE / info['path']).resolve()
        if not case_file.is_relative_to(path.parent) or not case_file.is_file():
            raise ValueError(f'sealed case leaves its output directory: {instance_id}')
        payload = case_file.read_bytes()
        if info['sha256'] != hash_bytes(payload):
            raise ValueError(f'sealed case bytes changed: {instance_id}')
        case = json.loads(payload)
        if case['instance_id'] != instance_id:
            raise ValueError(f'sealed case identity differs: {instance_id}')
        cases[instance_id] = case
    manifest = seal['manifest']
    if not cases or list(cases) != manifest.get('instance_ids') or not manifest.get('sources'):
        raise ValueError('online manifest scope differs from seal')
    return seal, cases, hash_bytes(raw)


def frozen_reference():
    """Read existing reference code without resolving any graph at import time."""
    path = ROOT / 'results/grammar_gate/reference.py'
    spec = importlib.util.spec_from_file_location('frozen_grammar_gate_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.TOP_K != TOP_K or module.BUDGETS != BUDGETS:
        raise ValueError('existing reference has different K/checkpoints')
    return module, hash_bytes(path.read_bytes())


def original_cohorts():
    slots = load_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
    indexed = {row['instance_id']: row for row in read_csv(ROOT/'results/flat_audit/per_instance.csv')}
    fixed = {slot['instance_id'] for slot in slots if slot['seed_index'] == 0}
    target = {instance_id for instance_id, row in indexed.items() if row['target_b2_no_full_o1_yes'] == '1'}
    rich = {i for i in target if indexed[i]['composition_depth'] == '2' and indexed[i]['capability_richness'] == 'rich'}
    large = {i for i in target if int(indexed[i]['conditioned_structural_method_eligible']) >= 100_000}
    if (len(fixed), len(target), len(rich), len(large)) != (96, 842, 298, 340):
        raise ValueError('old development cohort counts changed')
    return slots, indexed, fixed, target, rich, large


def totals(rows, field, values, fixed):
    result = {}
    for value in values:
        selected = [row for row in rows if row[field] == value]
        if len(selected) != len(fixed) or {row['instance_id'] for row in selected} != fixed:
            raise ValueError(f'offline reference coverage differs for {field}={value}')
        result[str(value)] = dict(exact=sum(r['status'] == 'MATCH' for r in selected),
                                  mismatch=sum(r['status'] == 'MISMATCH' for r in selected),
                                  incomplete=sum(r['status'] == 'NOT_COMPARED' for r in selected))
    return result


def compare_fixed(seal_path):
    seal, cases, seal_hash = guarded_seal(seal_path)
    slots, indexed, fixed, _, _, _ = original_cohorts()
    if (set(cases) != fixed or seal['manifest'].get('phase') != 'correctness'
            or seal['manifest'].get('mode') != 'both'):
        raise ValueError('correctness comparison requires all 96 original fixed queries')
    module, reference_hash = frozen_reference()
    # Independent reference code may load the existing graph here. The online
    # worker is already exited and the complete batch seal has been verified.
    topk, protocol, graph_loaded = module.compare_offline(cases, slots, indexed)
    topk = [row for row in topk if row['instance_id'] in fixed]
    protocol = [row for row in protocol if row['instance_id'] in fixed]
    topk_summary = totals(topk, 'k', TOP_K, fixed)
    protocol_summary = totals(protocol, 'budget', BUDGETS, fixed)
    out = seal_path.resolve().parent/'offline'
    out.mkdir(exist_ok=True)
    paths = dict(topk=out/'topk_correctness.csv', protocol=out/'agreement_correctness.csv')
    write_csv(paths['topk'], topk)
    write_csv(paths['protocol'], protocol)
    all_checks = tuple(topk_summary.values()) + tuple(protocol_summary.values())
    mismatch = any(check['mismatch'] for check in all_checks)
    exact = all(check['exact'] == len(fixed) for check in all_checks)
    evidence = dict(instance_count=len(cases), seal_sha256=seal_hash,
                    online_sources=seal['manifest']['sources'],
                    graph_loaded_after_online_worker=graph_loaded,
                    reference_source_sha256=reference_hash,
                    topk=topk_summary, protocol=protocol_summary,
                    correctness_status='PASS' if exact else 'MISMATCH' if mismatch else 'INCOMPLETE',
                    performance_allowed=exact,
                    files_sha256={name:hash_bytes(path.read_bytes()) for name, path in paths.items()})
    write_json(out/'correctness_evidence.json', evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', type=Path, required=True)
    args = parser.parse_args()
    evidence = compare_fixed(args.seal)
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if evidence['performance_allowed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

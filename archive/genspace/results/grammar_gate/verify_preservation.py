"""Offline checksum audit of preserved inputs and the sealed online worker.

Run after the timed online batch has exited. Hashes already recorded by the
FLAT and INDEX gates are the historical trust anchors. This script does not
decode graph data or import experimental methods.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FLAT = ROOT/'results/flat_audit'
INDEX = ROOT/'results/index_gate'
OLD_TREES = (
    'src', 'schemas', 'tests', 'results/method_dev_v1', 'results/pilot',
    'results/pilot_attribution', 'results/pilot_attribution_work',
)
ONLINE_SOURCES = {
    'run_search.py', 'grammar_search.py', 'abstract_semantics.py', 'guard.py', 'protocol_adapter.py',
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def compare(expected):
    missing, changed = [], []
    for name, digest in expected.items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f'manifest path leaves the workspace: {name}')
        if not path.is_file():
            missing.append(name)
        elif file_sha(path) != digest:
            changed.append(name)
    return missing, changed


def replay_paths():
    source = ROOT/'results/method_dev_v1'
    return {
        **{name: INDEX/name for name in ('run_index_gate.py','index_tree.py','index_query.py')},
        **{name: source/name for name in ('runtime.py','private_protocol.py','public_search.py')},
        'manifest.json': INDEX/'index/manifest.json',
        'PILOT01_PLAN_TEMPLATE.json': ROOT/'PILOT01_PLAN_TEMPLATE.json',
        'instances_manifest.json': ROOT/'results/pilot/instances_manifest.json',
        'per_instance.csv': FLAT/'per_instance.csv',
        'PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json': ROOT/'PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json',
    }


def historical_checks():
    base = read_json(FLAT/'baseline_hashes.json')
    audit = read_json(INDEX/'audit_input_hashes.json')
    conflicts = sorted(k for k in base.keys() & audit.keys() if base[k] != audit[k])
    combined = {**base, **audit}
    old_paths = {
        path.relative_to(ROOT).as_posix()
        for directory in OLD_TREES
        for path in (ROOT/directory).rglob('*') if path.is_file()
    }
    added = sorted(old_paths.difference(combined))

    replay = INDEX/'replay_manifest.json'
    old_index_run = read_json(INDEX/'run_metadata.json')
    replay_sealed = old_index_run['replay_manifest_sha256'] == file_sha(replay)
    replay_expected = read_json(replay)['inputs_sha256']
    paths = replay_paths()
    if set(paths) != set(replay_expected):
        raise ValueError('unexpected prior index replay path set')
    for key, path in paths.items():
        name = path.relative_to(ROOT).as_posix()
        if name in combined and combined[name] != replay_expected[key]:
            conflicts.append(name)
        combined[name] = replay_expected[key]

    index = INDEX/'index'
    array_manifest = read_json(index/'manifest.json')
    arrays = {'shared':array_manifest['features'], **array_manifest['tree_arrays']}
    for directory, entries in arrays.items():
        for array_name, info in entries.items():
            name = (index/directory/(array_name+'.npy')).relative_to(ROOT).as_posix()
            combined[name] = info['sha256']
    missing, changed = compare(combined)
    return dict(files_checked=len(combined), historical_manifest_conflicts=conflicts,
                missing=missing, changed=changed, unexpected_files_in_historical_trees=added,
                prior_index_replay_seal_matches=replay_sealed)


def sealed_online_checks(seal_path):
    if not seal_path.is_file():
        return dict(online_batch_sealed=False, seal_verified=False, clean_guard=False)
    seal = read_json(seal_path)
    manifest = seal['manifest']
    manifest_match = manifest == read_json(seal_path.parent/'online_manifest.json')
    case_paths_match = list(seal['cases']) == manifest['instance_ids']
    source_expected = manifest['sources']
    source_layout_match = set(source_expected) == ONLINE_SOURCES
    source_changes = []
    for name in ONLINE_SOURCES:
        file = HERE/name
        if not file.is_file() or file_sha(file) != source_expected.get(name):
            source_changes.append(name)

    instance_manifest = read_json(ROOT/'results/pilot/instances_manifest.json')
    case_changes, input_changes = [], []
    for iid, entry in seal['cases'].items():
        case_path = (HERE/entry['path']).resolve()
        if case_path != (seal_path.parent/(iid+'.json')).resolve() or not case_path.is_file():
            case_changes.append(iid)
            continue
        if file_sha(case_path) != entry['sha256']:
            case_changes.append(iid)
            continue
        row = read_json(case_path)
        original = instance_manifest.get(iid, {})
        if (row.get('instance_id')!=iid or row.get('serialized_sha256') != original.get('sha256') or
                row.get('instance_hash') != original.get('instance_hash')):
            input_changes.append(iid)

    guard = seal['guard']
    counts = guard.get('forbidden_call_counts', {})
    required_guard_keys = {
        'semantic_graph_file','index_gate_artifact','availability_index_artifact',
        'unlisted_workspace_input','write_outside_current_output','FastLibrary.from_graph',
        'FastLibrary.__init__','AvailabilityBundle.load','read_graph','graph_library',
        'compact_dp.compact_library','compact_graph.compact_library','semantic_dp.library',
        'semantic_dp.streaming_reference','enumeration.candidates','engine.enumerate_compositions',
        'generate_instance','derive_seed',
    }
    clean_guard = (guard.get('pass') is True and guard.get('blocked') == [] and
                   required_guard_keys <= set(counts) and all(type(v) is int and v==0 for v in counts.values()))
    sealed = seal.get('complete_batch') is True and manifest_match and case_paths_match
    seal_verified = sealed and source_layout_match and not (source_changes or case_changes or input_changes)
    return dict(online_batch_sealed=sealed, seal_verified=seal_verified, clean_guard=clean_guard,
                seal_sha256=file_sha(seal_path), sealed_cases=len(seal['cases']),
                online_source_changes=sorted(source_changes), sealed_case_changes=case_changes,
                sealed_case_input_mismatches=input_changes,
                forbidden_call_counts=counts, blocked_events=guard.get('blocked', []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seal', type=Path, default=HERE/'fixed_depth2'/'search_seal.json')
    args = parser.parse_args()
    historical = historical_checks()
    online = sealed_online_checks(args.seal.resolve())
    auth = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    confirm_denied = auth['namespace_authorizations']['CONFIRM']['allowed'] is False
    frozen_exists = (ROOT/'FROZEN_CONFIG.yaml').exists()
    preserved = (not any(historical[k] for k in ('historical_manifest_conflicts','missing','changed',
                                                'unexpected_files_in_historical_trees'))
                 and historical['prior_index_replay_seal_matches'] and confirm_denied and not frozen_exists)
    complete = preserved and online['seal_verified'] and online['clean_guard']
    report = dict(preserved=preserved, confirm_denied=confirm_denied, frozen_config_exists=frozen_exists,
                  graph_independence_checks=('PASS' if complete else 'UNVERIFIED' if preserved and
                                              not online['online_batch_sealed'] else 'FAIL'),
                  historical=historical, online=online)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    (HERE/'preservation_check.json').write_text(json.dumps(report, ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if not complete:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

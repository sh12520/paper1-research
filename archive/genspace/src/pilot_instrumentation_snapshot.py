"""Pilot instrumentation preparation fingerprint; no research execution.

This preparation scope deliberately is not accepted as an executable FAST
scope. It requires a future explicit authorization and a separately audited
execution route before any PILOT or CONFIRM seed can be generated.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .execution_snapshot import ROOT, SMOKE02_SNAPSHOT, build_snapshot, sha256_file

PILOT_PREPARATION_SCOPE = 'pilot-preparation'
PILOT_SNAPSHOT = ROOT / 'PILOT_EXECUTION_SNAPSHOT_FINGERPRINT.json'
PILOT_AUTHORIZATION = ROOT / 'PILOT_AUTHORIZATION_STATE.json'
UNCHANGED_FIELDS = ('semantic_core_source_hashes', 'config_sha256',
                    'semantic_library_format_version', 'semantic_library_sha256',
                    'availability_manifest_sha256', 'availability_index_sha256',
                    'registry_fingerprint', 'model_fingerprint',
                    'independent_reference_report_sha256')


def build_preparation_snapshot():
    return build_snapshot(scope=PILOT_PREPARATION_SCOPE)


def compare_research_inputs(snapshot, historical_path=SMOKE02_SNAPSHOT):
    historical = json.loads(Path(historical_path).read_text(encoding='utf8'))
    return {key: snapshot.get(key) == historical.get(key) for key in UNCHANGED_FIELDS}


def verify_preparation_snapshot(path=PILOT_SNAPSHOT):
    actual = json.loads(Path(path).read_text(encoding='utf8'))
    expected = build_preparation_snapshot()
    if actual != expected:
        different = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
        raise ValueError('pilot preparation snapshot mismatch: ' + ', '.join(different))
    if not all(compare_research_inputs(actual).values()):
        raise ValueError('pilot preparation differs from SMOKE research inputs')
    return actual


def locked_authorization(snapshot_path=PILOT_SNAPSHOT):
    verify_preparation_snapshot(snapshot_path)
    return {'authorization_version': 1, 'namespace_authorizations': {
        'PILOT': {'allowed': False, 'required_snapshot_sha256': sha256_file(snapshot_path)},
        'CONFIRM': {'allowed': False}}}


def verify_locked_authorization(path=PILOT_AUTHORIZATION, snapshot_path=PILOT_SNAPSHOT):
    actual = json.loads(Path(path).read_text(encoding='utf8'))
    if actual != locked_authorization(snapshot_path):
        raise ValueError('pilot authorization is not locked to this snapshot')
    return actual


def _write_new(path, obj):
    path = Path(path)
    if path.exists():
        raise FileExistsError('refusing to overwrite: ' + str(path))
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('x', encoding='utf8') as f:
        json.dump(obj, f, sort_keys=True, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def write_locked_preparation():
    snap = build_preparation_snapshot()
    checks = compare_research_inputs(snap)
    if not all(checks.values()):
        raise ValueError('historical research input mismatch')
    _write_new(PILOT_SNAPSHOT, snap)
    try:
        _write_new(PILOT_AUTHORIZATION, locked_authorization())
    except Exception:
        # A snapshot without authorization is fail-closed and retained for audit.
        raise
    return checks


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    if args.write:
        print(json.dumps(write_locked_preparation(), sort_keys=True))
    else:
        verify_preparation_snapshot(); verify_locked_authorization()
        print('locked pilot preparation snapshot verified; PILOT and CONFIRM disabled')

if __name__ == '__main__':
    main()

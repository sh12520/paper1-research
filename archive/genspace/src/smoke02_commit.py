"""Fail-closed atomic per-instance persistence primitives for SMOKE-02.

No instance/seed generation or evaluation happens here. Caller supplies a
snapshot verifier that revalidates all source and library fingerprints.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

METHODS = frozenset(('B0','B1','B2','O1'))
NAMESPACE = 'GENSPACE-FAIL-01-SMOKE'


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode('utf8')


def _write_synced(path, data):
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _validate_identity(instance_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', instance_id):
        raise ValueError('unsafe instance ID')


def _snapshot(snapshot_hash, verify_snapshot):
    if verify_snapshot() != snapshot_hash:
        raise ValueError('execution snapshot mismatch')


def _schema(data, instance_id, instance_hash, namespace=NAMESPACE):
    if not isinstance(data, dict) or data.get('instance_id') != instance_id:
        raise ValueError('invalid result identity')
    if data.get('instance_hash') != instance_hash or data.get('namespace') != namespace:
        raise ValueError('invalid result instance hash or namespace')
    rows = data.get('rows')
    if not isinstance(rows, list) or len(rows) != 4 or {r.get('method') for r in rows if isinstance(r,dict)} != METHODS:
        raise ValueError('incomplete method results')
    for row in rows:
        if row.get('instance_hash') != instance_hash or row.get('namespace') != namespace:
            raise ValueError('method identity mismatch')
    _json_bytes(data)  # Reject nonfinite values and non-JSON data.


def inspect_complete(root, instance_id, instance_hash, snapshot_hash, verify_snapshot, validate_instance, *, namespace=NAMESPACE):
    """Return False if absent; raise on any malformed/incompatible existing commit.

    validate_instance must independently validate already serialized instance
    bytes and return (instance_hash, namespace). No regeneration is performed.
    """
    _validate_identity(instance_id)
    _snapshot(snapshot_hash, verify_snapshot)
    final = Path(root)/instance_id
    if not final.exists():
        return False
    if not final.is_dir() or not (final/'COMPLETE.json').is_file():
        raise ValueError('incomplete published directory: quarantine required')
    marker = json.loads((final/'COMPLETE.json').read_text(encoding='utf8'))
    payload = (final/'result.json').read_bytes()
    instance = (final/'instance.json').read_bytes()
    data=json.loads(payload)
    _schema(data, instance_id, instance_hash, namespace)
    expected={'format':2,'instance_id':instance_id,'instance_hash':instance_hash,
              'namespace':namespace,'snapshot_hash':snapshot_hash,'result_sha256':_digest(payload),
              'instance_sha256':_digest(instance),
              'method_sha256':{r['method']:_digest(_json_bytes(r)) for r in data['rows']}}
    if any(marker.get(k)!=v for k,v in expected.items()) or not isinstance(marker.get('completed_at'),(int,float)):
        raise ValueError('COMPLETE marker mismatch')
    actual_hash, actual_namespace = validate_instance(instance)
    if actual_hash != instance_hash or actual_namespace != namespace:
        raise ValueError('serialized instance mismatch')
    _snapshot(snapshot_hash, verify_snapshot)
    return True


def commit_instance(root, instance_id, instance_hash, instance_bytes, result, snapshot_hash,
                    verify_snapshot, validate_instance, *, hook=None, namespace=NAMESPACE):
    """Write, validate, fsync, rename, then atomically publish COMPLETE marker.

    hook is a test-only interruption injection point. Published directories
    without COMPLETE are never considered complete and must be quarantined.
    """
    _validate_identity(instance_id)
    _snapshot(snapshot_hash, verify_snapshot)
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    if (root/instance_id).exists():
        raise FileExistsError('refusing overwrite of committed/incomplete output')
    actual_hash, actual_namespace = validate_instance(instance_bytes)
    if actual_hash != instance_hash or actual_namespace != namespace:
        raise ValueError('serialized instance mismatch')
    _schema(result, instance_id, instance_hash, namespace)
    temp = Path(tempfile.mkdtemp(prefix='.tmp-'+instance_id+'-', dir=root))
    data = _json_bytes(result)
    _write_synced(temp/'instance.json', instance_bytes)
    _write_synced(temp/'result.json', data)
    # Validate exactly the bytes that will be renamed, not only caller objects.
    _schema(json.loads((temp/'result.json').read_bytes()), instance_id, instance_hash, namespace)
    if validate_instance((temp/'instance.json').read_bytes()) != (instance_hash, namespace):
        raise ValueError('serialized instance mismatch after write')
    _snapshot(snapshot_hash, verify_snapshot)
    if hook: hook('before_rename')
    os.rename(temp, root/instance_id)
    final = root/instance_id
    if hook: hook('after_rename')
    _snapshot(snapshot_hash, verify_snapshot)
    marker = {'format':2,'instance_id':instance_id,'instance_hash':instance_hash,
              'namespace':namespace,'snapshot_hash':snapshot_hash,'result_sha256':_digest(data),
              'instance_sha256':_digest(instance_bytes),
              'method_sha256':{r['method']:_digest(_json_bytes(r)) for r in result['rows']},
              'completed_at':time.time()}
    _write_synced(final/'COMPLETE.tmp', _json_bytes(marker))
    if hook: hook('before_marker')
    os.replace(final/'COMPLETE.tmp', final/'COMPLETE.json')
    if hook: hook('after_marker')
    if not inspect_complete(root, instance_id, instance_hash, snapshot_hash, verify_snapshot, validate_instance, namespace=namespace):
        raise ValueError('published commit did not validate')
    return final


def quarantine_incomplete(root, instance_id, snapshot_hash, verify_snapshot):
    """Preserve evidence of interrupted published directory before retrying."""
    _validate_identity(instance_id)
    _snapshot(snapshot_hash, verify_snapshot)
    root=Path(root); final=root/instance_id
    if not final.exists(): return None
    if (final/'COMPLETE.json').exists():
        raise ValueError('cannot quarantine a COMPLETE entry')
    quarantine=root/'.interrupted'; quarantine.mkdir(exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix=instance_id+'-',dir=quarantine))
    destination.rmdir()
    os.rename(final,destination)
    return destination


def streaming_failure_digest(domain, generated, v2, v3, physical, accepted, chunk_size=65536):
    """SHA256 of first-failure bytes without allocating the full layer array.

    The input stage masks must already have been validated as nested. Digest
    byte order and layer codes match the existing observer's first-failure hash.
    """
    import numpy as np
    arrays = tuple(np.asarray(x) for x in (domain, generated, v2, v3, physical, accepted))
    n=len(arrays[0])
    if chunk_size <= 0 or any(a.dtype != np.bool_ or a.ndim != 1 or len(a)!=n for a in arrays):
        raise ValueError('invalid stage masks')
    digest=hashlib.sha256()
    for start in range(0,n,chunk_size):
        stop=min(start+chunk_size,n)
        d,g,b,c,p,a=(x[start:stop] for x in arrays)
        codes=np.zeros(stop-start,dtype=np.uint8)
        codes[d]=1
        codes[g]=3
        codes[g & b]=4
        codes[g & c]=5
        codes[g & p]=6
        codes[g & a]=7
        digest.update(codes.tobytes())
    return digest.hexdigest()


def verify_smoke02_snapshot():
    """Verify live source/config/graph/indices under the dedicated scope."""
    from .execution_snapshot import SMOKE02_SNAPSHOT, verify_snapshot
    verify_snapshot(path=SMOKE02_SNAPSHOT, scope='smoke02')
    return _digest(SMOKE02_SNAPSHOT.read_bytes())

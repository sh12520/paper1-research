"""Optional per-class first-failure artifact for an audited semantic graph.

The caller must supply the *actual generated semantic universe* mask. Graph
classes excluded by capability-dependent generation are not V2 rejections.
This helper never constructs candidates, evaluates utilities, or reads private
data; its output is indexed by the immutable graph's class-ID order.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


CODES = {
    'OUT_OF_DEPTH': 0,
    'NOT_GENERATED': 1,
    'V1_FAILED': 2,
    'V2_FAILED': 3,
    'V3_FAILED': 4,
    'V4_FAILED': 5,
    'V5_FAILED': 6,
    'VERIFIED': 7,
}


def derive_candidate_layers(evaluation, generated_mask):
    """Return a uint8 layer code per graph class; no private values are read.

    The graph has already passed V1, so V1_FAILED is reserved but not emitted.
    `generated_mask` must identify the actual capability-conditioned universe,
    including graph depth restriction. It is deliberately required: treating
    the entire rich graph as generated would misreport sparse V2 failures.
    """
    import numpy as np

    names = ('in_domain', 'v2_pass', 'v3_pass', 'physical_ok', 'accepted')
    arrays = [np.asarray(getattr(evaluation, name)) for name in names]
    if not arrays or arrays[0].ndim != 1:
        raise ValueError('stage masks must be one-dimensional')
    if any(a.shape != arrays[0].shape or a.dtype != np.bool_ for a in arrays):
        raise ValueError('stage masks must be equally sized boolean arrays')
    generated = np.asarray(generated_mask)
    if generated.shape != arrays[0].shape or generated.dtype != np.bool_:
        raise ValueError('generated universe must be an equally sized boolean mask')
    domain, v2, v3, physical, accepted = arrays
    if np.any(generated & ~domain):
        raise ValueError('generated universe extends outside configured depth')
    for earlier, later in zip(arrays, arrays[1:]):
        if np.any(later & ~earlier):
            raise ValueError('validator stage masks are not nested')
    layer = np.full(domain.shape, CODES['OUT_OF_DEPTH'], dtype=np.uint8)
    layer[domain] = CODES['NOT_GENERATED']
    layer[generated] = CODES['V2_FAILED']
    layer[generated & v2] = CODES['V3_FAILED']
    layer[generated & v3] = CODES['V4_FAILED']
    layer[generated & physical] = CODES['V5_FAILED']
    layer[generated & accepted] = CODES['VERIFIED']
    return layer


def write_candidate_layers(path, layers, *, graph_sha256, snapshot_sha256, instance_hash,
                           baseline_layers=None):
    """Write a new compressed per-class artifact with identity metadata.

    Existing files are never overwritten. The caller is responsible for
    verifying these hashes against the graph and execution snapshot.
    """
    import numpy as np

    values = np.asarray(layers)
    if values.ndim != 1 or values.dtype != np.uint8 or np.any(values > CODES['VERIFIED']):
        raise ValueError('invalid first-failure layer array')
    for item in (graph_sha256, snapshot_sha256, instance_hash):
        if not isinstance(item, str) or not re.fullmatch(r'[0-9a-f]{64}', item):
            raise ValueError('artifact identifiers must be lowercase SHA256 digests')
    metadata = {'format': 'GENSPACE-CLASS-LAYERS-v1', 'class_order': 'audited_graph',
                'instance_id': Path(path).stem,
                'graph_sha256': graph_sha256, 'snapshot_sha256': snapshot_sha256,
                'instance_hash': instance_hash, 'codes': CODES,
                'v1_note': 'all graph records passed V1; code reserved'}
    if baseline_layers is not None:
        if not isinstance(baseline_layers, dict) or set(baseline_layers) != {'B0', 'B1', 'B2'}:
            raise ValueError('baseline layers must contain exactly B0, B1, B2')
        allowed = {'V1', 'V2', 'V3', 'V4', 'V5', 'VERIFIED'}
        for records in baseline_layers.values():
            if not isinstance(records, list):
                raise ValueError('baseline records must be lists')
            seen = set()
            for record in records:
                if (not isinstance(record, dict)
                        or set(record) != {'candidate', 'first_failure_layer', 'reason'}
                        or not isinstance(record['candidate'], str)
                        or not record['candidate']
                        or record['candidate'] in seen
                        or record['first_failure_layer'] not in allowed
                        or not isinstance(record['reason'], str)):
                    raise ValueError('invalid or duplicate baseline candidate record')
                seen.add(record['candidate'])
        metadata['baseline_candidate_layers'] = baseline_layers
    with Path(path).open('xb') as stream:
        np.savez_compressed(stream, layers=values,
                            metadata_json=np.array(json.dumps(metadata, sort_keys=True)))

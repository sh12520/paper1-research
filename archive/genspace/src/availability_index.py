"""Fail-closed, preloaded capability-conditioned semantic witness indices."""
from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .execution_snapshot import CORE_FILES, GRAPH, ROOT, sha256_file
from .fingerprints import fingerprint
from .engineering_depth2 import render_token

MANIFEST = ROOT / 'results' / 'engineering' / 'availability_indices' / 'manifest.json'
PATTERNS = frozenset(range(16, 32)) | {0}
COUNT = 1_394_064


@dataclass(frozen=True)
class AvailabilityIndex:
    header: dict
    tokens: object
    generated: object
    depth1: object
    depth1_witness: dict

    def mask(self, depth):
        if depth == 1:
            return self.depth1
        if depth == 2:
            return self.generated
        raise ValueError('unsupported composition depth')

    def witness(self, index, depth):
        if index < 0 or index >= COUNT or not self.mask(depth)[index]:
            raise ValueError('class not generated for this pattern/depth')
        if depth == 1:
            return self.depth1_witness[index]
        return render_token(self.tokens[index].tobytes(), self.header)

    def tie_key(self, index, depth):
        if depth == 1:
            return self.depth1_witness[index]
        return self.tokens[index].tobytes()


class AvailabilityBundle:
    def __init__(self, entries, manifest_sha256):
        self.entries = entries
        self.manifest_sha256 = manifest_sha256

    @staticmethod
    def pattern(evaluator):
        roles = dict(zip(evaluator.reference.roles, evaluator.reference.available))
        groups = (('observe_motion_state', 'apply_conditional_policy'),
                  ('apply_phased_policy',), ('schedule_start',),
                  ('enable_edge_offload', 'reserve_edge_compute'),
                  ('set_validity_interval',))
        pattern = sum((1 << i) for i, group in enumerate(groups)
                      if all(roles.get(role, False) for role in group))
        if pattern not in PATTERNS:
            raise ValueError('unsupported capability availability pattern')
        return pattern

    def for_evaluator(self, evaluator):
        return self.entries[self.pattern(evaluator)]

    @classmethod
    def load(cls, snapshot):
        expected_manifest = snapshot.get('availability_manifest_sha256')
        manifest_sha = sha256_file(MANIFEST)
        if not expected_manifest or manifest_sha != expected_manifest:
            raise ValueError('availability manifest differs from execution snapshot')
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if manifest.get('format') != 'GENSPACE-AVAILABILITY-MANIFEST-v1':
            raise ValueError('unsupported availability manifest')
        graph_sha = sha256_file(GRAPH)
        if graph_sha != manifest.get('rich_graph_sha256') or graph_sha != snapshot['semantic_library_sha256']:
            raise ValueError('availability index graph mismatch')
        old = manifest['source_fingerprint']
        current = fingerprint()
        # Runner/reporting integration is intentionally allowed to change after
        # index construction; all code that constructs its semantics is not.
        build_inputs = (*CORE_FILES, 'src/engineering_depth2.py', 'src/fingerprints.py',
                        'tools/build_availability_index.py')
        from .core_authorization_compat import core_source_matches
        if any(not core_source_matches(p,old['sources'].get(p),current['sources'].get(p),ROOT) for p in build_inputs):
            raise ValueError('availability index semantic builder changed')
        if old['config_hash'] != current['config_hash'] or old['dependency_hash'] != current['dependency_hash']:
            raise ValueError('availability index config or Python environment differs')
        by_pattern = {entry['pattern']: entry for entry in manifest['patterns']}
        if set(by_pattern) != PATTERNS or len(manifest['patterns']) != len(PATTERNS):
            raise ValueError('availability manifest is incomplete or duplicated')
        entries = {}
        for pattern in sorted(PATTERNS):
            item = by_pattern[pattern]
            path = MANIFEST.parent / f'availability_{pattern:02d}.bin.gz'
            if item['class_set_mismatches'] != 0 or sha256_file(path) != item['sha256']:
                raise ValueError('availability index checksum or set check failed')
            with gzip.open(path, 'rb') as stream:
                if stream.read(4) != b'GSA1':
                    raise ValueError('invalid availability index magic')
                raw = stream.read(4)
                if len(raw) != 4:
                    raise ValueError('truncated availability header')
                length = struct.unpack('>I', raw)[0]
                if length > 100_000_000:
                    raise ValueError('invalid availability header length')
                header = json.loads(stream.read(length))
                payload = stream.read()
            if (header.get('format') != 'GENSPACE-AVAILABILITY-v1'
                    or header.get('pattern') != pattern
                    or header.get('record_count') != COUNT
                    or header.get('rich_graph_sha256') != graph_sha
                    or header.get('source_hash') != old['source_hash']
                    or header.get('config_hash') != old['config_hash']
                    or len(payload) != COUNT * 7):
                raise ValueError('availability index header or length mismatch')
            tokens = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 7)
            generated = tokens[:, 0] != 255
            witnesses = dict(header['depth1_witness'])
            if (len(witnesses) != item['depth1_count']
                    or int(np.count_nonzero(generated)) != item['semantic_count']
                    or header['present_count'] != item['semantic_count']):
                raise ValueError('availability index count mismatch')
            depth1 = np.zeros(COUNT, dtype=bool)
            ids = np.fromiter(witnesses, dtype=np.int64)
            if np.any(ids < 0) or np.any(ids >= COUNT) or np.any(~generated[ids]):
                raise ValueError('invalid depth-one availability index')
            depth1[ids] = True
            generated.flags.writeable = False
            depth1.flags.writeable = False
            entries[pattern] = AvailabilityIndex(header, tokens, generated, depth1, witnesses)
        return cls(entries, manifest_sha)

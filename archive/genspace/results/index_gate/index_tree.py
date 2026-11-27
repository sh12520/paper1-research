"""Build and load frozen public feature/bounding indices for INDEX-GATE-01."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import sys
from time import perf_counter

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_PATH = HERE / 'index'
METHOD = ROOT / 'results' / 'method_dev_v1'
sys.path[:0] = [str(ROOT), str(METHOD)]

import numpy as np

from public_search import PublicView, group_bits
from src.execution_snapshot import GRAPH, sha256_file
from src.fast_exact import FastLibrary
from src.instances import load_model_config
from src.registry import default_registry
from tools.smoke_01 import process_memory

INDEX_VERSION = 'INDEX-GATE-01-public-tree-v1'
LEAF_SIZE = 32
PROFILE_COUNT = 27
IDLE = 2 * PROFILE_COUNT
RICH_BIT = np.uint32(1 << 31)
SHARED_FIELDS = ('cell_code', 'demand_basis', 'quality', 'cost', 'active_mask', 'offload_mask', 'group_bits',
                 'group_count', 'required_role_masks', 'depth', 'available1', 'available2', 'static_ids')
TREE_FIELDS = ('order', 'roots', 'lo', 'hi', 'min_cost', 'max_quality', 'min_groups', 'min_id',
               'start', 'stop', 'left', 'right', 'any1', 'any2', 'all1', 'all2', 'depth_min', 'depth_max',
               'depth1_counts', 'role_any', 'role_all')
VARIANTS = ('contract', 'generic')


@dataclass(frozen=True)
class PublicBasis:
    horizon: int
    states: tuple
    profiles: tuple
    resource_parameters: tuple
    role_costs: tuple

    @classmethod
    def frozen(cls):
        model = load_model_config()['model_draft']
        domain = model['scalar_domains']['b2']
        profiles = tuple(product(domain['quality'], domain['deadline'], domain['rate']))
        role_costs = tuple(sorted((name, float(cap.execution_cost),
                                  tuple(sorted((k, float(v)) for k, v in cap.resource_cost.items())))
                                 for name, cap in default_registry().items()))
        resource_parameters = tuple(sorted((name, float(value)) for name, value in model['demand'].items()))
        return cls(3, ('still', 'moving'), profiles, resource_parameters, role_costs)

    def validate_view(self, view):
        observed = PublicBasis(view.horizon, view.states, view.profiles, view.resource_parameters, view.role_costs)
        if observed != self:
            raise ValueError('query profile, time/state, public cost, or demand basis differs from the frozen index')
        if view.depth not in (1, 2):
            raise ValueError('index supports audited depth 1 or 2')


def role_score_basis(basis):
    """Match FastLibrary.bind_public_basis + FLAT _proxy role-cost expression."""
    execution = np.zeros(4096, dtype=np.float64)
    resource = np.zeros((4096, 3), dtype=np.float64)
    roles = [(cost, dict(costs)) for _, cost, costs in basis.role_costs]
    for mask in range(4096):
        selected = [item for i, item in enumerate(roles) if mask & (1 << i)]
        execution[mask] = sum(cost for cost, _ in selected)
        resource[mask] = [sum(costs.get(k, 0.0) for _, costs in selected) for k in ('RAN', 'FH', 'EDGE')]
    return execution + resource.sum(axis=1)


def demand_score_basis(basis):
    p = dict(basis.resource_parameters)
    profiles = np.asarray(basis.profiles, dtype=np.float64)
    q, rate = profiles[:, 0], profiles[:, 2]
    if len(q) != PROFILE_COUNT:
        raise ValueError('expected the frozen 27-profile domain')
    demand = np.zeros((IDLE + 1, 3), dtype=np.float64)
    demand[:PROFILE_COUNT, 0] = q * 1.0
    demand[:PROFILE_COUNT, 1] = rate * p['fh_rate_factor'] * 1.0
    demand[PROFILE_COUNT:IDLE, 0] = q * p['offload_ran_factor']
    demand[PROFILE_COUNT:IDLE, 1] = rate * p['fh_rate_factor'] * p['offload_fh_factor']
    demand[PROFILE_COUNT:IDLE, 2] = q * p['offload_edge_factor']
    return demand


def extract(library, basis):
    """Fixed class data derived without reading serialized PILOT instances."""
    n = len(library.keys)
    active = library.active
    offload = active & (library.level == 1)
    if np.any(active & (library.profiles >= PROFILE_COUNT)) or np.any(active & (library.level > 1)):
        raise ValueError('unknown active profile or offload level in graph')
    cell_code = np.where(active, library.profiles + PROFILE_COUNT * offload, IDLE).astype(np.uint8)
    active_mask = np.zeros(n, dtype=np.uint8)
    offload_mask = np.zeros(n, dtype=np.uint8)
    quality = np.zeros(n, dtype=np.float64)
    cost = np.zeros(n, dtype=np.float64)
    role_cost = role_score_basis(basis)
    q = np.asarray([row[0] for row in basis.profiles], dtype=np.float64)
    for j in range(6):
        active_mask |= active[:, j].astype(np.uint8) << j
        offload_mask |= offload[:, j].astype(np.uint8) << j
        quality += np.where(active[:, j], q[np.where(active[:, j], library.profiles[:, j], 0)], 0.0)
        cost += np.where(active[:, j], role_cost[library.role_masks[:, j]], 0.0)
    quality /= 6.0
    cost /= 6.0

    bits = group_bits(library)
    group_count = np.asarray([k.bit_count() for k in range(16)], dtype=np.uint8)[bits]
    eligible = (group_count > 0) & (group_count <= 2)
    available1 = np.zeros(n, dtype=np.uint32)
    available2 = np.zeros(n, dtype=np.uint32)
    counts = {}
    for pattern, variant in sorted(library.availability.entries.items()):
        bit = np.uint32(1 << pattern)
        available1[variant.mask(1)] |= bit
        available2[variant.mask(2)] |= bit
        counts[str(pattern)] = [int(np.count_nonzero(eligible & variant.mask(d))) for d in (1, 2)]
    static_ids = np.flatnonzero(bits == 0).astype(np.uint32)
    depth = np.where((available1 & RICH_BIT) != 0, 1, 2).astype(np.uint8)
    depth[static_ids] = 0
    if len(static_ids) != 27 or np.any((available1 & ~available2) != 0):
        raise ValueError('inconsistent rich class depth or availability')

    features = {'cell_code': cell_code, 'demand_basis': demand_score_basis(basis), 'quality': quality,
                'cost': cost, 'active_mask': active_mask, 'offload_mask': offload_mask, 'group_bits': bits,
                'group_count': group_count, 'required_role_masks': library.required_role_masks,
                'depth': depth, 'available1': available1, 'available2': available2, 'static_ids': static_ids}
    return features, np.flatnonzero(eligible).astype(np.uint32), counts


class TreeBuilder:
    """Deterministic binary median tree with exact summary reductions."""

    def __init__(self, features, leaf_size):
        self.features = features
        self.leaf_size = leaf_size
        # Build-only dense matrix. Serialized complete records use compact codes.
        self.demand = features['demand_basis'][features['cell_code']].reshape(-1, 18)
        self.axis_scale = np.ptp(features['demand_basis'], axis=0)
        self.axis_scale = np.tile(np.where(self.axis_scale > 0.0, self.axis_scale, 1.0), 6)

    def make(self, class_ids, variant):
        f = self.features
        if variant == 'contract':
            # Exact masks at both depths group classes with the same derivability
            # even when a semantic class admits multiple syntactic witnesses.
            keys = tuple(f[name][class_ids] for name in ('group_bits', 'offload_mask', 'active_mask',
                                                        'available1', 'available2'))
            permutation = np.lexsort(keys)
            order = class_ids[permutation]
            ordered_keys = [key[permutation] for key in keys]
            changes = np.zeros(len(order) - 1, dtype=bool)
            for key in ordered_keys:
                changes |= key[:-1] != key[1:]
            root_boundaries = np.r_[0, np.flatnonzero(changes) + 1, len(order)]
        else:
            order = class_ids.copy()
            root_boundaries = np.asarray([0, len(order)])

        # A floor-median split keeps each non-root leaf at least half full.
        capacity = 4 * len(order) // self.leaf_size + 2 * len(root_boundaries) + 1
        tree = {name: np.empty(capacity, dtype=dtype) for name, dtype in {
            'min_cost': 'f8', 'max_quality': 'f8', 'min_groups': 'u1', 'min_id': 'u4',
            'start': 'u4', 'stop': 'u4', 'left': 'i4', 'right': 'i4',
            'any1': 'u4', 'any2': 'u4', 'all1': 'u4', 'all2': 'u4',
            'depth_min': 'u1', 'depth_max': 'u1', 'depth1_counts': 'u4',
            'role_any': 'u2', 'role_all': 'u2',
        }.items()}
        tree['lo'] = np.empty((capacity, 6, 3), dtype=np.float64)
        tree['hi'] = np.empty((capacity, 6, 3), dtype=np.float64)
        used = 0

        def fill(start, stop):
            nonlocal used
            node = used
            used += 1
            tree['start'][node], tree['stop'][node] = start, stop
            ids = order[start:stop]
            demands = self.demand[ids]
            lo, hi = demands.min(axis=0), demands.max(axis=0)
            tree['lo'][node], tree['hi'][node] = lo.reshape(6, 3), hi.reshape(6, 3)
            del demands
            if len(ids) > self.leaf_size:
                split_axis = int(np.argmax((hi - lo) / self.axis_scale))
                middle = len(ids) // 2
                if hi[split_axis] != lo[split_axis]:
                    partition = np.argpartition(self.demand[ids, split_axis], middle)
                    ids[:] = ids[partition]
                # If all demand vectors tie the current input order suffices.
                left, right = fill(start, start + middle), fill(start + middle, stop)
                tree['left'][node], tree['right'][node] = left, right
                for field, aggregate in (
                    ('min_cost', min), ('max_quality', max), ('min_groups', min), ('min_id', min),
                    ('any1', np.bitwise_or), ('any2', np.bitwise_or), ('all1', np.bitwise_and),
                    ('all2', np.bitwise_and), ('role_any', np.bitwise_or), ('role_all', np.bitwise_and),
                    ('depth_min', min), ('depth_max', max), ('depth1_counts', np.add),
                ):
                    tree[field][node] = aggregate(tree[field][left], tree[field][right])
            else:
                tree['left'][node] = tree['right'][node] = -1
                tree['min_cost'][node] = f['cost'][ids].min()
                tree['max_quality'][node] = f['quality'][ids].max()
                tree['min_groups'][node] = f['group_count'][ids].min()
                tree['min_id'][node] = ids.min()
                roles = f['required_role_masks'][ids]
                tree['role_any'][node] = np.bitwise_or.reduce(roles)
                tree['role_all'][node] = np.bitwise_and.reduce(roles)
                for d in (1, 2):
                    availability = f[f'available{d}'][ids]
                    tree[f'any{d}'][node] = np.bitwise_or.reduce(availability)
                    tree[f'all{d}'][node] = np.bitwise_and.reduce(availability)
                depth = f['depth'][ids]
                tree['depth_min'][node] = depth.min()
                tree['depth_max'][node] = depth.max()
                tree['depth1_counts'][node] = np.count_nonzero(depth == 1)
            return node

        roots = np.fromiter((fill(int(a), int(b)) for a, b in zip(root_boundaries[:-1], root_boundaries[1:])),
                            dtype=np.uint32, count=len(root_boundaries) - 1)
        data = {name: array[:used] for name, array in tree.items()}
        return dict(data, roots=roots, order=order)


def save_arrays(directory, arrays):
    directory.mkdir()
    files = {}
    for field, array in arrays.items():
        path = directory / (field + '.npy')
        np.save(path, array, allow_pickle=False)
        files[field] = {'sha256': sha256_file(path), 'bytes': path.stat().st_size}
    return files


def read_arrays(directory, files, fields):
    if set(files) != set(fields):
        raise ValueError(f'index schema differs for {directory.name}')
    data = {}
    for field in fields:
        path = directory / (field + '.npy')
        if path.stat().st_size != files[field]['bytes'] or sha256_file(path) != files[field]['sha256']:
            raise ValueError(f'index checksum differs: {path.name}')
        # Load once into process memory to separate cold index I/O and queries.
        array = np.load(path, allow_pickle=False)
        array.flags.writeable = False
        data[field] = array
    return data


def source_hashes(library):
    return {'graph': library.snapshot['semantic_library_sha256'],
            'availability': library.availability.manifest_sha256,
            'model_config': sha256_file(ROOT / 'config.yaml'),
            'registry': sha256_file(ROOT / 'src' / 'registry.py'),
            'flat_public_search': sha256_file(METHOD / 'public_search.py'),
            'builder': sha256_file(Path(__file__))}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf8')


class BoundingTree:
    def __init__(self, arrays):
        self.__dict__.update(arrays)


class Index:
    def __init__(self, features, trees, counts, basis, metadata, load_s):
        self.__dict__.update(features)
        self.basis = basis
        self.counts = counts
        self.trees = trees
        self.contract = trees['contract']
        self.generic = trees['generic']
        self.manifest = metadata
        self.load_s = load_s

    @classmethod
    def load(cls, path=DEFAULT_PATH, *, library):
        started = perf_counter()
        path = Path(path)
        metadata = json.loads((path / 'manifest.json').read_text(encoding='utf8'))
        if (metadata['version'] != INDEX_VERSION or metadata['source_sha256'] != source_hashes(library)
                or metadata['class_count'] != len(library.keys)):
            raise ValueError('index and public graph basis fingerprints differ')
        timings = {}
        phase = perf_counter()
        features = read_arrays(path / 'shared', metadata['features'], SHARED_FIELDS)
        timings['shared_features_load_s'] = perf_counter() - phase
        trees = {}
        for name in VARIANTS:
            phase = perf_counter()
            trees[name] = BoundingTree(read_arrays(path / name, metadata['tree_arrays'][name], TREE_FIELDS))
            timings[name + '_tree_load_s'] = perf_counter() - phase
        result = cls(features, trees, metadata['counts'], PublicBasis.frozen(), metadata, perf_counter() - started)
        result.load_timings = timings
        return result

    def validate_view(self, view):
        if not isinstance(view, PublicView):
            raise TypeError('index requires a sanitized FLAT PublicView')
        self.basis.validate_view(view)

    def conditioned_count(self, pattern, depth):
        if depth not in (1, 2):
            raise ValueError('index supports audited depth 1 or 2')
        return self.counts[str(pattern)][depth - 1]


def build(path, library, leaf_size):
    path = Path(path)
    path.mkdir(exist_ok=False)
    total_started = perf_counter()
    features, eligible, counts = extract(library, PublicBasis.frozen())
    shared_feature_s = perf_counter() - total_started
    shared_files = save_arrays(path / 'shared', features)
    builder = TreeBuilder(features, leaf_size)
    trees = {}
    tree_files = {}
    for variant in VARIANTS:
        started = perf_counter()
        tree = builder.make(eligible, variant)
        elapsed = perf_counter() - started
        tree_files[variant] = save_arrays(path / variant, tree)
        trees[variant] = {'build_s': elapsed, 'serialized_bytes': sum(x['bytes'] for x in tree_files[variant].values()),
                          'nodes': len(tree['start']), 'leaves': int(np.count_nonzero(tree['left'] < 0)),
                          'roots': len(tree['roots'])}
        del tree
    del builder
    metadata = {'version': INDEX_VERSION, 'source_sha256': source_hashes(library), 'class_count': len(library.keys),
                'leaf_size': leaf_size, 'counts': counts, 'features': shared_files, 'tree_arrays': tree_files}
    write_json(path / 'manifest.json', metadata)
    payload_bytes = sum(f.stat().st_size for f in path.rglob('*.npy')) + (path / 'manifest.json').stat().st_size
    graph_bytes = GRAPH.stat().st_size
    result = {'version': INDEX_VERSION, 'graph_bytes': graph_bytes,
              'shared_bytes': sum(x['bytes'] for x in shared_files.values()),
              'index_bytes_total': payload_bytes, 'graph_plus_index_bytes': graph_bytes + payload_bytes,
              'peak_build_working_set_bytes': process_memory(os.getpid())[1],
              'shared_features_s': shared_feature_s, 'index_build_s': perf_counter() - total_started,
              'graph_and_availability_load': library.load_timings, 'trees': trees}
    write_json(path / 'build_metrics.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('build', 'load'))
    parser.add_argument('--path', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--leaf-size', type=int, default=LEAF_SIZE)
    args = parser.parse_args()
    if args.leaf_size < 2:
        parser.error('--leaf-size must be at least 2')
    library = FastLibrary.from_graph(scope='pilot-execution')
    if args.operation == 'build':
        result = build(args.path, library, args.leaf_size)
    else:
        index = Index.load(args.path, library=library)
        result = {'index_load_s': index.load_s, 'process_peak_working_set_bytes': process_memory(os.getpid())[1],
                  'graph_and_availability_load': library.load_timings, 'index_load_breakdown': index.load_timings}
        write_json(args.path / 'load_metrics.json', result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

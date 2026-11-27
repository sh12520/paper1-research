"""Verify stored class coverage, availability partitions and bounds exhaustively."""

import json
from pathlib import Path

import numpy as np


INDEX = Path(__file__).resolve().parent / 'index'
RICH_BIT = np.uint32(1 << 31)


def arrays(folder):
    return {p.stem: np.load(p, mmap_mode='r', allow_pickle=False) for p in sorted((INDEX / folder).glob('*.npy'))}


def equal(left, right, message):
    if not np.array_equal(left, right):
        raise ValueError(message)


def audit_tree(name, features, eligible, counts):
    tree = arrays(name)
    order = tree['order']
    n = len(tree['left'])
    roots = tree['roots']
    internal = np.flatnonzero(tree['left'] >= 0)
    leaves = np.flatnonzero(tree['left'] < 0)
    left, right = tree['left'][internal], tree['right'][internal]
    start, stop = tree['start'], tree['stop']
    leaf_starts = start[leaves]
    equal(np.sort(order), eligible, 'wrong structural candidate coverage')
    equal(np.bincount(np.r_[roots, left, right], minlength=n), np.ones(n), 'node ownership is not unique')
    if not ((left > internal).all() and (right > internal).all() and (stop > start).all()):
        raise ValueError('invalid child ordering or empty range')
    equal(start[left], start[internal], 'left child coverage')
    equal(stop[right], stop[internal], 'right child coverage')
    equal(stop[left], start[right], 'gap or overlap between child ranges')
    equal(leaf_starts, np.r_[0, stop[leaves[:-1]]], 'leaf ranges do not tile the candidate array')
    if stop[leaves[-1]] != len(order):
        raise ValueError('last leaf does not finish the candidate array')

    for field, source, reduction, combine in (
        ('min_cost', 'cost', np.minimum, np.minimum),
        ('max_quality', 'quality', np.maximum, np.maximum),
        ('min_groups', 'group_count', np.minimum, np.minimum),
        ('min_id', None, np.minimum, np.minimum),
        ('any1', 'available1', np.bitwise_or, np.bitwise_or),
        ('any2', 'available2', np.bitwise_or, np.bitwise_or),
        ('all1', 'available1', np.bitwise_and, np.bitwise_and),
        ('all2', 'available2', np.bitwise_and, np.bitwise_and),
        ('depth_min', 'depth', np.minimum, np.minimum),
        ('depth_max', 'depth', np.maximum, np.maximum),
        ('depth1_counts', 'depth', np.add, np.add),
        ('role_any', 'required_role_masks', np.bitwise_or, np.bitwise_or),
        ('role_all', 'required_role_masks', np.bitwise_and, np.bitwise_and),
    ):
        values = order if source is None else features[source][order]
        if field == 'depth1_counts':
            values = (values == 1).astype(np.uint32)
        equal(tree[field][leaves], reduction.reduceat(values, leaf_starts), f'{field}: leaf bound differs')
        equal(tree[field][internal], combine(tree[field][left], tree[field][right]), f'{field}: internal bound differs')

    for cell in range(6):
        points = features['demand_basis'][features['cell_code'][order, cell]]
        for field, reduction in (('lo', np.minimum), ('hi', np.maximum)):
            equal(tree[field][leaves, cell], reduction.reduceat(points, leaf_starts, axis=0), f'{field}: leaf cell bound differs')
            equal(tree[field][internal, cell], reduction(tree[field][left, cell], tree[field][right, cell]),
                  f'{field}: internal cell bound differs')

    if name == 'contract':
        for feature in ('available1', 'available2', 'active_mask', 'offload_mask', 'group_bits'):
            values = features[feature][order]
            equal(np.minimum.reduceat(values, start[roots]), np.maximum.reduceat(values, start[roots]),
                  f'contract partition mixes {feature}')
        for pattern, expected in counts.items():
            bit = np.uint32(1 << int(pattern))
            for depth in (1, 2):
                selected = (tree[f'all{depth}'][roots] & bit) != 0
                if np.sum(stop[roots[selected]] - start[roots[selected]]) != expected[depth - 1]:
                    raise ValueError(f'contract partition count differs at {(pattern, depth)}')

    return {'nodes_checked': n, 'leaves_checked': len(leaves), 'root_partitions': len(roots),
            'unique_classes': len(order), 'summary_checks': 'PASS'}


def main():
    manifest = json.loads((INDEX / 'manifest.json').read_text(encoding='utf8'))
    features = arrays('shared')
    eligible = np.flatnonzero((features['group_count'] > 0) & (features['group_count'] <= 2)).astype(np.uint32)
    equal(features['static_ids'], np.flatnonzero(features['group_bits'] == 0), 'wrong B2 class set')
    for pattern, expected in manifest['counts'].items():
        bit = np.uint32(1 << int(pattern))
        count = [int(np.count_nonzero(features[f'available{d}'][eligible] & bit)) for d in (1, 2)]
        equal(count, expected, 'conditioned count differs')
    results = {name: audit_tree(name, features, eligible, manifest['counts']) for name in ('contract', 'generic')}
    report = json.dumps(results, indent=2) + '\n'
    (INDEX.parent / 'tree_structure_audit.json').write_text(report, encoding='utf8')
    print(report, end='')


if __name__ == '__main__':
    main()

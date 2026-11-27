"""Compare FAST and packed reference over all classes, ENGINEERING only.

The tolerance was fixed in DIFFERENTIAL_VALIDATION_SPEC.md before running.
This tool does not generate research namespaces or inspect scientific results.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import struct
import time
from pathlib import Path

from src.engineering_depth2 import PackedEvaluator, read_graph
from src.fast_exact import FastEvaluator, FastLibrary
from src.instances import generate_instance
from src.models import Static
from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.enumeration import syntax_key
from src.registry import default_registry
from src.state_machine import semantic_key, verify_instance
from src.execution_snapshot import SNAPSHOT, sha256_file, verify_snapshot

TOLERANCE = 1e-12
NAMESPACE = 'GENSPACE-FAIL-01-ENGINEERING'


def independent_label_bits(key):
    """Independent compact-guard classifier; never inspects witness syntax."""
    cells = [bytes(key[25 + 4*i:29 + 4*i]) for i in range(6)]
    active = [cell[0] != 255 for cell in cells]
    static = all(active) and len(set(cells)) == 1 and cells[0][1] == 0
    conditional = any(cells[2*t] != cells[2*t + 1] for t in range(3))
    delayed = any(not active[s] and (active[s+2] or active[s+4]) for s in range(2))
    phased = any(active[j] and active[j-2] and cells[j] != cells[j-2]
                 for s in range(2) for j in (s+2, s+4))
    offload = any(active[i] and cells[i][1] == 1 for i in range(6))
    hybrid = sum((conditional, delayed, phased, offload)) >= 2
    return (int(static) | (int(conditional) << 1) | (int(delayed) << 2)
            | (int(phased) << 3) | (int(offload) << 4) | (int(hybrid) << 5))


def fixtures(depth=2):
    rows = (
        ('F1', 'low', 'rich', 'medium'),
        ('F2', 'medium', 'sparse', 'high'),
        ('F3', 'high', 'rich', 'medium'),
        ('F4', 'low', 'sparse', 'high'),
    )
    for family, pressure, richness, conflict in rows:
        config = {'resource_pressure': pressure, 'capability_richness': richness,
                  'preference_conflict': conflict, 'composition_depth': depth}
        yield generate_instance(family, config, 'full-differential-' + family,
                                namespace=NAMESPACE)


def graph_index(library, key):
    """Find key in the graph's strictly sorted byte order without AST scans."""
    lo, hi = 0, len(library.keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if library.keys[mid].tobytes() < key:
            lo = mid + 1
        else:
            hi = mid
    if lo == len(library.keys) or library.keys[lo].tobytes() != key:
        raise ValueError('reference key missing from graph')
    return lo


def syntax_depth(tree):
    if tree[0] == 'Static':
        return 0
    if tree[0] in ('If', 'Sequence'):
        return 1 + max(syntax_depth(tree[2]), syntax_depth(tree[3]))
    return 1 + syntax_depth(tree[2])


def compare_depth1(instance, library):
    """Compare all 1,539 depth-one classes directly to AST interpretation."""
    if instance.namespace != NAMESPACE or instance.public.configuration['composition_depth'] != 1:
        raise ValueError('depth-one ENGINEERING fixture required')
    public = instance.public
    encoder = CompactEncoder(public)
    domain = Domain(public.b2_profiles, public.conditions, public.durations,
                    public.offsets, public.intervals, public.offload_levels)
    expected = {}
    # Enumerate the rich syntactic superset; actual instance capability
    # availability is checked independently at V2 for each candidate.
    for node in enumerate_compositions(domain, 1, default_registry()):
        key = encoder.encode(node)
        if key not in expected or syntax_key(node) < syntax_key(expected[key]):
            expected[key] = node
    if len(expected) != 1539:
        raise ValueError('unexpected full depth-one semantic count')
    evaluator = FastEvaluator(instance, library)
    variant = library.availability.for_evaluator(evaluator)
    fast = evaluator.evaluate()
    roles = {role for role, available in zip(evaluator.reference.roles, evaluator.reference.available)
             if available}
    conditioned = {}
    for node in enumerate_compositions(domain, 1, roles):
        key = encoder.encode(node)
        if key not in conditioned or syntax_key(node) < syntax_key(conditioned[key]):
            conditioned[key] = node
    b2 = {encoder.encode(Static(p)) for p in public.b2_profiles}
    counts = {name: 0 for name in ('domain', 'generated', 'v2', 'v3', 'physical', 'application_utility',
              'network_utility', 'nash', 'acceptance', 'novelty', 'mechanism', 'witness',
              'nonfinite', 'not_applicable')}
    examples = []
    reference_winner = reference_welfare = reference_witness = None
    v5_count = 0
    maxima = {'application_utility': 0., 'network_utility': 0., 'nash': 0.}
    bit_identical = {'application_utility': 0, 'network_utility': 0, 'nash': 0}

    def mismatch(name, index):
        counts[name] += 1
        if len(examples) < 20:
            examples.append({'kind': name, 'class_id': index})

    if int(fast.in_domain.sum()) != len(expected):
        counts['domain'] += 1
    for key, node in expected.items():
        i = graph_index(library, key)
        result = verify_instance(node, instance, 1)
        if not bool(fast.in_domain[i]):
            mismatch('domain', i)
        v2 = result.failed_layer not in ('V1', 'V2')
        v3 = result.failed_layer not in ('V1', 'V2', 'V3')
        physical = result.failed_layer in (None, 'V5')
        if v2 != bool(fast.v2_pass[i]): mismatch('v2', i)
        if v3 != bool(fast.v3_pass[i]): mismatch('v3', i)
        if physical != bool(fast.physical_ok[i]): mismatch('physical', i)
        if result.verified != bool(fast.accepted[i]): mismatch('acceptance', i)
        if (key not in b2) != bool(library.structural[i]): mismatch('novelty', i)
        if independent_label_bits(key) != int(library.mechanism_bits[i]): mismatch('mechanism', i)
        generated = key in conditioned
        if generated != bool(variant.mask(1)[i]):
            mismatch('generated', i)
        if generated:
            witness = library.witness(i, depth=1, evaluator=evaluator)
            if witness != syntax_key(conditioned[key]) or syntax_depth(json.loads(witness)) > 1:
                mismatch('witness', i)
        if not physical:
            if not all(math.isnan(float(v[i])) for v in
                       (fast.application_utility, fast.network_utility, fast.nash)):
                mismatch('not_applicable', i)
            continue
        v5_count += 1
        app, network = result.application_utility, result.network_utility
        product = app * network
        for name, left, right in (
            ('application_utility', app, float(fast.application_utility[i])),
            ('network_utility', network, float(fast.network_utility[i])),
            ('nash', product, float(fast.nash[i])),
        ):
            if not math.isfinite(left) or not math.isfinite(right):
                mismatch('nonfinite', i)
                continue
            delta = abs(left-right)
            maxima[name] = max(maxima[name], delta)
            if delta > TOLERANCE:
                mismatch(name, i)
            if struct.pack('>d', left) == struct.pack('>d', right):
                bit_identical[name] += 1
        if generated and result.verified and (reference_welfare is None or product >= reference_welfare):
            expected_witness = syntax_key(conditioned[key])
            if (reference_welfare is None or product > reference_welfare
                    or expected_witness < reference_witness):
                reference_winner, reference_welfare, reference_witness = i, product, expected_witness
    fast_witness = (None if fast.winner is None else
                    library.witness(fast.winner, depth=1, evaluator=evaluator))
    return {'family': public.family, 'configuration': public.configuration,
            'instance_hash': instance.instance_hash, 'candidate_count': len(conditioned),
            'rich_depth1_classes_checked': len(expected),
            'conditioned_witness_validation': True,
            'reference_v5_reached_count': v5_count, 'mismatches': counts,
            'mismatch_examples': examples, 'maximum_absolute_differences': maxima,
            'bit_identical_counts': bit_identical,
            'winner_class_equal': reference_winner == fast.winner,
            'winner_witness_equal': reference_witness == fast_witness,
            'same_representative': reference_winner == fast.winner and reference_witness == fast_witness,
            'fast_stage_timings': fast.timings}


def compare_fixture(instance, header, records, library):
    if instance.namespace != NAMESPACE:
        raise ValueError('only ENGINEERING instances are permitted')
    ref = PackedEvaluator(instance)
    evaluator = FastEvaluator(instance, library)
    variant = library.availability.for_evaluator(evaluator)
    fast = evaluator.evaluate()
    b2 = {CompactEncoder(instance.public).encode(Static(p)) for p in instance.public.b2_profiles}
    counts = {name: 0 for name in ('domain', 'generated', 'v2', 'v3', 'public', 'physical', 'application_utility',
              'network_utility', 'nash', 'acceptance', 'novelty', 'mechanism', 'nonfinite',
              'not_applicable')}
    bit_identical = {'application_utility': 0, 'network_utility': 0, 'nash': 0}
    maxima = {'application_utility': 0., 'network_utility': 0., 'nash': 0.}
    examples = []
    reaches_v5 = 0
    reference_welfare = None
    max_nash_ties = []
    structural_roles = {'observe_motion_state', 'apply_conditional_policy', 'apply_phased_policy',
                        'schedule_start', 'set_validity_interval', 'enable_edge_offload',
                        'reserve_edge_compute'}
    missing_structural = sum(1 << i for i, role in enumerate(ref.roles)
                             if role in structural_roles and not ref.available[i])
    # Full comparison includes the selected classes; this fixed hash-derived
    # sample records additional audit coverage without using study seeds.
    sampled_ids = {int.from_bytes(hashlib.sha256(
        ('GENSPACE-ENGINEERING-SEMANTIC-SAMPLE-' + str(i)).encode()).digest()[:8],
        'big') % len(records) for i in range(1024)}
    sampled_ids.update((0, len(records) - 1))
    sample_checked = 0
    sample_labels = set()
    sample_active_counts = set()
    minimum_reservation_gap = {'application': None, 'network': None}
    started = time.perf_counter()

    def mismatch(name, index):
        counts[name] += 1
        if len(examples) < 20:
            examples.append({'kind': name, 'class_id': index})

    for i, (key, token) in enumerate(records):
        # This direct equality prevents comparing differently ordered IDs.
        if key != library.keys[i].tobytes():
            raise ValueError('graph class ordering or contents differ')
        if key[0] != 1:
            raise ValueError('graph contains a non-V3-valid class')
        if i in sampled_ids:
            sample_checked += 1
            sample_labels.add(independent_label_bits(key))
            sample_active_counts.add(sum(key[25 + 4*j] != 255 for j in range(6)))
        public_ok = ref.public_filter(key)
        # All records are within the fixed depth-two class domain and the
        # graph's V3-valid bit is set; V2 is therefore the only public reject.
        if not bool(fast.in_domain[i]):
            mismatch('domain', i)
        reference_generated = (int(library.required_role_masks[i]) & missing_structural) == 0
        if reference_generated != bool(variant.generated[i]):
            mismatch('generated', i)
        if public_ok != bool(fast.v2_pass[i]):
            mismatch('v2', i)
        if public_ok != bool(fast.v3_pass[i]):
            mismatch('v3', i)
        if public_ok != bool(fast.public_ok[i]):
            mismatch('public', i)
        physical = ref.physical(key) if public_ok else None
        physical_ok = physical is not None
        if physical_ok != bool(fast.physical_ok[i]):
            mismatch('physical', i)
        if (key not in b2) != bool(library.structural[i]):
            mismatch('novelty', i)
        if independent_label_bits(key) != int(library.mechanism_bits[i]):
            mismatch('mechanism', i)
        if not physical_ok:
            if bool(fast.accepted[i]):
                mismatch('acceptance', i)
            if not all(math.isnan(float(v[i])) for v in
                       (fast.application_utility, fast.network_utility, fast.nash)):
                mismatch('not_applicable', i)
            continue
        reaches_v5 += 1
        accepted, app, network = ref.acceptance(physical)
        for name, value, reservation in (
            ('application', app, instance.private.application['reservation']),
            ('network', network, instance.private.network['reservation']),
        ):
            gap = abs(value - reservation)
            previous = minimum_reservation_gap[name]
            minimum_reservation_gap[name] = gap if previous is None else min(previous, gap)
        product = app * network
        if accepted != bool(fast.accepted[i]):
            mismatch('acceptance', i)
        for name, expected, actual in (
            ('application_utility', app, float(fast.application_utility[i])),
            ('network_utility', network, float(fast.network_utility[i])),
            ('nash', product, float(fast.nash[i])),
        ):
            if not math.isfinite(expected) or not math.isfinite(actual):
                mismatch('nonfinite', i)
                continue
            delta = abs(expected - actual)
            maxima[name] = max(maxima[name], delta)
            if delta > TOLERANCE:
                mismatch(name, i)
            if struct.pack('>d', expected) == struct.pack('>d', actual):
                bit_identical[name] += 1
        if reference_generated and accepted:
            if reference_welfare is None or product > reference_welfare:
                reference_welfare = product
                max_nash_ties = [i]
            elif product == reference_welfare:
                max_nash_ties.append(i)

    fast_winner = fast.winner
    winner_in_optimal_set = (fast_winner is None if reference_welfare is None
                             else fast_winner in max_nash_ties)
    return {
        'family': instance.public.family,
        'configuration': instance.public.configuration,
        'instance_hash': instance.instance_hash,
        'candidate_count': len(records),
        'reference_v5_reached_count': reaches_v5,
        'mismatches': counts,
        'mismatch_examples': examples,
        'maximum_absolute_differences': maxima,
        'bit_identical_counts': bit_identical,
        'winner_in_optimal_set': winner_in_optimal_set,
        'optimal_tie_class_ids': max_nash_ties,
        'conditioned_witness_validation': False,
        'same_representative': None,
        'sample_coverage': {
            'hash_namespace': 'GENSPACE-ENGINEERING-SEMANTIC-SAMPLE',
            'selected_unique_classes': len(sampled_ids),
            'checked_classes': sample_checked,
            'label_bit_patterns': sorted(sample_labels),
            'active_cell_counts': sorted(sample_active_counts),
        },
        'minimum_reservation_gap_among_v4_feasible': minimum_reservation_gap,
        'compare_wall_seconds': time.perf_counter() - started,
        'fast_stage_timings': fast.timings,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph', default='results/engineering/semantic_library.graph.gz')
    parser.add_argument('--output', default='results/engineering/fast_reference_diff.json')
    parser.add_argument('--depth1-only', action='store_true')
    args = parser.parse_args()
    path = Path(args.graph)
    snapshot_start = verify_snapshot(graph=path)
    snapshot_file_sha = sha256_file(SNAPSHOT)
    graph_sha = sha256_file(path)
    header, records = read_graph(path)
    if len(records) != 1_394_064:
        raise ValueError('complete graph required; refusing partial comparison')
    library = FastLibrary.from_graph(path)
    results = []
    partial_path = Path(args.output).with_suffix('.partial.json')
    for instance in fixtures(depth=1 if args.depth1_only else 2):
        row = (compare_depth1(instance, library) if args.depth1_only
               else compare_fixture(instance, header, records, library))
        if (verify_snapshot(graph=path) != snapshot_start
                or sha256_file(SNAPSHOT) != snapshot_file_sha
                or sha256_file(path) != graph_sha):
            raise ValueError('snapshot or graph changed during differential')
        results.append(row)
        partial_path.write_text(json.dumps({
            'namespace': NAMESPACE,
            'complete': False,
            'candidate_count': 1539 if args.depth1_only else len(records),
            'tolerance_absolute': TOLERANCE,
            'execution_snapshot_sha256': snapshot_file_sha,
            'execution_snapshot': snapshot_start,
            'graph_sha256': graph_sha,
            'results': results,
        }, indent=2), encoding='utf-8')
        print('completed', row['family'], 'mismatches', row['mismatches'], flush=True)
    result = {
        'namespace': NAMESPACE,
        'candidate_count': 1539 if args.depth1_only else len(records),
        'tolerance_absolute': TOLERANCE,
        'graph_sha256': graph_sha,
        'execution_snapshot_sha256': snapshot_file_sha,
        'execution_snapshot': snapshot_start,
        'snapshot_verified_at_start_and_after_each_fixture': True,
        'comparison_basis': ('FAST vs direct AST reference, entire depth-one semantic set' if args.depth1_only
                             else 'FAST vs packed reference; packed path has reduced-domain AST differential evidence'),
        'results': results,
        # Depth-two conditioned lexical equality requires the separate
        # independent syntactic scan; the packed graph cannot validate itself.
        'all_matched': (args.depth1_only and all(not any(x['mismatches'].values()) and x['same_representative'] for x in results)),
    }
    if (verify_snapshot(graph=path) != snapshot_start
            or sha256_file(SNAPSHOT) != snapshot_file_sha
            or sha256_file(path) != graph_sha):
        raise ValueError('snapshot or graph changed before final report')
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()

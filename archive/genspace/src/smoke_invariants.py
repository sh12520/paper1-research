"""SMOKE-01 implementation invariants; not research hypothesis tests.

The observer consumes a single already-generated instance and the exact FAST
arrays from the same paired execution. It never generates a seed, changes a
preference, computes rates, performs bootstrap, or evaluates Gates A–E.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from types import SimpleNamespace

from .engine import BASE
from .instances import registry_from_public
from .registry import default_registry
from .state_machine import _signature, bind_capabilities

SMOKE_NAMESPACE = 'GENSPACE-FAIL-01-SMOKE'
SHADOW_NAMESPACE = 'GENSPACE-FAIL-01-ENGINEERING-SHADOW'
PILOT_NAMESPACE = 'GENSPACE-FAIL-01-PILOT'
METHODS = ('B0', 'B1', 'B2', 'O1')
NEGATIVE_REMOVED = ('apply_conditional_policy', 'apply_phased_policy',
                    'schedule_start', 'set_validity_interval', 'enable_edge_offload')


def expected_instance_ids():
    """The preregistered 192 IDs; this operation does not derive any seed."""
    return tuple(f'{f}__{pressure}__{conflict}__{rich}__d{depth}__s{seed}'
                 for f, pressure, conflict, rich, depth, seed in itertools.product(
                     ('F1', 'F2', 'F3', 'F4'), ('low', 'medium', 'high'),
                     ('medium', 'high'), ('sparse', 'rich'), (1, 2), (0, 1)))


def _key_index(keys, key):
    lo, hi = 0, len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid].tobytes() < key:
            lo = mid + 1
        else:
            hi = mid
    if lo == len(keys) or keys[lo].tobytes() != key:
        raise ValueError('independent B2 static signature missing from graph')
    return lo


def independent_b2_mask(public, library):
    """Reconstruct every static *packed key* directly, with no AST creation.

    The graph format is fixed by the audited snapshot: V3 flag, two bytes per
    canonical role, then six (profile, level, role-mask) guarded cells.
    Predicate truth is derived from public constraints and profile membership.
    This is independent of the precomputed `library.structural` mask and the
    pattern-zero index that are being checked.
    """
    import numpy as np
    roles = tuple(sorted(default_registry()))
    if len(roles) != 12 or public.horizon != 3 or tuple(public.states) != ('still', 'moving'):
        raise ValueError('unsupported B2 reconstruction basis')
    registry = registry_from_public(public)
    bits = sum(1 << i for i, role in enumerate(roles) if role in BASE)
    b2 = np.zeros(len(library.keys), dtype=bool)
    ids = []
    for i, profile in enumerate(public.b2_profiles):
        header = bytearray([1])
        for role in roles:
            if role not in BASE:
                header.extend((255, 0))
                continue
            predicates = []
            for predicate in sorted(registry[role].preconditions):
                if predicate in ('quality_supported', 'deadline_supported', 'rate_supported'):
                    predicates.append(profile in public.b2_profiles)
                elif predicate in ('ran_reservation_supported', 'fh_reservation_supported'):
                    predicates.append(bool(public.public_constraints.get('reservation_supported', False)))
                else:
                    raise ValueError('unknown static capability predicate')
            mask = sum(1 << j for j, truth in enumerate(predicates) if truth)
            header.extend((1, mask))  # 'static' scope bit
        cell = bytes((i, 0, bits >> 8, bits & 255))
        key = bytes(header) + cell * 6
        index = _key_index(library.keys, key)
        ids.append(index)
        b2[index] = True
    if len(ids) != len(set(ids)) or len(ids) != len(public.b2_profiles):
        raise ValueError('duplicate B2 packed static signatures')
    return b2


def _negative_available(public, registry):
    """Apply the preregistered five-role removal, including equivalent providers."""
    if any(cid not in registry for cid in public.capabilities):
        raise ValueError('available capability missing from public registry')
    signatures = {_signature(registry[role]) for role in NEGATIVE_REMOVED}
    kept = tuple(cid for cid in public.capabilities
                 if cid in registry and _signature(registry[cid]) not in signatures)
    if not all(bind_capabilities({role}, kept, registry) for role in BASE):
        raise ValueError('negative control would remove a static capability')
    availability = [bool(bind_capabilities({role}, kept, registry))
                    for role in sorted(default_registry())]
    return kept, availability


def check_instance(instance, library, evaluator, evaluation, variant):
    """Check all public/verification invariants for one paired SMOKE instance.

    Runs inside the FAST evaluation observer. It derives B2 independently,
    checks the per-instance no-structural negative control, and recomputes
    V2 and public hard/physical conditions for every claimed verified class.
    A failure returns `ok=False`; callers must stop or record SMOKE_FAIL.
    """
    import numpy as np
    public = instance.public
    if instance.namespace not in (SMOKE_NAMESPACE, SHADOW_NAMESPACE, PILOT_NAMESPACE):
        raise ValueError('invariant observer requires SMOKE or ENGINEERING-SHADOW namespace')
    depth = public.configuration['composition_depth']
    registry = registry_from_public(public)
    roles = tuple(sorted(default_registry()))
    checks = {}
    details = {}
    m0, mr, b2_profiles = map(set, (public.m0_profiles, public.mr_profiles, public.b2_profiles))
    checks['m0_subset_mr_subset_b2'] = m0 <= mr <= b2_profiles
    scalar = independent_b2_mask(public, library)
    generated = variant.mask(depth)
    details['generated_semantic_class_count'] = int(np.count_nonzero(generated))
    checks['b2_subset_mc'] = bool(np.all(~scalar | generated))
    checks['b2_matches_library_static_mask'] = bool(np.array_equal(scalar, ~library.structural))
    kept, neg_available = _negative_available(public, registry)
    neg_ref = SimpleNamespace(roles=roles, available=neg_available)
    neg_pattern = library.availability.pattern(SimpleNamespace(reference=neg_ref))
    neg_mask = library.availability.entries[neg_pattern].mask(depth)
    checks['negative_control_pattern_zero'] = neg_pattern == 0
    checks['negative_control_o1_equals_b2'] = bool(np.array_equal(neg_mask, scalar))
    details['negative_control_removed_capability_count'] = len(public.capabilities) - len(kept)

    masks = [np.asarray(getattr(evaluation, name)) for name in
             ('in_domain', 'v2_pass', 'v3_pass', 'physical_ok', 'accepted')]
    if any(x.dtype != np.bool_ or x.ndim != 1 or len(x) != len(library.keys) for x in masks):
        raise ValueError('evaluation mask schema mismatch')
    domain, v2, v3, physical, accepted = masks
    details['rich_graph_in_domain_count'] = int(np.count_nonzero(domain))
    checks['stage_masks_nested'] = all(not bool(np.any(later & ~earlier))
                                       for earlier, later in zip(masks, masks[1:]))
    checks['verified_only_generated'] = not bool(np.any(accepted & ~generated))
    checks['generated_only_in_domain'] = not bool(np.any(generated & ~domain))
    # Independent byte-level expectation for optional NPZ artifacts.  This is
    # derived directly from the observed stage masks and actual generated set,
    # not from the stage-report writer or from aggregate rejection totals.
    from .smoke02_commit import streaming_failure_digest
    details['first_failure_layer_sha256'] = streaming_failure_digest(domain, generated, v2, v3, physical, accepted)
    feasible = np.flatnonzero(physical)
    utility_ok = True
    for name in ('application_utility', 'network_utility', 'nash'):
        value = np.asarray(getattr(evaluation, name))
        if value.shape != domain.shape:
            raise ValueError('utility array schema mismatch')
        v = value[feasible]
        utility_ok &= bool(np.all(np.isfinite(v) & (v >= 0) & (v <= 1)))
    checks['reached_v5_utility_finite_unit_interval'] = utility_ok

    # Independent V2 + V3 + V4 checks on *every* class marked accepted.
    verified = np.flatnonzero(accepted & generated)
    invalid = np.zeros(len(verified), dtype=bool)
    compatible = {role: bool(bind_capabilities({role}, public.capabilities, registry))
                  and _signature(registry[role]) == _signature(default_registry()[role])
                  for role in roles}
    scopes = ('static', 'conditional', 'phased', 'delayed', 'validity', 'offload')
    for j, role in enumerate(roles):
        scope = library.keys[verified, 1 + 2*j]
        pred = library.keys[verified, 2 + 2*j]
        supported = sum(1 << i for i, name in enumerate(scopes) if name in registry[role].supported_scope)
        expected_pred = (1 << len(registry[role].preconditions)) - 1
        invalid |= ((scope != 255) & ((not compatible[role]) | ((scope & (~supported & 255)) != 0)
                                    | (pred != expected_pred)))
    invalid |= library.keys[verified, 0] != 1
    capacities = {(t, s): (ran, fh, edge) for t, s, ran, fh, edge in public.capacity}
    expected_cells = {(t, s) for t in range(public.horizon) for s in public.states}
    checks['all_capacity_cells_finite_nonnegative'] = (
        len(public.capacity) == len(expected_cells) and set(capacities) == expected_cells
        and all(math.isfinite(v) and v >= 0 for row in public.capacity for v in row[2:]))
    if not checks['all_capacity_cells_finite_nonnegative']:
        invalid[:] = True
    else:
        q = np.array([p.quality for p in public.b2_profiles])
        d = np.array([p.deadline for p in public.b2_profiles])
        rate = np.array([p.rate for p in public.b2_profiles])
        surcharge = np.zeros((1 << len(roles), 3))
        for mask in range(len(surcharge)):
            for j, role in enumerate(roles):
                if mask & (1 << j):
                    for k, resource in enumerate(('RAN', 'FH', 'EDGE')):
                        surcharge[mask, k] += registry[role].resource_cost.get(resource, 0.)
        edge_bit = 1 << roles.index('reserve_edge_compute')
        offload_bit = 1 << roles.index('enable_edge_offload')
        base_bits = sum(1 << roles.index(role) for role in BASE)
        counts = np.zeros(len(verified), dtype=np.uint8)
        params, hard = public.resource_parameters, public.public_constraints
        for cell in range(6):
            active = library.active[verified, cell]
            counts += active
            profile = library.profiles[verified, cell]
            level = library.level[verified, cell]
            masks_for_cell = library.role_masks[verified, cell]
            invalid |= active & ((profile >= len(q)) | (level > 1))
            safe_profile = np.where(active & (profile < len(q)), profile, 0)
            safe_mask = np.where(masks_for_cell < len(surcharge), masks_for_cell, 0)
            invalid |= active & (masks_for_cell >= len(surcharge))
            invalid |= active & ((masks_for_cell & ~library.required_role_masks[verified]) != 0)
            invalid |= active & ((masks_for_cell & base_bits) != base_bits)
            invalid |= active & (level == 1) & (((masks_for_cell & edge_bit) == 0)
                                               | ((masks_for_cell & offload_bit) == 0))
            off = level == 1
            ran = q[safe_profile] * np.where(off, params['offload_ran_factor'], 1.) + surcharge[safe_mask, 0]
            fh = (rate[safe_profile] * params['fh_rate_factor']) * np.where(off, params['offload_fh_factor'], 1.) + surcharge[safe_mask, 1]
            edge = np.where(off, q[safe_profile] * params['offload_edge_factor'], 0.) + surcharge[safe_mask, 2]
            capacity = capacities[(cell // 2, public.states[cell % 2])]
            for load, limit in zip((ran, fh, edge), capacity):
                invalid |= active & (~np.isfinite(load) | (load < 0) | (load > limit))
            invalid |= active & (q[safe_profile] < hard['min_quality'])
            invalid |= active & ((q[safe_profile] < 0) | (q[safe_profile] > 1)
                                 | (d[safe_profile] <= 0) | (rate[safe_profile] <= 0))
            invalid |= active & (d[safe_profile] > hard['max_deadline'])
            invalid |= active & (edge != 0) & ((masks_for_cell & edge_bit) == 0)
        invalid |= counts < hard['min_active_slots']
    details['invalid_verified_count'] = int(np.count_nonzero(invalid))
    checks['no_invalid_class_verified'] = details['invalid_verified_count'] == 0
    return {'ok': all(checks.values()), 'checks': checks, 'counts': details}


def _finite_json(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite_json(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite_json(v) for v in value)
    return True


def check_rows(rows, instances, expected_ids=None, validations=None, *, namespace=SMOKE_NAMESPACE):
    """Validate coverage, paired identities and result schemas without rates."""
    if namespace not in (SMOKE_NAMESPACE, SHADOW_NAMESPACE, PILOT_NAMESPACE):
        raise ValueError('unsupported namespace for invariant validation')
    expected = set(expected_instance_ids() if expected_ids is None else expected_ids)
    grouped = {}
    malformed_row = False
    for row in rows:
        if not isinstance(row, dict):
            malformed_row = True
            continue
        grouped.setdefault(row.get('instance_id'), []).append(row)
    checks = {'exact_instance_coverage': set(grouped) == expected and set(instances) == expected,
              'four_distinct_methods': True, 'paired_instance_hashes': True,
              'complete_output_schema': True, 'output_finite': True,
              'reported_utilities_unit_interval': True, 'aggregate_counts_consistent': True,
              'per_instance_checks_all_pass': validations is not None and set(validations) == expected,
              'o1_generated_count_matches': validations is not None and set(validations) == expected}
    if malformed_row:
        checks['complete_output_schema'] = False
    required = {'instance_id', 'seed_index', 'method', 'agreement', 'candidate_count',
                'validator_rejections', 'verified_count', 'representative', 'application_utility',
                'network_utility', 'nash_welfare', 'compiled_actions', 'runtime_seconds',
                'instance_hash', 'public_hash', 'private_hash', 'family', 'configuration',
                'namespace', 'seed_label', 'structurally_novel', 'mechanism_labels',
                'capability_count', 'ast_depth'}
    for iid, group in grouped.items():
        if iid not in instances:
            checks['paired_instance_hashes'] = False
            continue
        inst = instances[iid]
        validation = None if validations is None else validations.get(iid)
        if validation is None or validation.get('ok') is not True:
            checks['per_instance_checks_all_pass'] = False
        if len(group) != 4 or {r.get('method') for r in group} != set(METHODS):
            checks['four_distinct_methods'] = False
        for row in group:
            if not required <= set(row):
                checks['complete_output_schema'] = False
                continue
            if (inst.namespace != namespace or row['namespace'] != namespace
                    or row['instance_hash'] != inst.instance_hash or row['public_hash'] != inst.public_hash
                    or row['private_hash'] != inst.private_hash or row['family'] != inst.public.family
                    or row['configuration'] != inst.public.configuration):
                checks['paired_instance_hashes'] = False
            cfg = inst.public.configuration
            seed = row['seed_index']
            if (type(seed) is not int or seed not in (range(20) if namespace == PILOT_NAMESPACE else (0, 1))
                    or str(seed) != str(inst.seed_label)
                    or row['seed_label'] != inst.seed_label
                    or iid != f"{inst.public.family}__{cfg['resource_pressure']}__{cfg['preference_conflict']}__{cfg['capability_richness']}__d{cfg['composition_depth']}__s{seed}"):
                checks['paired_instance_hashes'] = False
            checks['output_finite'] &= _finite_json(row)
            agreement = row['agreement']
            if (type(agreement) is not bool or type(row['runtime_seconds']) not in (int, float)
                    or not math.isfinite(row['runtime_seconds']) or row['runtime_seconds'] < 0):
                checks['complete_output_schema'] = False
            numbers = [row[x] for x in ('application_utility', 'network_utility', 'nash_welfare')]
            if agreement:
                if (any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in numbers)
                        or not row['representative'] or not row['compiled_actions']):
                    checks['reported_utilities_unit_interval'] = False
                elif (not isinstance(row['compiled_actions'], list)
                      or any(not isinstance(step, dict)
                             or set(step) != {'time', 'state', 'operation', 'arguments', 'before', 'after'}
                             for step in row['compiled_actions'])):
                    checks['complete_output_schema'] = False
            elif any(v is not None for v in numbers) or row['representative'] is not None or row['compiled_actions'] is not None:
                checks['complete_output_schema'] = False
            rejection = row['validator_rejections']
            if (type(row['candidate_count']) is not int or type(row['verified_count']) is not int
                    or row['candidate_count'] < 0 or row['verified_count'] < 0
                    or not isinstance(rejection, dict)
                    or any(type(v) is not int or v < 0 for v in rejection.values())
                    or row['candidate_count'] != row['verified_count'] + sum(rejection.values())):
                checks['aggregate_counts_consistent'] = False
            if (type(agreement) is bool and type(row['verified_count']) is int
                    and agreement != (row['verified_count'] > 0)):
                checks['aggregate_counts_consistent'] = False
            if row['method'] in ('B0', 'B1', 'B2'):
                domain = {'B0': inst.public.m0_profiles, 'B1': inst.public.mr_profiles,
                          'B2': inst.public.b2_profiles}[row['method']]
                if row['candidate_count'] != len(set(domain)):
                    checks['aggregate_counts_consistent'] = False
            elif row['method'] == 'O1':
                counts = {} if validation is None else validation.get('counts', {})
                if (row['candidate_count'] != counts.get('generated_semantic_class_count')
                        or row.get('rich_graph_in_domain_count') != counts.get('rich_graph_in_domain_count')):
                    checks['o1_generated_count_matches'] = False
    return {'ok': all(checks.values()), 'checks': checks,
            'expected_instance_count': len(expected), 'observed_instance_count': len(grouped),
            'observed_method_row_count': len(rows)}


def check_execution_status(completed_ids, exceptions, skip_events, expected_ids=None):
    """Require explicit crash/skip evidence and exactly-once completion."""
    expected = set(expected_instance_ids() if expected_ids is None else expected_ids)
    provided = completed_ids is not None and exceptions is not None and skip_events is not None
    completed = [] if completed_ids is None else list(completed_ids)
    checks = {
        'completion_evidence_present': provided,
        'every_instance_completed_once': set(completed) == expected and len(completed) == len(expected),
        'no_crash_or_exception': exceptions is not None and len(exceptions) == 0,
        'no_explicit_or_silent_skip': skip_events is not None and len(skip_events) == 0
                                      and set(completed) == expected and len(completed) == len(expected),
    }
    return {'ok': all(checks.values()), 'checks': checks,
            'expected_instance_count': len(expected), 'completed_instance_count': len(completed)}


def check_repeats(primary, repeats, expected_ids):
    """Compare all non-timing result fields, including full actions and hashes."""
    expected = set(expected_ids)
    checks = {'exact_repeat_subset': set(repeats) == expected and expected <= set(primary),
              'non_timing_fields_identical': True}
    for iid in expected & set(primary) & set(repeats):
        def canonical(rows):
            return json.dumps([{k: v for k, v in row.items() if k != 'runtime_seconds'}
                               for row in rows], sort_keys=True, separators=(',', ':'), allow_nan=False)
        try:
            equal = canonical(primary[iid]) == canonical(repeats[iid])
        except (TypeError, ValueError, AttributeError):
            equal = False
        if not equal:
            checks['non_timing_fields_identical'] = False
    return {'ok': all(checks.values()), 'checks': checks,
            'expected_repeat_count': len(expected), 'observed_repeat_count': len(repeats)}


def check_snapshot_unchanged(start_sha, end_sha):
    import re
    valid = all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{64}', x)
                for x in (start_sha, end_sha))
    return {'ok': bool(valid and start_sha == end_sha),
            'checks': {'snapshot_hash_valid_and_unchanged': bool(valid and start_sha == end_sha)}}

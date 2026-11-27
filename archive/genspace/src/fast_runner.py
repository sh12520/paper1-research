"""ENGINEERING-only paired runner over a verified compact semantic library.

This entry point uses the same deserialized instance for every method.  It does
not build or enumerate O1 ASTs; a single selected witness is rendered after
selection.  Research namespaces remain blocked until a subsequent gate.
"""
from __future__ import annotations

import json
import struct
from dataclasses import asdict
from time import perf_counter

from .enumeration import candidates, syntax_key
from .instances import deserialize_instance
from .state_machine import verify_instance
from .engine import required_capabilities
from .models import Profile, Static, If, Sequence, Delay, ValidFor, Offload
from .state_machine import normalize

_LABELS = ('STATIC', 'STATE_CONDITIONAL', 'DELAYED_START',
           'TEMPORAL_PHASED', 'OFFLOAD', 'HYBRID')


def _depth(tree):
    if tree[0] == 'Static':
        return 0
    if tree[0] in ('If', 'Sequence'):
        return 1 + max(_depth(tree[2]), _depth(tree[3]))
    return 1 + _depth(tree[2])


def _decode_witness(tree):
    """Decode the single selected, subsequently verified graph witness."""
    op = tree[0]
    if op == 'Static' and len(tree) == 4:
        return Static(Profile(*tree[1:]))
    if op == 'If' and len(tree) == 4:
        return If(tree[1], _decode_witness(tree[2]), _decode_witness(tree[3]))
    if op == 'Sequence' and len(tree) == 4:
        return Sequence(tree[1], _decode_witness(tree[2]), _decode_witness(tree[3]))
    if op == 'Delay' and len(tree) == 3:
        return Delay(tree[1], _decode_witness(tree[2]))
    if op == 'ValidFor' and len(tree) == 3:
        return ValidFor(tuple(tree[1]), _decode_witness(tree[2]))
    if op == 'Offload' and len(tree) == 3:
        return Offload(tree[1], _decode_witness(tree[2]))
    raise ValueError('invalid selected witness encoding')


def _same_float(a, b):
    return struct.pack('>d', float(a)) == struct.pack('>d', float(b))


def _encode_selected(node, public, compatibility):
    """Pack the one selected AST without constructing a dummy Static AST."""
    from .compact_semantics import CompactEncoder, SCOPES
    from .instances import registry_from_public
    from .state_machine import semantic_key
    encoder = object.__new__(CompactEncoder)
    encoder.public = public
    encoder.roles = compatibility.roles
    encoder.role_index = compatibility.role_index
    encoder.reg = registry_from_public(public)
    encoder.profiles = {(p.quality, p.deadline, p.rate): i
                        for i, p in enumerate(public.b2_profiles)}
    encoder.scope_bits = {scope: 1 << i for i, scope in enumerate(SCOPES)}
    return encoder.pack(semantic_key(node, public))


def run_paired_fast(serialized_instance, library, candidate_layers_path=None, evaluation_observer=None, phase_observer=None):
    """Return rows plus stage timings; require a snapshot-verified library."""
    envelope = json.loads(serialized_instance)
    if not isinstance(envelope, dict) or envelope.get('namespace') not in ('GENSPACE-FAIL-01-ENGINEERING', 'GENSPACE-FAIL-01-ENGINEERING-SHADOW', 'GENSPACE-FAIL-01-SMOKE', 'GENSPACE-FAIL-01-PILOT'):
        raise RuntimeError('namespace not enabled')
    if envelope['namespace'] in ('GENSPACE-FAIL-01-SMOKE','GENSPACE-FAIL-01-PILOT'):
        from .smoke_authorization import authorize
        authorize(envelope['namespace'])
    from .fast_exact import FastEvaluator
    import numpy as np

    def event(name):
        if phase_observer is not None:
            phase_observer(name)
    event('INSTANCE_START')
    all_start = perf_counter()
    t = perf_counter()
    instance = deserialize_instance(serialized_instance)
    evaluator = FastEvaluator(instance, library)
    stages = {'instance_deserialize_init_s': perf_counter() - t}
    p = instance.public
    depth = p.configuration['composition_depth']
    rows = []
    baseline_layers = {}
    for method in ('B0', 'B1', 'B2'):
        t = perf_counter()
        seen, rejection, best = set(), {}, None
        verified_count = 0
        layer_records = []
        for node in candidates(method, p, depth):
            key = syntax_key(node)
            if key in seen:
                continue
            seen.add(key)
            result = verify_instance(node, instance, depth)
            if candidate_layers_path is not None:
                layer_records.append({'candidate': key,
                                      'first_failure_layer': result.failed_layer or 'VERIFIED',
                                      'reason': result.reason})
            if not result.verified:
                rejection[result.failed_layer] = rejection.get(result.failed_layer, 0) + 1
                continue
            verified_count += 1
            rank = (-result.application_utility * result.network_utility, key)
            if best is None or rank < best[0]:
                best = (rank, node, result)
        row = {'method': method, 'agreement': best is not None,
               'candidate_count': len(seen), 'validator_rejections': rejection,
               'candidate_count_unit': 'semantic_classes',
               'verified_count': verified_count, 'any_verified_structural': False,
               'representative': None, 'application_utility': None,
               'network_utility': None, 'nash_welfare': None,
               'structurally_novel': None, 'mechanism_labels': (),
               'capability_count': None, 'ast_depth': None, 'compiled_actions': None}
        if best is not None:
            rank, node, result = best
            row.update(representative=rank[1], application_utility=result.application_utility,
                       network_utility=result.network_utility, nash_welfare=-rank[0],
                       structurally_novel=False, mechanism_labels=('STATIC',), ast_depth=0,
                       capability_count=len(required_capabilities(normalize(node, p))),
                       compiled_actions=[asdict(step) for step in result.compiled_actions])
        stages[method + '_s'] = perf_counter() - t
        row['runtime_seconds'] = stages[method + '_s']
        rows.append(row)
        if candidate_layers_path is not None:
            baseline_layers[method] = layer_records

    t = perf_counter()
    result = evaluator.evaluate(phase_observer=phase_observer)
    stages.update(result.timings)
    variant = library.availability.for_evaluator(evaluator)
    if evaluation_observer is not None:
        for value in vars(result).values():
            if isinstance(value, np.ndarray):
                value.flags.writeable = False
        evaluation_observer(instance, library, evaluator, result, variant)
    generated = variant.mask(depth)
    if np.any(generated & ~result.in_domain):
        raise ValueError('conditioned universe extends beyond graph depth')
    accepted = generated & result.accepted
    winner = result.winner
    if winner is not None and not accepted[winner]:
        raise ValueError('selected class is outside the conditioned accepted set')
    row = {'method': 'O1', 'agreement': winner is not None,
           'candidate_count': int(np.count_nonzero(generated)),
           'candidate_count_unit': 'semantic_classes',
           'rich_graph_in_domain_count': int(np.count_nonzero(result.in_domain)),
           'not_generated_count': int(np.count_nonzero(result.in_domain & ~generated)),
           'oracle_status': 'DIAGNOSTIC_EXISTENCE_ORACLE',
           'verified_count': int(np.count_nonzero(accepted)),
           'any_verified_structural': bool(np.any(accepted & library.structural)),
           'validator_rejections': {
               'V1': 0,
               'V2': int(np.count_nonzero(generated & ~result.v2_pass)),
               'V3': int(np.count_nonzero(generated & result.v2_pass & ~result.v3_pass)),
               'V4': int(np.count_nonzero(generated & result.v3_pass & ~result.physical_ok)),
               'V5': int(np.count_nonzero(generated & result.physical_ok & ~result.accepted)),
           }, 'representative': None, 'application_utility': None,
           'network_utility': None, 'nash_welfare': None,
           'structurally_novel': None, 'mechanism_labels': (),
           'capability_count': None, 'ast_depth': None, 'compiled_actions': None}
    witness_start = perf_counter()
    if winner is not None:
        i = winner
        witness = library.witness(i, depth, evaluator=evaluator)
        tree = json.loads(witness)
        node = _decode_witness(tree)  # Exactly one selected O1 AST reconstruction.
        if _encode_selected(node, p, evaluator.reference) != library.keys[i].tobytes():
            raise ValueError('selected witness does not match semantic class')
        checked = verify_instance(node, instance, depth)
        if (not checked.verified
                or not _same_float(checked.application_utility, result.application_utility[i])
                or not _same_float(checked.network_utility, result.network_utility[i])
                or not _same_float(checked.application_utility * checked.network_utility, result.nash[i])):
            raise ValueError('selected witness failed benchmark revalidation')
        labels = int(library.mechanism_bits[i])
        row.update(representative=witness,
                   application_utility=float(result.application_utility[i]),
                   network_utility=float(result.network_utility[i]),
                   nash_welfare=float(result.nash[i]),
                   structurally_novel=bool(library.structural[i]),
                   mechanism_labels=tuple(label for k, label in enumerate(_LABELS) if labels & (1 << k)),
                   capability_count=int(library.required_role_masks[i]).bit_count(),
                   ast_depth=_depth(tree),
                   compiled_actions=[asdict(step) for step in checked.compiled_actions])
    stages['selected_witness_validation_s'] = perf_counter() - witness_start
    stages['O1_s'] = perf_counter() - t
    row['runtime_seconds'] = stages['O1_s']
    rows.append(row)
    if candidate_layers_path is not None:
        t = perf_counter()
        from .stage_report import derive_candidate_layers, write_candidate_layers
        from .execution_snapshot import sha256_file
        layers = derive_candidate_layers(result, generated)
        write_candidate_layers(candidate_layers_path, layers,
            graph_sha256=library.snapshot['semantic_library_sha256'],
            snapshot_sha256=sha256_file(library.snapshot_path), instance_hash=instance.instance_hash,
            baseline_layers=baseline_layers)
        stages['candidate_layers_write_s'] = perf_counter() - t
    by_method = {x['method']: x for x in rows}
    b1, o1 = by_method['B1'], by_method['O1']
    for item in rows:
        item.update(instance_hash=instance.instance_hash,
                    public_hash=instance.public_hash,
                    private_hash=instance.private_hash,
                    family=p.family, configuration=p.configuration,
                    namespace=instance.namespace, seed_label=instance.seed_label,
                    b1_deadlock=not b1['agreement'],
                    verified_deadlock_resolved=not b1['agreement'] and o1['agreement'],
                    pareto_improvement_over_b1=None)
    if b1['agreement'] and o1['agreement']:
        a, n = o1['application_utility'], o1['network_utility']
        ba, bn = b1['application_utility'], b1['network_utility']
        o1['pareto_improvement_over_b1'] = a >= ba and n >= bn and (a > ba or n > bn)
    t = perf_counter()
    event('SERIALIZATION_START')
    json.dumps(rows, sort_keys=True, allow_nan=False)
    event('SERIALIZATION_END')
    stages['result_serialization_s'] = perf_counter() - t
    stages['complete_run_paired_s'] = perf_counter() - all_start
    event('FAST_EVALUATION_COMPLETE')
    return rows, stages

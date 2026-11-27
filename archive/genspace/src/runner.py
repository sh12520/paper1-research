"""Experimental paired benchmark runner; never an authorization to run research.

O1 uses the pre-pilot semantic DP, whose full-domain completeness and resource
feasibility have not been established. Do not interpret as final exact results.
"""
from collections import Counter
import json
from dataclasses import asdict, dataclass
from .instances import digest
from time import perf_counter
from .engine import ast_depth, required_capabilities
from .enumeration import METHODS, candidates, syntax_key
from .instances import deserialize_instance
from .models import Static
from .semantic_dp import library
from .state_machine import normalize, semantic_key, verify_instance


def mechanism_labels(signature):
    """Describe observable service patterns, independently of witness syntax."""
    _, valid, cells = signature
    if not valid:
        return ()
    by_time = {}
    by_state = {}
    for t, state, value in cells:
        # The semantic cell also contains active role identities and their
        # resource/execution costs.  A conditional can change those without
        # changing the displayed profile or offload level.
        output = value
        by_time.setdefault(t, []).append(output)
        by_state.setdefault(state, []).append((t, output))
    labels = set()
    if any(len(set(values)) > 1 for values in by_time.values()):
        labels.add('STATE_CONDITIONAL')
    for observations in by_state.values():
        observations.sort()
        if observations and observations[0][1] is None and any(value is not None for _, value in observations[1:]):
            labels.add('DELAYED_START')
        if any(a is not None and b is not None and a != b
               for (_, a), (_, b) in zip(observations, observations[1:])):
            labels.add('TEMPORAL_PHASED')
        if any(value is not None and value[3] != 'none' for _, value in observations):
            labels.add('OFFLOAD')
    all_values = [value for _, _, value in cells]
    if (all_values and all(value is not None for value in all_values)
            and len(set(all_values)) == 1 and all_values[0][3] == 'none'):
        labels.add('STATIC')
    if len(labels) >= 2:
        labels.add('HYBRID')
    return tuple(sorted(labels))



def library_basis_hash(public, depth):
    """Public inputs that determine the draft semantic signature and grammar.

    Capacity and private values affect evaluation but not key construction.
    This is valid only for the current pre-pilot interpreter, not a permanent
    cross-version compatibility guarantee; fingerprint source separately.
    """
    fields = ('horizon', 'states', 'b2_profiles', 'capabilities', 'conditions',
              'durations', 'offsets', 'intervals', 'offload_levels',
              'public_constraints', 'resource_parameters', 'registry', 'model_config_hash')
    obj = asdict(public)
    return digest({'depth': depth, **{name: obj[name] for name in fields}})


@dataclass(frozen=True)
class PreparedLibrary:
    basis_hash: str
    depth: int
    entries: dict


def precompute_library(public, depth):
    return PreparedLibrary(library_basis_hash(public, depth), depth, library(public, depth))


def run_paired(serialized_instance, registry=None, prepared_library=None,
               fast_library=None, include_timings=False, candidate_layers_path=None):
    """Evaluate one serialized instance; O1 output is EXPERIMENTAL ONLY.

    B2 semantic membership uses all public static profiles, independently of
    private acceptance. Candidate count for O1 is semantic classes emitted by
    the experimental DP; it is not the count of raw syntax trees.
    """
    envelope = json.loads(serialized_instance)
    if not isinstance(envelope, dict) or envelope.get('namespace') not in ('GENSPACE-FAIL-01-ENGINEERING', 'GENSPACE-FAIL-01-SMOKE'):
        raise RuntimeError('namespace not enabled')
    if envelope['namespace'] == 'GENSPACE-FAIL-01-SMOKE' and fast_library is None:
        raise RuntimeError('SMOKE requires its snapshot-verified FAST library')
    if fast_library is not None:
        if registry is not None or prepared_library is not None:
            raise ValueError('fast runner takes its verified library and serialized registry only')
        from .fast_runner import run_paired_fast
        rows, timings = run_paired_fast(serialized_instance, fast_library, candidate_layers_path)
        return (rows, timings) if include_timings else rows
    if include_timings:
        raise ValueError('separate stage timings require the fast library')
    if candidate_layers_path is not None:
        raise ValueError('candidate layer artifacts require the fast library')
    instance = deserialize_instance(serialized_instance)
    if instance.namespace != 'GENSPACE-FAIL-01-ENGINEERING':
        raise RuntimeError('Experimental runner is restricted to engineering fixtures; research runs are blocked')
    p = instance.public
    depth = p.configuration['composition_depth']
    if prepared_library is not None and (prepared_library.depth != depth or prepared_library.basis_hash != library_basis_hash(p, depth)):
        raise ValueError('Prepared semantic library does not match public grammar and semantic inputs')
    scalar_semantics = {semantic_key(Static(profile), p) for profile in p.b2_profiles}
    rows = []
    for method in METHODS:
        start = perf_counter()
        if method == 'O1':
            prepared = precompute_library(p, depth) if prepared_library is None else prepared_library
            values = (entry.witness for entry in prepared.entries.values())
        else:
            values = candidates(method, p, depth, registry)
        rejection = Counter()
        best = None
        generated = 0
        verified_count = 0
        structural_verified = False
        seen = set()
        for node in values:
            signature = semantic_key(node, p)
            if signature in seen:
                continue
            seen.add(signature)
            generated += 1
            result = verify_instance(node, instance, depth, registry)
            if not result.verified:
                rejection[result.failed_layer] += 1
                continue
            verified_count += 1
            novel = signature not in scalar_semantics
            structural_verified |= novel
            key = syntax_key(node)
            welfare = result.application_utility * result.network_utility
            rank = (-welfare, key)
            if best is None or rank < best[0]:
                best = (rank, node, result, signature)
        row = {
            'method': method, 'family': p.family, 'configuration': p.configuration,
            'namespace': instance.namespace, 'seed_label': instance.seed_label,
            'public_hash': instance.public_hash, 'private_hash': instance.private_hash,
            'instance_hash': instance.instance_hash,
            'agreement': best is not None, 'candidate_count': generated,
            'candidate_count_unit': 'semantic_classes',
            'oracle_status': 'EXPERIMENTAL_NOT_VALIDATED',
            'verified_count': verified_count, 'any_verified_structural': structural_verified,
            'validator_rejections': dict(rejection), 'runtime_seconds': perf_counter() - start,
            'application_utility': None, 'network_utility': None, 'nash_welfare': None,
            'ast_depth': None, 'capability_count': None, 'representative': None,
            'structurally_novel': None, 'mechanism_labels': (),
        }
        if best is not None:
            _, node, result, signature = best
            row.update(application_utility=result.application_utility,
                       network_utility=result.network_utility,
                       nash_welfare=result.application_utility * result.network_utility,
                       ast_depth=ast_depth(node), capability_count=len(required_capabilities(normalize(node, p))),
                       representative=syntax_key(node), structurally_novel=signature not in scalar_semantics,
                       mechanism_labels=mechanism_labels(signature))
        rows.append(row)
    assert len({row['instance_hash'] for row in rows}) == 1
    by_method = {row['method']: row for row in rows}
    b1, oracle = by_method['B1'], by_method['O1']
    resolved = not b1['agreement'] and oracle['agreement']
    for row in rows:
        row['b1_deadlock'] = not b1['agreement']
        row['verified_deadlock_resolved'] = resolved
        row['pareto_improvement_over_b1'] = None
    if b1['agreement'] and oracle['agreement']:
        a, n = oracle['application_utility'], oracle['network_utility']
        ba, bn = b1['application_utility'], b1['network_utility']
        oracle['pareto_improvement_over_b1'] = a >= ba and n >= bn and (a > ba or n > bn)
    return rows

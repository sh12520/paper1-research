"""Fail-closed binding between the exact graph and the executing code.

This is an engineering snapshot, not a frozen experiment configuration.  It
does not create instances or access any experiment seed namespace.
"""
from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import struct
from itertools import product
from math import isfinite

from .fingerprints import ROOT, fingerprint
from .instances import canonical_json, load_model_config
from .registry import default_registry

GRAPH = ROOT / 'results' / 'engineering' / 'semantic_library.graph.gz'
AUDIT = ROOT / 'results' / 'engineering' / 'external_full_depth2_cached_01' / 'report.json'
SNAPSHOT = ROOT / 'EXECUTION_SNAPSHOT_FINGERPRINT.json'
SMOKE_SNAPSHOT = ROOT / 'SMOKE_EXECUTION_SNAPSHOT_FINGERPRINT.json'
SMOKE02_SNAPSHOT = ROOT / 'SMOKE02_EXECUTION_SNAPSHOT_FINGERPRINT.json'
SMOKE02_SHADOW_SNAPSHOT = ROOT / 'SMOKE02_SHADOW_EXECUTION_SNAPSHOT_FINGERPRINT.json'
PILOT_PREPARATION_SNAPSHOT = ROOT / 'PILOT_EXECUTION_SNAPSHOT_FINGERPRINT.json'
PILOT_EXECUTABLE_SNAPSHOT = ROOT / 'PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json'
EXECUTION_SCOPES = ('engineering', 'smoke', 'smoke02', 'shadow', 'pilot-preparation', 'pilot-execution')
AVAILABILITY_MANIFEST = ROOT / 'results' / 'engineering' / 'availability_indices' / 'manifest.json'
CORE_FILES = (
    'src/models.py', 'src/instances.py', 'src/registry.py', 'src/engine.py',
    'src/enumeration.py', 'src/state_machine.py', 'src/compact_semantics.py',
    'src/compact_dp.py', 'src/compact_graph.py',
)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def object_hash(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def source_tree_hash(source_hash, root=ROOT):
    """Bind schemas without altering the audited semantic-index fingerprint."""
    root=Path(root)
    schemas={p.relative_to(root).as_posix():sha256_file(p)
             for p in sorted(root.glob('schemas/**/*')) if p.is_file()}
    plan=root/'SMOKE02_PLAN_TEMPLATE.json'
    if not plan.is_file(): raise ValueError('formal identity plan template missing')
    pilot_plan=root/'PILOT01_PLAN_TEMPLATE.json'
    if not pilot_plan.is_file(): raise ValueError('pilot identity plan template missing')
    return object_hash({'source_hash':source_hash,'schemas':schemas,'formal_plan_sha256':sha256_file(plan),'pilot_plan_sha256':sha256_file(pilot_plan)})


def graph_header(path=GRAPH):
    with gzip.open(path, 'rb') as f:
        if f.read(4) != b'GSG1':
            raise ValueError('incompatible graph magic')
        raw = f.read(4)
        if len(raw) != 4:
            raise ValueError('truncated graph header')
        size = struct.unpack('>I', raw)[0]
        if size > 100_000_000:
            raise ValueError('invalid graph header length')
        data = f.read(size)
        if len(data) != size:
            raise ValueError('truncated graph header')
        header = json.loads(data)
    if header.get('format') != 'GENSPACE-GRAPH-v1' or header.get('key_bytes') != 49:
        raise ValueError('unsupported graph format')
    return header


def availability_index_digests():
    """Bind all 17 files to the index manifest, including pre/post checks."""
    manifest = json.loads(AVAILABILITY_MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('format') != 'GENSPACE-AVAILABILITY-MANIFEST-v1':
        raise ValueError('unsupported availability manifest')
    entries = manifest.get('patterns', [])
    expected_patterns = set(range(16, 32)) | {0}
    if len(entries) != len(expected_patterns) or {x.get('pattern') for x in entries} != expected_patterns:
        raise ValueError('availability manifest is incomplete or duplicated')
    result = {}
    for item in entries:
        pattern = item['pattern']
        digest = sha256_file(AVAILABILITY_MANIFEST.parent / f'availability_{pattern:02d}.bin.gz')
        if digest != item.get('sha256') or item.get('class_set_mismatches') != 0:
            raise ValueError('availability index mismatch')
        result[str(pattern)] = digest
    return result


def build_snapshot(graph=GRAPH, audit=AUDIT, *, scope='engineering'):
    """Construct snapshot only after checking the independently audited core."""
    if scope not in EXECUTION_SCOPES:
        raise ValueError('unsupported execution scope')
    current = fingerprint()
    report = json.loads(Path(audit).read_text(encoding='utf-8'))
    old = report['code_fingerprint']
    if not report['comparison']['exact_bytewise_sets_equal']:
        raise ValueError('independent reference did not match')
    if (report['comparison']['graph_unique_count'] != 1394064 or
            report['expected_syntax_count'] != 4909437):
        raise ValueError('unexpected audited candidate count')
    from .core_authorization_compat import core_source_matches
    if any(not core_source_matches(p,old['sources'].get(p),current['sources'].get(p),ROOT) for p in CORE_FILES):
        raise ValueError('semantic core differs from the independent audit')
    if old['config_hash'] != current['config_hash']:
        raise ValueError('configuration differs from the independent audit')
    graph_digest = sha256_file(graph)
    if graph_digest != report['auxiliary_script_and_graph_hashes']['graph']:
        raise ValueError('graph digest differs from the independent audit')
    header = graph_header(graph)
    model_config = load_model_config()
    registry = {key: asdict(value) for key, value in sorted(default_registry().items())}
    try:
        numpy_version = metadata.version('numpy')
    except metadata.PackageNotFoundError:
        numpy_version = None
    dependencies = {'python': platform.python_version(),
                    'implementation': platform.python_implementation(),
                    'numpy': numpy_version}
    return {
        'snapshot_version': 2,
        'execution_scope': scope,
        'source_tree_sha256': source_tree_hash(current['source_hash']),
        'semantic_core_source_hashes': {p: current['sources'][p] for p in CORE_FILES},
        'runner_source_hash': current['sources']['src/runner.py'],
        'config_sha256': current['config_hash'],
        'dependency_versions': dependencies,
        'dependency_fingerprint': object_hash(dependencies),
        'python_version': platform.python_version(),
        'semantic_library_format_version': header['format'],
        'semantic_library_sha256': graph_digest,
        'availability_manifest_sha256': sha256_file(AVAILABILITY_MANIFEST),
        'availability_index_sha256': availability_index_digests(),
        'semantic_class_count': report['comparison']['graph_unique_count'],
        'registry_fingerprint': object_hash(registry),
        'model_fingerprint': object_hash({'model_draft': model_config['model_draft'],
                                          'capability_cost_accounting': model_config['capability_cost_accounting']}),
        'independent_reference_report_sha256': sha256_file(audit),
    }


def verify_snapshot(path=SNAPSHOT, graph=GRAPH, audit=AUDIT, *, scope='engineering'):
    """Reject absent, stale or mismatched code, environment, model or graph."""
    saved = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = build_snapshot(graph, audit, scope=scope)
    if saved != expected:
        different = sorted(k for k in set(saved) | set(expected) if saved.get(k) != expected.get(k))
        raise ValueError('execution snapshot mismatch: ' + ', '.join(different))
    return saved


def verify_public_instance(public, snapshot):
    """Fail closed unless the public model matches the audited graph basis.

    Capacity and capability availability are allowed to vary per instance;
    they are checked independently during public filtering and feasibility.
    Extra equivalent provider declarations are permitted in the registry.
    """
    full = load_model_config()
    m = full['model_draft']
    grid = full['parameter_grid']
    if public.family not in grid['family']:
        raise ValueError('unsupported benchmark family')
    required_configuration = ('resource_pressure', 'preference_conflict',
                              'capability_richness', 'composition_depth')
    if set(public.configuration) != set(required_configuration):
        raise ValueError('instance configuration is incomplete or has unexpected fields')
    for key in required_configuration:
        value = public.configuration[key]
        if value not in grid[key] or (key == 'composition_depth' and type(value) is not int):
            raise ValueError('unsupported configuration field: ' + key)
    if public.model_config_hash != snapshot['model_fingerprint']:
        raise ValueError('instance model fingerprint differs from snapshot')
    if public.horizon != m['horizon'] or tuple(public.states) != tuple(m['states']):
        raise ValueError('unsupported horizon or exogenous states')
    for name, config_name in (('m0_profiles', 'm0'), ('mr_profiles', 'mr'), ('b2_profiles', 'b2')):
        domain = m['scalar_domains'][config_name]
        expected = tuple(product(domain['quality'], domain['deadline'], domain['rate']))
        actual = tuple((p.quality, p.deadline, p.rate) for p in getattr(public, name))
        if actual != expected:
            raise ValueError('instance profile domain differs: ' + name)
    for name in ('conditions', 'durations', 'offsets', 'offload_levels'):
        if tuple(getattr(public, name)) != tuple(m[name]):
            raise ValueError('instance grammar basis differs: ' + name)
    if tuple(tuple(x) for x in public.intervals) != tuple(tuple(x) for x in m['intervals']):
        raise ValueError('instance validity intervals differ')
    if public.resource_parameters != m['demand'] or public.public_constraints != m['public_hard_constraints']:
        raise ValueError('unsupported resource parameters or public constraints')
    canonical = {key: asdict(value) for key, value in sorted(default_registry().items())}
    actual = {key: public.registry.get(key) for key in canonical}
    if object_hash(actual) != snapshot['registry_fingerprint']:
        raise ValueError('canonical registry declarations differ')
    if not set(public.capabilities) <= set(public.registry):
        raise ValueError('available capability is missing a registry declaration')
    expected_cells = {(t, s) for t in range(public.horizon) for s in public.states}
    cells = {(t, s) for t, s, *_ in public.capacity}
    if cells != expected_cells or len(public.capacity) != len(expected_cells):
        raise ValueError('capacity cells are missing or duplicated')
    if any(not isfinite(v) or v < 0 for row in public.capacity for v in row[2:]):
        raise ValueError('invalid capacity')


def verify_private_preferences(private):
    """Reject non-model inputs before evaluating any private utility.

    The documented sampling ranges contain strictly positive finite weights
    and reservations within [0,1]. Rejection here is fail-closed input
    validation; it never changes public candidate generation.
    """
    names = (
        (private.application, ('quality_weight', 'latency_weight',
                               'start_delay_weight', 'switching_penalty')),
        (private.network, ('ran_cost', 'fh_cost', 'edge_cost',
                           'policy_complexity_cost', 'actuation_switching_cost')),
    )
    for prefs, keys in names:
        if any(type(prefs.get(k)) not in (int, float) or not isfinite(prefs[k]) or prefs[k] <= 0
               for k in keys):
            raise ValueError('invalid utility weights')
        if not isfinite(sum(prefs[k] for k in keys)):
            raise ValueError('utility weight total is not finite')
        value = prefs.get('reservation')
        if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 1:
            raise ValueError('invalid reservation utility')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--write', action='store_true')
    p.add_argument('--scope', choices=EXECUTION_SCOPES, default='engineering')
    args = p.parse_args()
    if args.write:
        target = {'engineering': SNAPSHOT, 'smoke': SMOKE_SNAPSHOT, 'smoke02': SMOKE02_SNAPSHOT, 'shadow': SMOKE02_SHADOW_SNAPSHOT, 'pilot-preparation': PILOT_PREPARATION_SNAPSHOT, 'pilot-execution': PILOT_EXECUTABLE_SNAPSHOT}[args.scope]
        if args.scope == 'pilot-preparation' and target.exists(): raise FileExistsError('historical preparation snapshot is immutable')
        target.write_text(json.dumps(build_snapshot(scope=args.scope), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    else:
        verify_snapshot(path={'engineering': SNAPSHOT, 'smoke': SMOKE_SNAPSHOT, 'smoke02': SMOKE02_SNAPSHOT, 'shadow': SMOKE02_SHADOW_SNAPSHOT, 'pilot-preparation': PILOT_PREPARATION_SNAPSHOT, 'pilot-execution': PILOT_EXECUTABLE_SNAPSHOT}[args.scope], scope=args.scope)
        print('execution snapshot verified')

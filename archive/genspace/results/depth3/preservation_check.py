"""Offline preservation and graph-independence seal audit for depth three."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
from audit_common import HERE, ROOT, read_json, sealed_payloads, write_json

sys.path.insert(0,str(ROOT))
from src.instances import deserialize_instance


LEGACY_ROOTS = ('results/grammar_gate','results/grammar_dedup')
ONLINE_SOURCES = {
    'results/depth3/run_depth3.py', 'results/depth3/depth_search.py',
    'results/depth3/check_reduced_depth3.py', 'results/grammar_dedup/dedup_search.py',
    'results/grammar_gate/grammar_search.py', 'results/grammar_gate/abstract_semantics.py',
    'results/grammar_gate/guard.py', 'results/grammar_gate/protocol_adapter.py',
}
GUARD_KEYS = {
    'semantic_graph_file','index_gate_artifact','availability_index_artifact',
    'unlisted_workspace_input','write_outside_current_output','FastLibrary.from_graph',
    'FastLibrary.__init__','AvailabilityBundle.load','read_graph','graph_library',
    'compact_dp.compact_library','compact_graph.compact_library','semantic_dp.library',
    'semantic_dp.streaming_reference','enumeration.candidates','engine.enumerate_compositions',
    'generate_instance','derive_seed',
}
LIMITS = dict(wall_seconds=120.,worker_rss_mib=2048,partial_expanded=2_000_000,frontier_size=260_000,
              prelaunch_available_mib=1280,emergency_available_mib=768)


def historical_auditor():
    source = ROOT/'results/grammar_gate/verify_preservation.py'
    spec = spec_from_file_location('depth3_prior_historical_audit',source)
    if spec is None or spec.loader is None:
        raise ValueError('previous read-only historical checksum auditor is unavailable')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_plans():
    fixed = [entry for entry in read_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
             if entry['seed_index']==0]
    configs = {(x['family'], *(x['configuration'][name] for name in (
            'resource_pressure','preference_conflict','capability_richness','composition_depth'))) for x in fixed}
    if not len(fixed)==len(configs)==len({x['instance_id'] for x in fixed})==96:
        raise ValueError('fixed-grid design is incomplete or duplicated')
    development = [x for x in fixed if x['configuration']['composition_depth']==2 and
                   x['configuration']['preference_conflict']=='high']
    if len(development)!=24:
        raise ValueError('derived fixed-grid design does not contain 24 slot IDs')
    return {'regression':fixed,'development':development}


def check_case(phase, slot, row, sealed_entry, derived_entry, input_manifest, file_sha):
    iid = slot['instance_id']
    source = ROOT/'results/pilot/instances'/(iid+'.json')
    source_raw = source.read_bytes()
    instance = deserialize_instance(source_raw.decode('utf8'))
    actual_source = {'sha256':sha256(source_raw).hexdigest(),'instance_hash':instance.instance_hash,
                     'public_hash':instance.public_hash,'private_hash':instance.private_hash}
    if actual_source != input_manifest.get(iid) or instance.namespace!='GENSPACE-FAIL-01-PILOT':
        raise ValueError('serialized source does not match the immutable prior manifest')
    raw_id = sealed_entry['path']
    if raw_id != f'{phase}/{iid}.json':
        raise ValueError('online seal contains a noncanonical case location')
    expected_depth = 3 if phase=='development' else slot['configuration']['composition_depth']
    if (row['instance_hash']!=actual_source['instance_hash'] or row['serialized_sha256']!=actual_source['sha256']
            or row['source_sha256']!=actual_source['sha256'] or row['family']!=slot['family']
            or row['family']!=instance.public.family or row['configuration']!=slot['configuration']
            or row['configuration']!=instance.public.configuration or row['effective_depth']!=expected_depth):
        raise ValueError('sealed case identity, configuration, or effective depth differs')
    if phase=='regression':
        if derived_entry is not None or 'derived_query_id' in row or 'derived_input_sha256' in row:
            raise ValueError('an original-depth regression case carries a depth-3 derived copy')
        return

    query_id = iid+'__METHOD_D3'
    copy_path = HERE/'development/derived_inputs'/(query_id+'.json')
    if (derived_entry is None or derived_entry['path']!=copy_path.relative_to(HERE).as_posix()
            or not copy_path.is_file() or file_sha(copy_path)!=derived_entry['sha256']
            or row['derived_input_sha256']!=derived_entry['sha256'] or row['derived_query_id']!=query_id):
        raise ValueError('derived copy is missing or does not match the sealed hash')
    expected = {'derived_query_id':query_id,'source_instance_id':iid,'source_identity':actual_source,
                'effective_depth':3,'scope':'development_method_extension','source_record':json.loads(source_raw)}
    if read_json(copy_path)!=expected:
        raise ValueError('derived copy changed original values or reported identity')


def check_phase(phase, slots, instances, anchored_reduced, reduced, file_sha):
    folder = HERE/phase
    path = folder/'search_seal.json'
    seal,rows,seal_sha = sealed_payloads(path)
    manifest = seal['manifest']
    phase_errors = []
    expected_ids = [s['instance_id'] for s in slots]
    if (manifest!=read_json(folder/'online_manifest.json') or manifest.get('phase')!=phase
            or manifest.get('instance_ids')!=expected_ids or list(rows)!=expected_ids):
        phase_errors.append('sealed, saved, and planned manifest scopes differ')
    if (manifest.get('effective_depth')!=(3 if phase=='development' else 'original')
            or manifest.get('limits')!=LIMITS or manifest.get('tie_rule')!='score_then_unsigned_lexicographic_compact_key'
            or manifest.get('prefix_digest')!='sha256_concat_binary64_be_then_key'):
        phase_errors.append('engine scope, limits, or ranking declaration differs')
    sources = manifest['sources']
    different_sources = sorted(name for name in ONLINE_SOURCES
                               if not (ROOT/name).is_file() or file_sha(ROOT/name)!=sources.get(name))
    if set(sources)!=ONLINE_SOURCES or different_sources:
        phase_errors.append('online source files changed or are missing')
    if (manifest.get('reduced_evidence_sha256')!=anchored_reduced or reduced.get('status')!='PASS'
            or reduced.get('depth_search_sha256')!=sources.get('results/depth3/depth_search.py')):
        phase_errors.append('sealed method and independent reduced correctness are not bound together')
    counts = seal['guard'].get('forbidden_call_counts',{})
    if (seal['guard'].get('pass') is not True or seal['guard'].get('blocked')!=[]
            or not GUARD_KEYS<=set(counts) or any(type(value) is not int or value!=0 for value in counts.values())):
        phase_errors.append('online guard observations are missing or nonzero')

    derived = seal.get('derived_inputs',{})
    expected_derived_ids = expected_ids if phase=='development' else []
    if list(derived)!=expected_derived_ids:
        phase_errors.append('sealed derived identities differ from planned depth-3 identities')
    actual_queries = {p.stem for p in folder.glob('*.json') if p.stem not in ('search_seal','online_manifest')}
    if actual_queries!=set(expected_ids):
        phase_errors.append('unexpected or missing case files on disk')
    actual_copies = {p.stem for p in (folder/'derived_inputs').glob('*.json')}
    if actual_copies!={iid+'__METHOD_D3' for iid in expected_derived_ids}:
        phase_errors.append('unexpected or missing derived copy files on disk')

    case_errors = {}
    for slot in slots:
        iid = slot['instance_id']
        try:
            check_case(phase,slot,rows[iid],seal['cases'][iid],derived.get(iid),instances,file_sha)
        except (OSError, KeyError, ValueError) as exc:
            case_errors[iid] = str(exc)
    return {'passed':not phase_errors and not case_errors,'seal_sha256':seal_sha,
            'sealed_cases':len(rows),'expected_cases':len(slots),'sealed_copies':len(derived),
            'sources_checked':len(sources),'changed_sources':different_sources,
            'forbidden_call_counts':counts,'phase_errors':phase_errors,'case_errors':case_errors}


def confirmation_paths():
    roots = (ROOT,ROOT/'results')
    return sorted(p.relative_to(ROOT).as_posix() for parent in roots for p in parent.iterdir()
                  if p.name.lower().startswith(('confirm','genspace-fail-01-confirm')) and
                  (p.is_dir() or p.suffix.lower() in ('.json','.jsonl','.csv','.yaml','.yml')))


def main():
    past = historical_auditor()
    historical = past.historical_checks()
    prior = read_json(HERE/'historical_inputs.json')
    missing, changed = past.compare(prior)
    declared = {p.relative_to(ROOT).as_posix() for location in LEGACY_ROOTS
                for p in (ROOT/location).rglob('*') if p.is_file()}
    unexpected = sorted(declared-set(prior))
    frozen = (ROOT/'FROZEN_CONFIG.yaml').exists()
    authorized = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')['namespace_authorizations']['CONFIRM']['allowed']
    confirm_outputs = confirmation_paths()
    preserved = (len(prior)==791 and historical['files_checked']==16544
                and historical['prior_index_replay_seal_matches'] and authorized is False and not frozen
                and not any(historical[k] for k in ('historical_manifest_conflicts','missing','changed',
                                                     'unexpected_files_in_historical_trees'))
                and not (missing or changed or unexpected or confirm_outputs))

    reduced_path = HERE/'reduced_depth3_correctness.json'
    reduced = read_json(reduced_path)
    reduced_sha = past.file_sha(reduced_path)
    instances = read_json(ROOT/'results/pilot/instances_manifest.json')
    checks = {}
    for phase,slots in expected_plans().items():
        try:
            checks[phase] = check_phase(phase,slots,instances,reduced_sha,reduced,past.file_sha)
        except (OSError,KeyError,ValueError) as exc:
            checks[phase] = {'passed':False,'phase_errors':[str(exc)]}
    passed = preserved and all(check['passed'] for check in checks.values())
    report = {'status':'PASS' if passed else 'FAIL','preserved':preserved,
              'graph_independence_checks':'PASS' if passed else 'FAIL','historical':historical,
              'immediate_historical_files_checked':len(prior),'historical_anchor_sha256':past.file_sha(HERE/'historical_inputs.json'),
              'prior_missing':missing,'prior_changed':changed,'prior_unexpected':unexpected,
              'reduced_evidence_sha256':reduced_sha,'confirm_denied':authorized is False,
              'confirmation_output_paths':confirm_outputs,'frozen_config_exists':frozen,
              'online_seals':checks}
    write_json(HERE/'preservation_check.json',report)
    print(json.dumps(report,indent=2),flush=True)
    if not passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()

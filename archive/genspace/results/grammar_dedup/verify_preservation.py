"""Offline integrity audit for the original artifacts and the dedup run seals."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = ROOT/'results/grammar_gate'
SOURCES = {
    *(f'results/grammar_dedup/{x}' for x in ('run_dedup.py','dedup_search.py')),
    *(f'results/grammar_gate/{x}' for x in (
        'run_search.py','grammar_search.py','abstract_semantics.py','guard.py','protocol_adapter.py')),
}
GUARD_KEYS = {
    'semantic_graph_file','index_gate_artifact','availability_index_artifact',
    'unlisted_workspace_input','write_outside_current_output','FastLibrary.from_graph',
    'FastLibrary.__init__','AvailabilityBundle.load','read_graph','graph_library',
    'compact_dp.compact_library','compact_graph.compact_library','semantic_dp.library',
    'semantic_dp.streaming_reference','enumeration.candidates','engine.enumerate_compositions',
    'generate_instance','derive_seed',
}


def historical_auditor():
    spec = importlib.util.spec_from_file_location('original_grammar_preservation', LEGACY/'verify_preservation.py')
    if spec is None or spec.loader is None:
        raise ValueError('missing original historical checksum auditor')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def audit_seal(path, file_sha, instances, fixed_ids):
    path = path.resolve()
    if path.name!='search_seal.json' or path.parent.parent!=HERE:
        raise ValueError(f'seal is outside the dedup run folders: {path}')
    seal = read_json(path)
    manifest = seal['manifest']
    requested, observed = manifest['requested_ids'], manifest['instance_ids']
    invalid_scope = (len(requested)!=len(set(requested)) or len(observed)==0 or
                     observed!=list(seal['cases']) or observed!=requested[:len(observed)])
    stop = manifest['stop_proof']
    phase = manifest['phase']
    if phase=='correctness':
        invalid_scope |= (manifest['mode']!='both' or observed!=requested or
                          set(observed)!=fixed_ids or manifest['correctness_sha256'] is not None)
    elif phase in ('diagnostic','performance'):
        source = 'diagnostic_ids.json' if phase=='diagnostic' else 'performance_ids.json'
        invalid_scope |= (manifest['mode']!='topk' or set(requested)!=set(read_json(HERE/source)) or
                          not isinstance(manifest['correctness_sha256'],str))
    else:
        invalid_scope = True
    if observed!=requested:
        invalid_scope |= (phase!='performance' or not manifest['early_g4_stop'] or
                          not isinstance(stop,dict) or stop.get('observed')!=len(observed) or
                          stop.get('cohort_n')!=len(requested) or stop.get('lower_bound',0.)<=stop.get('limit',0.))
    elif stop is not None:
        invalid_scope = True
    disk_manifest = read_json(path.parent/'online_manifest.json')
    manifest_matches = ({k:v for k,v in manifest.items() if k not in ('instance_ids','stop_proof')}
                        == disk_manifest)
    expected_sources = manifest['sources']
    changed_sources = sorted(name for name in SOURCES
                             if not (ROOT/name).is_file() or file_sha(ROOT/name)!=expected_sources.get(name))
    invalid_sources = set(expected_sources)!=SOURCES or bool(changed_sources)

    changed_cases, mismatched_instances = [], []
    for iid,evidence in seal['cases'].items():
        actual = (HERE/evidence['path']).resolve()
        if actual!=(path.parent/(iid+'.json')).resolve() or not actual.is_file() or file_sha(actual)!=evidence['sha256']:
            changed_cases.append(iid)
            continue
        entry = read_json(actual)
        original = instances.get(iid,{})
        if (entry.get('instance_id')!=iid or entry.get('serialized_sha256')!=original.get('sha256') or
                entry.get('instance_hash')!=original.get('instance_hash')):
            mismatched_instances.append(iid)
    guard = seal['guard']
    counters = guard.get('forbidden_call_counts',{})
    clean = (guard.get('pass') is True and guard.get('blocked')==[] and GUARD_KEYS <= set(counters)
             and all(type(v) is int and v==0 for v in counters.values()))
    verified = (seal.get('complete_batch') is True and manifest_matches and not invalid_scope and
                not invalid_sources and not changed_cases and not mismatched_instances and clean)
    return dict(directory=path.parent.name, phase=phase, seal_sha256=file_sha(path),
                bound_correctness_sha256=manifest['correctness_sha256'], sealed_cases=len(observed),
                expected_cases=len(requested), passed=verified, invalid_scope=invalid_scope,
                manifest_matches=manifest_matches, invalid_sources=invalid_sources,
                changed_sources=changed_sources, changed_cases=changed_cases,
                mismatched_instances=mismatched_instances, forbidden_call_counts=counters,
                blocked_events=guard.get('blocked',[]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='append',type=Path,default=[],help='defaults to every dedup run seal')
    args = parser.parse_args()
    past = historical_auditor()
    historical = past.historical_checks()
    legacy_anchor = read_json(HERE/'old_grammar_preservation_inputs.json')
    legacy_missing, legacy_changed = past.compare(legacy_anchor)
    legacy_files = {p.relative_to(ROOT).as_posix() for p in LEGACY.rglob('*') if p.is_file()}
    unexpected_legacy_files = sorted(legacy_files.difference(legacy_anchor))

    auth = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    confirm_denied = auth['namespace_authorizations']['CONFIRM']['allowed'] is False
    frozen_exists = (ROOT/'FROZEN_CONFIG.yaml').exists()
    preserved = (historical['prior_index_replay_seal_matches'] and confirm_denied and not frozen_exists
                 and not any(historical[k] for k in ('historical_manifest_conflicts','missing','changed',
                                                      'unexpected_files_in_historical_trees'))
                 and not (legacy_missing or legacy_changed or unexpected_legacy_files))

    instances = read_json(ROOT/'results/pilot/instances_manifest.json')
    plan = read_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
    fixed = {s['instance_id'] for s in plan if s['seed_index']==0}
    seal_paths = args.seal or sorted(HERE.glob('*/search_seal.json'))
    seals = [audit_seal(path,past.file_sha,instances,fixed) for path in seal_paths]
    unsealed = sorted(p.parent.name for p in HERE.glob('*/online_manifest.json')
                      if not (p.parent/'search_seal.json').is_file())
    declared = {p.parent.name for p in HERE.glob('*/search_seal.json')}
    audited = {row['directory'] for row in seals}
    correctness = [s for s in seals if s['phase']=='correctness']
    clearance_ok = not any(s['phase']!='correctness' for s in seals)
    if len(correctness)==1 and not clearance_ok:
        proof_dir = HERE/correctness[0]['directory']/'offline'
        evidence_file = proof_dir/'correctness_evidence.json'
        if evidence_file.is_file():
            evidence = read_json(evidence_file)
            proof_sha = past.file_sha(evidence_file)
            clearance_ok = (evidence['performance_allowed'] is True and evidence['correctness_status']=='PASS'
                            and evidence['seal_sha256']==correctness[0]['seal_sha256'] and
                            all(past.file_sha(proof_dir/name)==evidence['files_sha256'][key] for key,name in (
                                ('topk','topk_correctness.csv'), ('protocol','agreement_correctness.csv'))) and
                            all(s['bound_correctness_sha256']==proof_sha for s in seals if s['phase']!='correctness'))
    integrity = (preserved and not unsealed and audited==declared and len(seals)==len(audited)
                 and len(correctness)==1 and all(s['passed'] for s in seals) and clearance_ok)
    report = dict(preserved=preserved, confirm_denied=confirm_denied, frozen_config_exists=frozen_exists,
                  graph_independence_checks='PASS' if integrity else 'FAIL', historical=historical,
                  prior_failed_grammar_files_checked=len(legacy_anchor), prior_grammar_missing=legacy_missing,
                  prior_grammar_changed=legacy_changed, prior_grammar_unexpected=unexpected_legacy_files,
                  unsealed_online_runs=unsealed, unaudited_seal_directories=sorted(declared-audited),
                  correctness_clearance_matches=clearance_ok, online_seals=seals)
    (HERE/'preservation_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('preserved','confirm_denied','frozen_config_exists',
                                           'historical','graph_independence_checks','unsealed_online_runs')},indent=2))
    if not integrity:
        raise SystemExit(1)


if __name__=='__main__':
    main()

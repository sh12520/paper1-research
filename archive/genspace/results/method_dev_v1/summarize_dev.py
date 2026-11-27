"""Offline-only complete-development reporter; creates no benchmark instances."""
import argparse,csv,hashlib,json,math,statistics
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/method_dev_v1'
METHODS=('B2','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY','SINGLETON-ONLY','DG-PCE')
BUDGETS=(100,500,1000,5000,10000)
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')
def mean(x):return statistics.fmean(x) if x else None
def median(x):return statistics.median(x) if x else None
def write_csv(path, rows):
    if not rows:raise ValueError('empty output')
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in r.items()})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-dir',required=True);ap.add_argument('--privacy-audit',required=True);args=ap.parse_args()
    run=Path(args.run_dir).resolve()
    if run!=(BASE/'run_protocol_fixed').resolve():raise ValueError('only the protocol-fixed full run is eligible; earlier records cannot be merged')
    manifest=read(run/'run_manifest.json');guard=read(run/'_guard.json');privacy=read(args.privacy_audit)
    if privacy.get('pass') is not True:raise ValueError('privacy audit not passed')
    if privacy.get('source_hashes')!=manifest.get('code_sha256'):raise ValueError('privacy audit does not bind current method sources')
    if privacy.get('config_sha256')!=manifest.get('config_sha256'):raise ValueError('privacy audit does not bind current method config')
    if manifest.get('methods')!=list(METHODS) or manifest.get('budgets')!=list(BUDGETS) or manifest.get('offset')!=0 or manifest.get('limit')!=0:raise ValueError('not full fixed development run')
    if guard.get('count')!=1920 or guard.get('forbidden_calls')!={'derive_seed':0,'generate_instance':0}:raise ValueError('instance/seed guard failed')
    if sha((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_bytes())!=manifest['plan_sha256']:raise ValueError('plan changed')
    if sha((BASE/'method_config.json').read_bytes())!=manifest['config_sha256']:raise ValueError('config changed')
    if any(sha((BASE/name).read_bytes())!=h for name,h in manifest['code_sha256'].items()):raise ValueError('method source changed')
    if sha((ROOT/'PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json').read_bytes())!=manifest['pilot_execution_snapshot_sha256']:raise ValueError('pilot snapshot changed')
    if read(ROOT/'PILOT_AUTHORIZATION_STATE.json')['namespace_authorizations']['CONFIRM']['allowed'] is not False or (ROOT/'FROZEN_CONFIG.yaml').exists():raise ValueError('forbidden confirmation state')
    ids=[s['instance_id'] for s in read(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']]
    if len(ids)!=1920 or len(set(ids))!=1920:raise ValueError('plan coverage')
    expected=set(ids);actual={p.name for p in run.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name!='interrupted'}
    if expected!=actual:raise ValueError('missing or unexpected instance transactions')
    rows=[];records=[];mhash=sha(enc(manifest))
    for iid in ids:
        p=run/iid;raw=(p/'record.json').read_bytes();x=json.loads(raw);marker=read(p/'COMPLETE.json')
        if marker.get('instance_id')!=iid or marker.get('record_sha256')!=sha(raw) or marker.get('run_manifest_sha256')!=mhash or x.get('instance_id')!=iid:raise ValueError('invalid transaction '+iid)
        inputs={'instance':ROOT/'results/pilot/instances'/(iid+'.json'),'oracle':ROOT/'results/pilot/main'/iid/'result.json','oracle_marker':ROOT/'results/pilot/main'/iid/'COMPLETE.json','attribution':ROOT/'results/pilot_attribution_work/records'/(iid+'.json')}
        if marker.get('input_sha256')!={k:sha(path.read_bytes()) for k,path in inputs.items()}:raise ValueError('original input changed '+iid)
        if set(x['methods'])!=set(METHODS):raise ValueError('method coverage '+iid)
        o=x['oracle'];records.append(x)
        for method in METHODS:
            outs=x['methods'][method]['budgets']
            if set(outs)!=set(map(str,BUDGETS)):raise ValueError('budget coverage '+iid)
            previous=False
            for budget in BUDGETS:
                v=outs[str(budget)];agree=v['agreement']
                if type(agree) is not bool or previous and not agree or v['verification_calls']>budget:raise ValueError('budget/monotonicity '+iid)
                if agree and not o['O1_agreement']:raise ValueError('agreement exceeds oracle '+iid)
                if v['b2_agreement']!=o['B2_agreement'] or (v['b2_agreement'] and v['path']):raise ValueError('B2 entry condition '+iid)
                previous=agree
                row={'instance_id':iid,'instance_hash':x['instance_hash'],'public_hash':x['public_hash'],'private_hash':x['private_hash'],'family':x['family'],**x['configuration'],'method':method,'budget':budget,'oracle_recoverable':o['recoverable'],'multi_group_necessary':o['multi_group_necessary'],'non_offload_solvable':o['non_offload_solvable'],'o1_agreement':o['O1_agreement'],'o1_candidate_count':o['O1_candidate_count'],**v}
                for name,key in (('nash_gap','nash'),('application_utility_gap','uA'),('network_utility_gap','uN')):
                    oracle=o['O1_'+key];row[name]=(oracle-v[key]) if agree and o['O1_agreement'] else None
                row['search_reduction']=1-v['verification_calls']/o['O1_candidate_count']
                rows.append(row)
    targets=[x for x in records if x['oracle']['recoverable']];multi=[x for x in targets if x['oracle']['multi_group_necessary']];nonoff=[x for x in targets if x['oracle']['non_offload_solvable']]
    if len(targets)!=842 or len(multi)!=40 or len(nonoff)!=121:raise ValueError('unexpected oracle attribution cohort')
    # O1 is an unlimited offline reference, not an executable search method.
    for x in records:
        o=x['oracle']
        pilot=json.loads((ROOT/'results/pilot/main'/x['instance_id']/'result.json').read_bytes())
        historic_o1=next(v for v in pilot['rows'] if v['method']=='O1')['runtime_seconds']
        for budget in BUDGETS:
            rows.append({'instance_id':x['instance_id'],'instance_hash':x['instance_hash'],'public_hash':x['public_hash'],'private_hash':x['private_hash'],'family':x['family'],**x['configuration'],'method':'FULL-O1','budget':budget,'oracle_recoverable':o['recoverable'],'multi_group_necessary':o['multi_group_necessary'],'non_offload_solvable':o['non_offload_solvable'],'agreement':o['O1_agreement'],'b2_agreement':o['B2_agreement'],'nash_gap':0.0 if o['O1_agreement'] else None,'application_utility_gap':0.0 if o['O1_agreement'] else None,'network_utility_gap':0.0 if o['O1_agreement'] else None,'verification_calls':None,'search_reduction':None,'elapsed_seconds':historic_o1,'public_probe_count':None,'proposals':None,'rounds':None,'selected_group_mask':None})
    write_csv(BASE/'raw_results.csv',rows)
    summary=[]
    for method in (*METHODS,'FULL-O1'):
      for budget in BUDGETS:
        for cohort in ('ALL','RECOVERABLE','MULTI_GROUP','NON_OFFLOAD','F1','F2','F3','F4'):
            subset=[v for v in rows if v['method']==method and v['budget']==budget and (cohort=='ALL' or cohort=='RECOVERABLE' and v['oracle_recoverable'] or cohort=='MULTI_GROUP' and v['multi_group_necessary'] or cohort=='NON_OFFLOAD' and v['non_offload_solvable'] or cohort in ('F1','F2','F3','F4') and v['family']==cohort and v['oracle_recoverable'])]
            rec=[v for v in subset if v['oracle_recoverable']];deadlocks=[v for v in subset if not v['b2_agreement']];gaps=[v['nash_gap'] for v in subset if v['nash_gap'] is not None]
            def vals(k):return [v[k] for v in subset if v.get(k) is not None]
            summary.append({'method':method,'budget':budget,'cohort':cohort,'n':len(subset),'agreement_count':sum(v['agreement'] for v in subset),'agreement_rate':mean([int(v['agreement']) for v in subset]),'b2_deadlock_n':len(deadlocks),'b2_deadlocks_resolved':sum(v['agreement'] for v in deadlocks),'b2_deadlock_resolution_rate':mean([int(v['agreement']) for v in deadlocks]),'oracle_recoverable_n':len(rec),'oracle_recovered':sum(v['agreement'] for v in rec),'oracle_recovery_coverage':mean([int(v['agreement']) for v in rec]),'nash_gap_mean':mean(gaps),'nash_gap_n':len(gaps),'application_utility_gap_mean':mean(vals('application_utility_gap')),'network_utility_gap_mean':mean(vals('network_utility_gap')),'verification_calls_median':median(vals('verification_calls')),'verification_calls_mean':mean(vals('verification_calls')),'batch_calls_mean':mean(vals('batch_calls')),'batch_candidate_checks_mean':mean(vals('batch_candidate_checks')),'state_machine_calls_mean':mean(vals('state_machine_calls')),'search_reduction_mean':mean(vals('search_reduction')),'proposals_median':median(vals('proposals')),'rounds_median':median(vals('rounds')),'runtime_seconds_median':median(vals('elapsed_seconds')),'runtime_seconds_mean':mean(vals('elapsed_seconds')),'public_probe_count_mean':mean(vals('public_probe_count')),'b2_proxy_count_mean':mean(vals('b2_proxy_count')),'public_ranked_count_mean':mean(vals('public_ranked_count')),'public_setup_seconds_mean':mean(vals('public_setup_seconds')),'public_probe_seconds_mean':mean(vals('public_probe_seconds')),'public_ranking_seconds_mean':mean(vals('public_ranking_seconds')),'pair_composition_agreement_rate':mean([int(v['selected_group_mask'].bit_count()>=2) for v in subset if v.get('agreement') and v.get('selected_group_mask') is not None]),'first_mechanism_counts':dict(Counter(v['first_mechanism'] for v in subset if v.get('first_mechanism'))),'search_path_counts':dict(Counter(' > '.join(v.get('path',[])) for v in subset if v.get('path'))),'termination_reason_counts':dict(Counter(v['termination_reason'] for v in subset if v.get('termination_reason'))),'instances_hitting_stage_cap':sum(any(s.get('cap_hit') for s in v.get('stages',[])) for v in subset)})
    write_csv(BASE/'summary.csv',summary)
    get=lambda method,cohort:next(s for s in summary if s['method']==method and s['budget']==5000 and s['cohort']==cohort)
    d=get('DG-PCE','RECOVERABLE')['oracle_recovery_coverage'];random=get('RANDOM-BUDGET','RECOVERABLE')['oracle_recovery_coverage'];flat=get('FLAT-FEASIBILITY','RECOVERABLE')['oracle_recovery_coverage']
    wins=[f for f in ('F1','F2','F3','F4') if get('DG-PCE',f)['oracle_recovery_coverage']>get('RANDOM-BUDGET',f)['oracle_recovery_coverage']]
    checks={'orc_at_least_080':d>=.8,'beats_random':d>random,'beats_flat':d>flat,'beats_random_families_at_least_3':len(wins)>=3,'multi_group_nonzero':get('DG-PCE','MULTI_GROUP')['oracle_recovered']>0,'no_opponent_private_leakage':privacy['pass'] is True}
    gate={'status':'METHOD_PASS_V1' if all(checks.values()) else 'METHOD_WEAK_V1','checks':checks,'families_beating_random':wins,'development_only':True,'confirmation_gate':False,'privacy_audit':str(args.privacy_audit)}
    (BASE/'development_gate.json').write_text(json.dumps(gate,indent=2,sort_keys=True)+'\n',encoding='utf8')
    provenance={'run_directory':str(run),'run_manifest_sha256':mhash,'method_source_hashes':manifest['code_sha256'],'config_sha256':manifest['config_sha256'],'pilot_execution_snapshot_sha256':manifest['pilot_execution_snapshot_sha256'],'pilot_identity_plan_sha256':manifest['plan_sha256'],'pilot_instance_manifest_sha256':sha((ROOT/'results/pilot/instances_manifest.json').read_bytes()),'reporter_sha256':sha(Path(__file__).read_bytes()),'plotter_sha256':sha((BASE/'plot_budget_curves.py').read_bytes()),'no_new_random_instances':True,'no_benchmark_instance_seed_generation':True,'random_baseline_note':'Method PRNG is deterministically seeded from allowed sanitized public fields; it does not generate benchmark instances.'}
    (BASE/'report_provenance.json').write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n',encoding='utf8')
    failed=[v for v in rows if v['method']=='DG-PCE' and v['budget']==5000 and v['oracle_recoverable'] and not v['agreement']]
    lookup={(v['instance_id'],v['method'],v['budget']):v for v in rows}
    diagnosis={'unresolved_recoverable':len(failed),'reached_budget':sum(v['verification_calls']==5000 for v in failed),'termination_reason_counts':dict(Counter(v.get('termination_reason','unknown') for v in failed)),'stage_cap_hit':sum(any(s.get('cap_hit') for s in v.get('stages',[])) for v in failed),'stage_counts':dict(Counter(s['stage'] for v in failed for s in v.get('stages',[]) if s.get('verified',0)>0)),'multi_group_unresolved':sum(v['multi_group_necessary'] for v in failed),'multi_group_without_pair_stage':sum(v['multi_group_necessary'] and not any('+' in x for x in v['path']) for v in failed),'with_one_or_more_proposals':sum(v['proposals']>0 for v in failed),'random_resolved_same_instance':sum(lookup[(v['instance_id'],'RANDOM-BUDGET',5000)]['agreement'] for v in failed),'flat_resolved_same_instance':sum(lookup[(v['instance_id'],'FLAT-FEASIBILITY',5000)]['agreement'] for v in failed),'interpretation':'Observed path/budget/proposal indicators are not unique or causal failure classifications. Without the full verified candidate pool and private acceptance history at each checkpoint, selection, ranking, negotiation and budget effects are not separately identifiable.'}
    diagnosis['unresolved_instance_evidence']=[]
    for v in failed:
        attr=read(ROOT/'results/pilot_attribution_work/records'/(v['instance_id']+'.json'))
        diagnosis['unresolved_instance_evidence'].append({'instance_id':v['instance_id'],'family':v['family'],'first_mechanism':v.get('first_mechanism'),'path':v.get('path'),'stage_details':v.get('stages'),'proposals':v.get('proposals'),'verification_calls':v.get('verification_calls'),'successful_singleton_groups_offline':[name for bit,name in ((1,'C'),(2,'D'),(4,'P'),(8,'O')) if attr['subsets'][str(bit)]['agreement_exists']],'random_succeeds':lookup[(v['instance_id'],'RANDOM-BUDGET',5000)]['agreement'],'flat_succeeds':lookup[(v['instance_id'],'FLAT-FEASIBILITY',5000)]['agreement']})
    (BASE/'failure_diagnostics.json').write_text(json.dumps(diagnosis,sort_keys=True,indent=2)+'\n',encoding='utf8')
    lines=['# DG-PCE development results','','Exploratory development evaluation on the same 1,920 PILOT instances; this is not confirmation evidence. No new random benchmark instance or benchmark seed was generated. RANDOM-BUDGET uses a deterministic method PRNG derived only from allowed public fields.','',f"Development gate: **{gate['status']}**; individual checks: `{json.dumps(checks,sort_keys=True)}`.",'','Primary ORC uses 842 oracle-recoverable B2 deadlocks; family ORC uses the recoverable subset of that family. Nash/utility gaps are conditional on an actual agreement and are not zero-filled for failures; `nash_gap_n` reports the denominator. FULL-O1 is the existing unlimited offline oracle; it has no online budget/runtime. Search reduction counts exact verification calls, not public scan work.','', '| Method | B | ORC | Recovered / eligible | Median calls | Mean Nash gap | Gap n | Median runtime s |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for s in summary:
        if s['cohort']=='RECOVERABLE':lines.append('| {} | {} | {} | {}/{} | {} | {} | {} | {} |'.format(s['method'],s['budget'],s['oracle_recovery_coverage'],s['oracle_recovered'],s['oracle_recoverable_n'],s['verification_calls_median'],s['nash_gap_mean'],s['nash_gap_n'],s['runtime_seconds_median']))
    lines+=['','Numerical long-form results: `raw_results.csv` and `summary.csv`. Public setup/probe/ranking counts and times, pair use among agreements, first mechanisms, paths and utility gaps are in `summary.csv`. FULL-O1 runtime uses its recorded historical PILOT O1 stage time; unlike method end-to-end times it omits B2 and was not measured contemporaneously, so it is not directly comparable. The four method source hashes and locked configuration hash are in the run manifest. API-level information isolation is not an operating-system security boundary.','', 'Observed B=5000 failure indicators: `'+json.dumps(diagnosis,ensure_ascii=False,sort_keys=True)+'`. These indicators overlap; they do not establish distinct causal failure categories.']
    (BASE/'METHOD_DEV_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({'gate':gate,'records':len(records),'rows':len(rows),'cohort_sizes':{'recoverable':len(targets),'multi':len(multi),'nonoff':len(nonoff)}},sort_keys=True))

if __name__=='__main__':main()

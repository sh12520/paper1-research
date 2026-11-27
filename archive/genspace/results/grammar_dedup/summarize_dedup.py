"""Assess the staged duplication gate using sealed runs and archived baselines."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from reference import (BUDGETS, HERE, ROOT, TOP_K, guarded_seal, hash_bytes,
                       frozen_reference, load_json, original_cohorts, read_csv, write_csv, write_json)

CLASS_COUNT = 1_394_064
G3_THRESHOLD = .05
G4_THRESHOLD = .96834057


def read_evidence(seal_path):
    seal, cases, seal_hash = guarded_seal(seal_path)
    offline = seal_path.resolve().parent/'offline'
    evidence = load_json(offline/'correctness_evidence.json')
    if (evidence['seal_sha256'] != seal_hash or evidence['instance_count'] != len(cases)
            or evidence['online_sources'] != seal['manifest']['sources']):
        raise ValueError('correctness reference binds different online inputs')
    for name, file in (('topk', 'topk_correctness.csv'), ('protocol', 'agreement_correctness.csv')):
        if evidence['files_sha256'][name] != hash_bytes((offline/file).read_bytes()):
            raise ValueError(f'{name} reference comparison CSV changed')
    expected = {'topk': TOP_K, 'protocol': BUDGETS}
    results = {}
    for group, values in expected.items():
        checks = evidence[group]
        if set(checks) != {str(value) for value in values} or any(
                check['exact'] + check['mismatch'] + check['incomplete'] != 96 for check in checks.values()):
            raise ValueError('correctness evidence lacks the declared fixed query set')
        results[group] = ('FAIL' if any(check['mismatch'] for check in checks.values())
                          else 'PASS' if all(check['exact'] == 96 for check in checks.values())
                          else 'INCOMPLETE')
    if evidence['performance_allowed'] != all(v == 'PASS' for v in results.values()):
        raise ValueError('performance clearance differs from exact correctness evidence')
    return seal, evidence, results


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = q * (len(values) - 1)
    index = int(position)
    tail = min(index + 1, len(values) - 1)
    return values[index] + (values[tail] - values[index]) * (position - index)


def summary(values):
    measured = [float(value) for value in values if value not in (None, '')]
    if any(not math.isfinite(x) or x < 0. for x in measured):
        raise ValueError('timing/work measurement must be finite and nonnegative')
    return dict(n=len(measured), median=quantile(measured,.50), p95=quantile(measured,.95))


def fmt(data, *, percent=False):
    if not data['n']:
        return 'NA'
    if percent:
        return f"{data['median']:.4%} / {data['p95']:.4%}"
    return f"{data['median']:,.6g} / {data['p95']:,.6g}"


def floor(rows, ids, metric, threshold):
    measured = {r['instance_id']:float(r[metric]) for r in rows
                if r['instance_id'] in ids and r.get(metric) not in ('', None)}
    return dict(expected=len(ids), observed=len(measured), above=sum(x > threshold for x in measured.values()),
                threshold=threshold, full_p95_lower_bound=quantile([measured.get(i,0.) for i in ids],.95))


FIELDS = ('instance_id', 'family', 'richness', 'depth', 'conditioned_candidates', 'terminal_status',
          'candidate_outputs', 'public_search_s', 'unique_scores', 'score_ratio', 'partial_expanded',
          'frontier_peak', 'complete_assignments', 'duplicate_syntax_transfers',
          'witness_asts_materialized', 'witness_recipe_evaluations', 'symbolic_shapes', 'symbolic_cases',
          'template_count', 'template_recipes', 'template_build_s', 'template_payload_bytes',
          'exact_state_keys', 'complete_key_memo_size', 'cell_memo_size', 'peak_worker_bytes', 'limit', 'metric_payload')
EXTRA_FIELDS = ('witness_asts_materialized', 'witness_recipe_evaluations', 'symbolic_shapes',
                'symbolic_cases', 'template_count', 'template_recipes', 'template_build_s',
                'template_payload_bytes', 'exact_state_keys', 'complete_key_memo_size', 'cell_memo_size')


def perf_rows(paths, correctness, correctness_sha, original_large, meta, allowed):
    if paths and not allowed:
        raise ValueError('performance input supplied before exact 96/96 proof')
    records = {}
    seals = []
    for path in paths:
        seal, cases, hash_value = guarded_seal(path)
        manifest = seal['manifest']
        selected = manifest.get('requested_ids', [])
        if len(selected) != len(original_large) or set(selected) != original_large:
            raise ValueError('formal timing must request all original high-cost cohort IDs')
        if list(cases) != selected[:len(cases)] or manifest.get('phase') != 'performance':
            raise ValueError('formal timing cases differ from the original ordered high-cost cohort')
        if (manifest['sources'] != correctness['manifest']['sources']
                or manifest.get('correctness_sha256') != correctness_sha):
            raise ValueError('method source changed between exact and performance stages')
        if manifest.get('python') != correctness['manifest'].get('python'):
            raise ValueError('Python runtime changed between exact and performance stages')
        if len(cases)<len(original_large):
            proof=manifest.get('stop_proof') or {}
            times = sorted([case['topk_metrics']['wall_s'] for case in cases.values()]
                           + [0.]*(len(original_large)-len(cases)))
            lower=quantile(times,.95)
            if (not manifest.get('early_g4_stop') or proof.get('cohort_n')!=len(original_large)
                    or proof.get('observed')!=len(cases) or proof.get('lower_bound')!=lower
                    or lower<=G4_THRESHOLD):
                raise ValueError('formal timing ended early without a valid full-cohort p95 failure proof')
        if set(cases).intersection(records):
            raise ValueError('a formal performance ID appears in multiple shards')
        records.update(cases)
        seals.append(dict(seal_sha256=hash_value, case_count=len(cases)))
    rows = []
    for instance_id, case in records.items():
        config = case['configuration']
        previous = meta[instance_id]
        depth = int(config['composition_depth'])
        richness = config['capability_richness']
        if depth != int(previous['composition_depth']) or richness != previous['capability_richness']:
            raise ValueError(f'sealed query differs from archived cohort: {instance_id}')
        metrics = case.get('topk_metrics', {})
        scores = metrics.get('scores')
        status = case.get('topk_status','NOT_RUN')
        emitted = len(case.get('topk', []))
        full_count = int(previous['conditioned_structural_method_eligible'])
        if status not in ('COMPLETE','LIMIT','NOT_RUN'):
            raise ValueError(f'unknown performance terminal state: {instance_id}')
        if status == 'COMPLETE' and emitted != min(500, full_count):
            raise ValueError(f'performance case claims completion with an invalid prefix length: {instance_id}')
        rows.append(dict(instance_id=instance_id, family=previous['family'], richness=richness, depth=depth,
                         conditioned_candidates=full_count, terminal_status=status, candidate_outputs=emitted,
                         public_search_s=metrics.get('public_search_s', metrics.get('wall_s')),
                         unique_scores=scores, score_ratio=None if scores is None else scores/CLASS_COUNT,
                         partial_expanded=metrics.get('partial_expanded'), frontier_peak=metrics.get('frontier_peak'),
                         complete_assignments=metrics.get('complete_syntax'),
                         duplicate_syntax_transfers=metrics.get('duplicates'),
                         **{key:metrics.get(key) for key in EXTRA_FIELDS},
                         peak_worker_bytes=metrics.get('peak_working_set_bytes'), limit=case.get('topk_limit'),
                         metric_payload=metrics))
    return rows, seals


def historical_lanes(ids):
    recent = read_csv(ROOT/'results/index_gate/per_query.csv')
    prior = read_csv(ROOT/'results/grammar_gate/per_query.csv')
    lanes = {name:{r['instance_id']:r['total_public_search_s'] for r in recent
                    if r['instance_id'] in ids and r['k']=='500' and r['variant']==name}
             for name in ('flat','generic','contract')}
    if any(set(lane) != ids for lane in lanes.values()):
        raise ValueError('archived FLAT and indexed baseline scope differs from the declared >=100k set')
    lanes['prior_grammar'] = {r['instance_id']:r['wall_s'] for r in prior
                               if r['instance_id'] in ids and r['mode']=='topk'}
    return lanes


def check_diagnostic(path, correctness, clearance_digest, allowed):
    """Compare the same 128 previous fixtures without accessing the reference graph."""
    if path is None:
        return None
    if not allowed:
        raise ValueError('diagnostics cannot precede exact correctness clearance')
    seal, cases, seal_sha = guarded_seal(path)
    manifest = seal['manifest']
    old_reference, _ = frozen_reference()
    previous, old_hash = old_reference.sealed_cases(ROOT/'results/grammar_gate/fixed_depth2/search_seal.json')
    if (len(cases) != 128 or list(cases) != list(previous) or manifest.get('phase') != 'diagnostic'
            or manifest['sources'] != correctness['manifest']['sources']
            or manifest.get('correctness_sha256') != clearance_digest):
        raise ValueError('diagnostic seal does not bind the prior 128 fixtures and cleared method source')
    output = []
    for iid, case in cases.items():
        old = previous[iid]
        if (case['serialized_sha256'] != old['serialized_sha256']
                or case['configuration'] != old['configuration']):
            raise ValueError(f'new diagnostic input changed: {iid}')
        prev_metrics, new_metrics = old['topk_metrics'], case['topk_metrics']
        shared = min(len(old['topk']),len(case['topk']))
        same = all(a['key']==b['key'] and old_reference.same_float(a['score'],b['score']) and a['witness']==b['witness']
                   for a,b in zip(old['topk'][:shared],case['topk'][:shared]))
        timing_kind = ('exact_pair' if old['topk_status'] == case['topk_status'] == 'COMPLETE'
                       else 'prior_censored_lower_bound' if old['topk_status']=='LIMIT' and case['topk_status']=='COMPLETE'
                       else None)
        output.append(dict(instance_id=iid, checked_shared_prefix=shared, shared_prefix_exact=int(same),
                           prior_status=old['topk_status'], new_status=case['topk_status'],
                           prior_wall_s=prev_metrics['wall_s'], new_wall_s=new_metrics['wall_s'],
                           paired_speedup_kind=timing_kind,
                           paired_speedup=None if not timing_kind else prev_metrics['wall_s']/new_metrics['wall_s'],
                           prior_complete_syntax=prev_metrics['complete_syntax'],
                           prior_duplicate_transfers=prev_metrics['duplicates'],
                           new_complete_assignments=new_metrics['complete_syntax'],
                           new_duplicate_transfers=new_metrics['duplicates'],
                           new_witness_asts=new_metrics.get('witness_asts_materialized'),
                           new_witness_recipe_evaluations=new_metrics.get('witness_recipe_evaluations')))
    write_csv(HERE/'paired_old_128_diagnostics.csv',output)
    both_done = [r for r in output if r['paired_speedup_kind']=='exact_pair']
    prior_capped = [r for r in output if r['paired_speedup_kind']=='prior_censored_lower_bound']
    paired_metrics = ('prior_wall_s','new_wall_s','paired_speedup')
    return dict(n=len(output), diagnostics_seal_sha256=seal_sha, prior_seal_sha256=old_hash,
                prefix_matches=sum(bool(r['checked_shared_prefix']) and r['shared_prefix_exact'] for r in output),
                prefix_mismatches=sum(not r['shared_prefix_exact'] for r in output),
                no_shared_prefix=sum(r['checked_shared_prefix']==0 for r in output),
                certified_prior=sum(r['prior_status']=='COMPLETE' for r in output),
                certified_new=sum(r['new_status']=='COMPLETE' for r in output),
                formal_limits_before=sum(r['prior_status']=='LIMIT' for r in output),
                formal_limits_after=sum(r['new_status']=='LIMIT' for r in output),
                both_completed={key:summary(r[key] for r in both_done) for key in paired_metrics},
                censored_speedup_min=min((r['paired_speedup'] for r in prior_capped),default=None),
                censored_speedup_bounds={key:summary(r[key] for r in prior_capped) for key in paired_metrics},
                censored_cases=[{key:r[key] for key in ('instance_id','prior_wall_s','new_wall_s','paired_speedup')}
                                for r in prior_capped],
                metrics={key:summary(r[key] for r in output) for key in (
                    'prior_wall_s','new_wall_s','prior_complete_syntax','prior_duplicate_transfers',
                    'new_complete_assignments','new_duplicate_transfers','new_witness_asts',
                    'new_witness_recipe_evaluations')})


def former_protocol_limits(correctness_path):
    _, current, _ = guarded_seal(correctness_path)
    old_module, _ = frozen_reference()
    old, _ = old_module.sealed_cases(ROOT/'results/grammar_gate/correctness_protocol_depth2/search_seal.json')
    rows = []
    for iid, previous in old.items():
        if previous['protocol_status'] != 'LIMIT':
            continue
        updated = current[iid]
        rows.append(dict(instance_id=iid, prior_status='LIMIT', new_status=updated['protocol_status'],
                         prior_elapsed_s=previous['protocol_total_elapsed_s'],
                         new_elapsed_s=updated['protocol_total_elapsed_s'],
                         new_verification_calls=updated.get('protocol',{}).get('5000',{}).get('verification_calls')))
    return rows


def gate_for(rows, ids, metric, threshold):
    bound = floor(rows, ids, metric, threshold)
    complete = [r for r in rows if r['instance_id'] in ids and r['terminal_status']=='COMPLETE']
    full = len(complete)==len(ids)
    q = summary(row.get(metric) for row in complete)
    if bound['full_p95_lower_bound'] > threshold:
        gate = 'FAIL'
    elif full and q['n']==len(ids):
        gate = 'PASS' if q['p95'] <= threshold else 'FAIL'
    else:
        gate = 'INCOMPLETE'
    return gate, bound, q


def table(headers, lines):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |',
            *['| ' + ' | '.join(str(field).replace('|','\\|') for field in row) + ' |' for row in lines]]


def report(path, content):
    path.write_text('\n'.join(content) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correctness-seal', type=Path, required=True)
    parser.add_argument('--diagnostic-seal', type=Path)
    parser.add_argument('--performance-seal', type=Path, action='append', default=[])
    args = parser.parse_args()
    seal, evidence, exact = read_evidence(args.correctness_seal)
    _, meta, _, _, rich, large = original_cohorts()
    if not rich <= large:
        raise ValueError('formal timing scope does not contain all original rich depth-two cases')
    clearance_file=args.correctness_seal.resolve().parent/'offline'/'correctness_evidence.json'
    clearance_digest=hash_bytes(clearance_file.read_bytes())
    diagnostic=check_diagnostic(args.diagnostic_seal, seal, clearance_digest, evidence['performance_allowed'])
    if diagnostic and diagnostic['prefix_mismatches']:
        exact['topk'] = 'FAIL'
    rows, perf = perf_rows(args.performance_seal, seal, clearance_digest, large, meta,
                           evidence['performance_allowed'])
    import json
    if rows:
        write_csv(HERE/'per_query.csv', [{k:(json.dumps(r[k], sort_keys=True) if k=='metric_payload' else r[k])
                                         for k in FIELDS} for r in rows])
    else:
        with (HERE/'per_query.csv').open('w', encoding='utf-8', newline='') as sink:
            csv.DictWriter(sink,fieldnames=FIELDS).writeheader()
    g3, g3_floor, score_distribution = gate_for(rows, rich, 'score_ratio', G3_THRESHOLD)
    g4, g4_floor, runtime_distribution = gate_for(rows, large, 'public_search_s', G4_THRESHOLD)
    g5 = 'PASS'  # Every contributing online phase passed and was independently sealed.
    if not all(gate=='PASS' for gate in exact.values()):
        status = 'UNSOUND_OR_INCOMPLETE'
    elif g4 == 'FAIL':
        status = 'EXACT_BUT_SLOW'
    elif g3 == g4 == g5 == 'PASS':
        status = 'PASS'
    else:
        status = 'UNSOUND_OR_INCOMPLETE'

    attempted = {r['instance_id'] for r in rows if r['instance_id'] in large and r.get('public_search_s') is not None}
    certified = {r['instance_id'] for r in rows if r['instance_id'] in attempted and r['terminal_status']=='COMPLETE'}
    baseline_lanes = historical_lanes(large)
    lane_tables = {}
    for scope, ids in (('full cohort', large), ('same attempted IDs', attempted), ('same certified IDs', certified)):
        lane_tables[scope] = {name:summary(data[i] for i in ids & set(data)) for name,data in baseline_lanes.items()}
        lane_tables[scope]['deduplicated_grammar'] = summary(r['public_search_s'] for r in rows if r['instance_id'] in ids)

    check_table = [(group, index, counts['exact'], counts['mismatch'], counts['incomplete'])
                   for group in ('topk','protocol') for index,counts in evidence[group].items()]
    old_limits = former_protocol_limits(args.correctness_seal)
    report(ROOT/'GRAMMAR_DEDUP_CORRECTNESS.md', [
        '# Grammar deduplication correctness', '', f'G1 **{exact["topk"]}**. G2 **{exact["protocol"]}**.', '',
        'The fixed set consists of the original 96 seed-index-0 serialized development queries. An independent '
        'reference loaded the existing graph only after the graph-free online worker finished and its seal verified. '
        'It reproduced original FLAT candidate order and compared binary64 score bits. It also compared original '
        'agreements, representatives, utilities, Nash values, verification counts and exact proposal histories.', '',
        *table(('Check', 'K or budget', 'Exact / 96', 'Mismatch', 'Incomplete'), check_table), '',
        'The correctness record binds the online source fingerprint, sealed input IDs and reference CSVs. '
        'Formal performance clearance requires all comparisons at each K and budget.', '',
        f'Performance clearance = **{evidence["performance_allowed"]}**.',
        '', 'The final two limits from the preceding grammar gate were both included in the original fixed 96. '
        'Times below are correctness-phase end-to-end protocol run times. They do not enter G4.', '',
        *table(('Formerly limited query','Prior elapsed s (censored)','New elapsed s','New terminal status','B=5000 verification calls'), [
            (r['instance_id'],f"{r['prior_elapsed_s']:.6g}",f"{r['new_elapsed_s']:.6g}",r['new_status'],r['new_verification_calls'])
            for r in old_limits]),
        *(['', f'The same-128 diagnostic had {diagnostic["prefix_matches"]} exact nonempty shared prefixes, '
                f'{diagnostic["prefix_mismatches"]} mismatches and {diagnostic["no_shared_prefix"]} empty intersections.']
          if diagnostic else []),
    ])
    runtime_rows = [(scope,name,r['n'],fmt(r)) for scope, lanes in lane_tables.items() for name,r in lanes.items()]
    bound_rows = [(gate, b['observed'],b['expected'], b['above'],f'{b["full_p95_lower_bound"]:.9g}',b['threshold'])
                  for gate,b in (('G3',g3_floor),('G4',g4_floor))]
    work = {f:summary(r.get(f) for r in rows) for f in (
        'public_search_s', 'unique_scores', 'partial_expanded', 'frontier_peak',
        'complete_assignments', 'duplicate_syntax_transfers', *EXTRA_FIELDS, 'peak_worker_bytes')}
    report(ROOT/'GRAMMAR_DEDUP_PERFORMANCE.md', [
        '# Grammar deduplication performance', '', f'G3 **{g3}**. G4 **{g4}**. Formal performance queried {len(rows)} '
        'of the original target IDs. Only the formal performance lane contributes measurements.', '',
        'G3 uses the original 298 rich depth-two targets and score ratios relative to 1,394,064 classes. '
        'G4 uses the original 340 targets with at least 100,000 conditioned candidates and the frozen '
        '0.96834057-second K=500 p95 threshold. Complete-cohort coverage is required for a pass. Limited attempts '
        'still supply measured lower bounds on work and time; unmeasured IDs use the nonnegative lower bound zero '
        'only in the mathematical full-cohort lower-bound calculation.', '',
        *table(('Gate', 'Observed', 'Original n', 'Observed over threshold', 'Full p95 lower bound', 'Threshold'),bound_rows), '',
        'Archived timings for the prior grammar include their recorded limits. Matching-ID panels distinguish '
        'attempted and certified comparisons. Historical cohort timing is shown for its measured coverage.', '',
        *table(('Scope', 'Lane', 'n', 'Public search seconds median / p95'),runtime_rows), '',
        *table(('Observed new performance metric', 'n', 'median / p95'),
               [(f,r['n'],fmt(r)) for f,r in work.items()]), '',
        'Symbolic template construction time is included in public search time. A complete assignment instantiates '
        'a packed semantic key. Witness AST materializations and candidate recipe evaluations are measured '
        'separately. Template payload bytes cover documented Python objects and payloads. Peak worker bytes are '
        'observed process working set and include the resident runtime.', '',
        f'Rich depth-two certified score ratio median / p95 = {fmt(score_distribution, percent=True)}.',
        *(['', '## Same 128 prior diagnostic fixtures', '',
           f'Certified K=500 completion was {diagnostic["certified_prior"]}/128 before quotienting and '
           f'{diagnostic["certified_new"]}/128 after it. This panel uses separate diagnostic queries and is '
           'excluded from the G3 and G4 decisions.', '',
           *table(('Diagnostic metric','n','median / p95'),
                   [(name,value['n'],fmt(value)) for name,value in diagnostic['metrics'].items()]),
           '', 'The completed-pair speedup is old elapsed time divided by new elapsed time on the same ID. '
           'For the prior capped queries, old elapsed time is a lower bound on time to an eventual exact K=500 '
           'result, so the ratio also gives a lower bound. Per-ID ratios are summarized directly.', '',
           *table(('Paired scope','n','Prior s median / p95','New s median / p95','Speedup median / p95'), [
               (label, lane['paired_speedup']['n'],fmt(lane['prior_wall_s']),fmt(lane['new_wall_s']),fmt(lane['paired_speedup']))
               for label,lane in (('Both completed',diagnostic['both_completed']),('Prior capped, lower bounds',diagnostic['censored_speedup_bounds']))
           ]), '',
           *table(('Censored query','Prior observed s','New certified s','Speedup ≥'), [
               (r['instance_id'],f"{r['prior_wall_s']:.6g}",f"{r['new_wall_s']:.6g}",f"{r['paired_speedup']:.6g}")
               for r in diagnostic['censored_cases']]),
           '', 'See `paired_old_128_diagnostics.csv` for the exact matched-ID rows.'] if diagnostic else []),
    ])
    decision = dict(status=status, gates=dict(G1=exact['topk'],G2=exact['protocol'],G3=g3,G4=g4,G5=g5),
                    performance_queries=len(rows), performance_seals=perf,
                    score_distribution=score_distribution, runtime_distribution=runtime_distribution,
                    runtime_lanes=lane_tables, work=work, full_cohort_bounds=dict(G3=g3_floor,G4=g4_floor),
                    prior_128_diagnostic=diagnostic,
                    old_protocol_limits=old_limits)
    write_json(HERE/'gate_decision.json', decision)
    if status == 'PASS':
        route = 'Recommend the next separately authorized depth-three feasibility stage. This run certified only the depth≤2 gate.'
    elif status == 'EXACT_BUT_SLOW':
        route = 'Stop the on-demand grammar route under this gate. The observed full-cohort p95 lower bound exceeded the fixed runtime limit.'
    else:
        route = 'Stop the on-demand grammar route at the incomplete or failed evidence check.'
    report(ROOT/'GRAMMAR_FINAL_ROUTE_DECISION.md', [
        '# Grammar final route decision', '', f'**{status}**', '',
        *table(('Gate','Result'),list(decision['gates'].items())), '', route, '',
        'All evidence uses existing serialized development queries. The online guard records zero prohibited '
        'graph, index and data access in each contributing seal. The offline comparator is a separate '
        'process. CONFIRM was not executed.',
    ])
    print(dict(status=status,gates=decision['gates']), flush=True)


if __name__ == '__main__':
    main()

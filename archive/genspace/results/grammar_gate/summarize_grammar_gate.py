"""Summarize sealed on-demand runs and offline comparisons without re-running them."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from reference import BUDGETS, DEFAULT_SEAL, HERE, ROOT, TOP_K, read_json, sealed_cases, write_csv

CLASS_COUNT = 1_394_064
G3_CAP = .05
G4_INDEX_MULTIPLIER = 2.
G4_FLAT_FRACTION = .70
METRICS = ('partial_generated', 'partial_expanded', 'frontier_peak', 'complete_syntax',
           'unique_semantics', 'scores', 'duplicates', 'emitted', 'bound_pruned_estimate',
           'bound_deferred_subtrees', 'frontier_remaining', 'frontier_min_lb', 'pruned_illegal',
           'structural_domain_rejects', 'wall_s', 'public_search_s', 'peak_memory_bytes')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


def write_doc(name, lines):
    (ROOT / name).write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def quantile(values, q):
    a = sorted(values)
    if not a:
        return None
    position = q * (len(a) - 1)
    start = int(position)
    end = min(start + 1, len(a) - 1)
    return a[start] + (a[end] - a[start]) * (position - start)


def distribution(rows, col):
    values = [float(r[col]) for r in rows if r.get(col) not in ('', None)]
    return dict(n=len(values), median=quantile(values, .50), p95=quantile(values, .95))


def full_cohort_lower_bound(measurements, cohort, field, threshold):
    """A censored measurement lower-bounds that same cursor's completed work."""
    observed = {r['instance_id']: float(r[field]) for r in measurements
                if r.get(field) not in (None, '')}
    if not set(observed) <= cohort or len(observed) > len(cohort):
        raise ValueError('lower bound inputs must come from the declared comparison cohort')
    # This uses zero only as a mathematical lower bound for every unobserved
    # nonnegative measurement. Descriptive summaries always omit these cases.
    lower_values = [observed.get(iid, 0.) for iid in cohort]
    return dict(cohort_n=len(cohort), observed_n=len(observed), threshold=threshold,
                observed_above_threshold=sum(value > threshold for value in observed.values()),
                p95_lower_bound=quantile(lower_values, .95))


def display(pair, *, pct=False):
    if not pair['n']:
        return 'NA'
    if pct:
        return f"{pair['median']:.4%} / {pair['p95']:.4%}"
    return f"{pair['median']:,.4g} / {pair['p95']:,.4g}"


def safe_table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |',
            *['| ' + ' | '.join(str(v).replace('|', '\\|') for v in row) + ' |' for row in rows]]


def seal_guard_status(seal, cases):
    def valid(guard):
        counters = guard.get('forbidden_call_counts')
        return (guard.get('pass') is True and isinstance(counters, dict) and bool(counters)
                and all(v == 0 for v in counters.values()) and not guard.get('blocked'))

    global_guard = seal.get('guard', {})
    # Main's process-wide counters cover the sealed run. Per-case snapshots
    # are optional and, if present in a fixture, must also pass.
    case_guards = [case['guard'] for case in cases.values() if 'guard' in case]
    if (global_guard and not valid(global_guard)) or any(g and not valid(g) for g in case_guards):
        return 'FAIL'
    return 'PASS' if cases and valid(global_guard) and all(map(valid, case_guards)) else 'INCOMPLETE'


def make_query_rows(cases, meta):
    rows = []
    for instance_id, case in cases.items():
        config = case['configuration']
        common = dict(instance_id=instance_id, family=meta[instance_id]['family'],
                      target=int(meta[instance_id]['target_b2_no_full_o1_yes']),
                      depth=int(config['composition_depth']), richness=config['capability_richness'],
                      pressure=config['resource_pressure'], conflict=config['preference_conflict'],
                      conditioned_count=int(meta[instance_id]['conditioned_structural_method_eligible']))
        for mode in ('topk', 'protocol'):
            raw = case.get(mode + '_metrics', {})
            status = case.get(mode + '_status', 'NOT_RUN')
            metrics = {key: raw.get(key) for key in METRICS}
            # Keep an explicit null for absent measurements. Neither a limit nor
            # an unrun query is represented as zero wall time or zero work.
            if metrics['peak_memory_bytes'] is None:
                metrics['peak_memory_bytes'] = raw.get('peak_working_set_bytes')
            if status != 'NOT_RUN' and metrics['bound_pruned_estimate'] is None:
                # The cursor leaves unexpanded subtrees on the frontier. It
                # does not permanently prune any subtree on a score bound.
                metrics['bound_pruned_estimate'] = 0
            timing = case.get('protocol_timing', {}) if mode == 'protocol' else {}
            if mode == 'protocol':
                metrics['public_search_s'] = timing.get('public_search_seconds', metrics['public_search_s'])
            row = dict(common, mode=mode, status=status, **metrics,
                       scores_over_full_graph=(None if metrics['scores'] is None else metrics['scores'] / CLASS_COUNT),
                       consumed_by_protocol=timing.get('complete_candidates_consumed', raw.get('consumed_by_protocol')),
                       protocol_total_elapsed_s=case.get('protocol_total_elapsed_s') if mode == 'protocol' else None,
                       verification_s=timing.get('verification_seconds'), negotiation_s=timing.get('protocol_seconds'),
                       witness_s=timing.get('witness_seconds'),
                       limit_reason=raw.get('limit_reason', case.get(mode + '_limit')),
                       raw_metrics_json=json.dumps(raw, ensure_ascii=False, sort_keys=True))
            rows.append(row)
    return rows


def compared(rows, identifiers):
    r = [row for row in rows if row['instance_id'] in identifiers]
    return dict(expected=len(r), matched=sum(row['status'] == 'MATCH' for row in r),
                mismatched=sum(row['status'] == 'MISMATCH' for row in r),
                incomplete=sum(row['status'] == 'NOT_COMPARED' for row in r))


def exact_gate(rows, fixed):
    if any(r['status'] == 'MISMATCH' for r in rows):
        return 'FAIL'
    return 'PASS' if all(r['status'] == 'MATCH' for r in rows if r['instance_id'] in fixed) else 'INCOMPLETE'


def merge_supplements(paths, base_seal, base_cases, fixed, topk, protocol):
    """Merge only independent correctness evidence. Performance rows stay sealed."""
    top_keys = {(r['instance_id'], r['k']): dict(r, evidence='formal') for r in topk}
    protocol_keys = {(r['instance_id'], r['budget']): dict(r, evidence='formal') for r in protocol}
    records = []
    for path in paths:
        cases, seal_sha = sealed_cases(path)
        seal = read_json(path)
        if not set(cases) <= fixed & set(base_cases):
            raise ValueError('correctness supplement must use the original fixed grid only')
        if (seal['manifest']['sources'] != base_seal['manifest']['sources']
                or seal['manifest']['python'] != base_seal['manifest']['python']):
            raise ValueError('correctness-only extension changed the frozen online method source or runtime')
        mode = seal['manifest']['mode']
        if mode not in ('topk', 'protocol') or any(base_cases[i][mode + '_status'] != 'LIMIT' for i in cases):
            raise ValueError('correctness supplement did not select solely formal limited cases for one mode')
        if seal_guard_status(seal, cases) != 'PASS':
            raise ValueError('correctness supplement has no clean online guard seal')
        offline_dir = path.resolve().parent / 'offline'
        meta = read_json(offline_dir / 'reference_metadata.json')
        if meta['seal_sha256'] != seal_sha:
            raise ValueError('correctness supplement reference binds a different seal')
        if mode == 'topk':
            checked = read_csv(offline_dir / 'topk_correctness.csv')
            rows, key_name = top_keys, 'k'
        else:
            checked = read_csv(offline_dir / 'agreement_correctness.csv')
            rows, key_name = protocol_keys, 'budget'
        matched_new, discrepancies = 0, 0
        for row in checked:
            if row['instance_id'] not in cases:
                continue
            key = (row['instance_id'], row[key_name])
            old = rows[key]
            if row['status'] == 'MISMATCH' or (row['status'] == 'MATCH' and old['status'] == 'NOT_COMPARED'):
                matched_new += row['status'] == 'MATCH'
                discrepancies += row['status'] == 'MISMATCH'
                rows[key] = dict(row, evidence=path.resolve().parent.name)
        records.append(dict(mode=mode, seal_sha256=seal_sha, cases=len(cases),
                            newly_matched=matched_new, mismatches=discrepancies))
    return list(top_keys.values()), list(protocol_keys.values()), records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', type=Path, default=DEFAULT_SEAL)
    parser.add_argument('--supplement-seal', type=Path, action='append', default=[])
    args = parser.parse_args()
    cases, accepted_seal = sealed_cases(args.seal)
    seal = read_json(args.seal)
    references = read_json(HERE / 'reference_metadata.json')
    if references['seal_sha256'] != accepted_seal:
        raise ValueError('comparison metadata binds a different online seal')
    old_rows = read_csv(ROOT / 'results/flat_audit/per_instance.csv')
    meta = {row['instance_id']: row for row in old_rows}
    slots = read_json(ROOT / 'PILOT01_PLAN_TEMPLATE.json')['instances']
    fixed = {slot['instance_id'] for slot in slots if slot['seed_index'] == 0}
    targets = {iid for iid, r in meta.items() if r['target_b2_no_full_o1_yes'] == '1'}
    rich = {iid for iid in targets if meta[iid]['capability_richness'] == 'rich' and meta[iid]['composition_depth'] == '2'}
    large = {iid for iid in targets if int(meta[iid]['conditioned_structural_method_eligible']) >= 100_000}
    if (len(fixed), len(targets), len(rich), len(large)) != (96, 842, 298, 340):
        raise ValueError('declared comparison cohorts differ from the historical audit')

    topk = read_csv(HERE / 'topk_correctness.csv')
    protocol = read_csv(HERE / 'agreement_correctness.csv')
    expected_topk = {(iid, k) for iid in fixed | targets for k in TOP_K}
    expected_protocol = {(iid, b) for iid in fixed | targets for b in BUDGETS}
    if (len(topk) != len(expected_topk) or {(r['instance_id'], int(r['k'])) for r in topk} != expected_topk
            or len(protocol) != len(expected_protocol) or {(r['instance_id'], int(r['budget'])) for r in protocol} != expected_protocol):
        raise ValueError('offline reference rows do not cover the declared fixed grid and target cohorts')

    queries = make_query_rows(cases, meta)
    if not queries:
        raise ValueError('no online query rows in sealed run')
    write_csv(HERE / 'per_query.csv', tuple(queries[0]), queries)
    top_queries = [row for row in queries if row['mode'] == 'topk' and row['status'] != 'NOT_RUN']
    kth = {row['instance_id']: row['status'] for row in topk if row['k'] == '500'}
    top_success = [row for row in top_queries if kth[row['instance_id']] == 'MATCH']
    top_ready = {row['instance_id'] for row in top_success}

    checked_topk, checked_protocol, supplements = merge_supplements(
        args.supplement_seal, seal, cases, fixed, topk, protocol)
    if supplements:
        write_csv(HERE / 'topk_correctness_combined.csv', tuple(checked_topk[0]), checked_topk)
        write_csv(HERE / 'agreement_correctness_combined.csv', tuple(checked_protocol[0]), checked_protocol)

    g1 = exact_gate(checked_topk, fixed)
    g2 = exact_gate(checked_protocol, fixed)
    g5 = seal_guard_status(seal, cases)
    preservation_path = HERE / 'preservation_check.json'
    preservation = read_json(preservation_path) if preservation_path.is_file() else {}
    if preservation:
        if preservation['online']['seal_sha256'] != accepted_seal:
            raise ValueError('preservation check binds a different online seal')
        if preservation['graph_independence_checks'] != 'PASS' or not preservation['preserved']:
            g5 = 'FAIL'
    elif g5 == 'PASS':
        g5 = 'INCOMPLETE'
    g3 = 'INCOMPLETE'
    g4 = 'INCOMPLETE'
    baseline_rows = [row for row in read_csv(ROOT / 'results/index_gate/per_query.csv')
                     if row['k'] == '500' and row['instance_id'] in large]
    baselines = {variant: [r for r in baseline_rows if r['variant'] == variant]
                 for variant in ('flat', 'generic', 'contract')}
    if any(len(rows) != len(large) or {r['instance_id'] for r in rows} != large for rows in baselines.values()):
        raise ValueError('saved INDEX-GATE comparison does not cover the same >=100k cohort')

    rich_measured = [row for row in top_queries if row['instance_id'] in rich]
    rich_scored = distribution(rich_measured, 'scores_over_full_graph')
    g3_bound = full_cohort_lower_bound(rich_measured, rich, 'scores_over_full_graph', G3_CAP)
    if g3_bound['p95_lower_bound'] > G3_CAP:
        g3 = 'FAIL'
    elif rich <= top_ready and rich_scored['n'] == len(rich):
        g3 = 'PASS' if rich_scored['p95'] <= G3_CAP else 'FAIL'

    def search_seconds(row):
        public = row.get('public_search_s')
        return public if public is not None else row.get('wall_s')

    def runtime(rows, variant):
        out = [dict(search_s=search_seconds(row)) for row in rows]
        return distribution(out, 'search_s') if variant == 'grammar' else distribution(rows, 'total_public_search_s')

    large_measured = [row for row in top_queries if row['instance_id'] in large]
    large_done = [row for row in top_success if row['instance_id'] in large]
    measured_runtime = runtime(large_measured, 'grammar')
    done_runtime = runtime(large_done, 'grammar')
    historic_runtime = {kind: runtime(rows, kind) for kind, rows in baselines.items()}
    measured_ids = {row['instance_id'] for row in large_measured if search_seconds(row) is not None}
    done_ids = {row['instance_id'] for row in large_done if search_seconds(row) is not None}
    measured_baselines = {kind: runtime([r for r in rows if r['instance_id'] in measured_ids], kind)
                          for kind, rows in baselines.items()}
    done_baselines = {kind: runtime([r for r in rows if r['instance_id'] in done_ids], kind)
                      for kind, rows in baselines.items()}
    g4_threshold = min(G4_INDEX_MULTIPLIER * historic_runtime['contract']['p95'],
                       G4_FLAT_FRACTION * historic_runtime['flat']['p95'])
    g4_bound = full_cohort_lower_bound([dict(r, search_s=search_seconds(r)) for r in large_measured],
                                      large, 'search_s', g4_threshold)
    if g4_bound['p95_lower_bound'] > g4_threshold:
        g4 = 'FAIL'
    elif large <= top_ready and done_runtime['n'] == len(large):
        g4 = 'PASS' if done_runtime['p95'] <= g4_threshold else 'FAIL'
    gates = dict(G1=g1, G2=g2, G3=g3, G4=g4, G5=g5)
    depth2 = all(value == 'PASS' for value in gates.values())
    depth3 = read_json(HERE / 'depth3_cases.json') if (HERE / 'depth3_cases.json').exists() else []
    if depth3 and not depth2:
        raise ValueError('depth3 results exist before the depth2 gates passed')
    depth3_fields = ('instance_id', 'k', 'status', 'certified_count', 'partial_expanded',
                     'frontier_peak', 'wall_s', 'peak_memory_bytes', 'limit_reason')
    write_csv(HERE / 'depth3.csv', depth3_fields, depth3)

    if any(gates[g] == 'FAIL' for g in ('G1', 'G2', 'G5')):
        status = 'FAIL_CORRECTNESS'
    elif not depth2:
        status = 'FAIL_SCALABILITY'
    elif not depth3 or any(row['status'] != 'EXACT_TOPK_CERTIFIED' for row in depth3):
        status = 'PASS_DEPTH2_ONLY'
    else:
        status = 'PASS'

    comparisons = []
    for name, ids in (('Fixed grid', fixed), ('Target cohort', targets)):
        for k in TOP_K:
            c = compared([row for row in checked_topk if int(row['k']) == k], ids)
            comparisons.append((name, f'Top-{k}', c['expected'], c['matched'], c['mismatched'], c['incomplete']))
        for budget in BUDGETS:
            c = compared([row for row in checked_protocol if int(row['budget']) == budget], ids)
            comparisons.append((name, f'Protocol B={budget}', c['expected'], c['matched'], c['mismatched'], c['incomplete']))
    write_doc('GRAMMAR_CORRECTNESS_REPORT.md', [
        '# Grammar search correctness and bilateral agreement', '',
        f'G1 **{g1}**. G2 **{g2}**. The sealed online batch contains {len(cases)} existing fixtures. '
        f'The independent reference loaded the semantic graph after the seal was verified ({references["reference_graph_loaded"]}).', '',
        *(['`GRAMMAR_GATE_FAIL_CORRECTNESS` was observed in a compared prefix.', ''] if g1 == 'FAIL' else []),
        'Top-K uses original FLAT `make_plan` and recomputes the selected prefix scores with the original '
        '`_proxy` and score expression. The reference compares 49-byte semantic signatures in FLAT class-ID '
        'order and exact binary64 score bits. Each emitted prefix is checked even when the query later reaches a limit.', '',
        'Agreement compares the original hash-bound FLAT record for that serialized fixture. The checker compares '
        'the agreement result, class signature, normalized representative, both utility bit patterns, Nash, '
        'verification calls and proposal history through each budget. Missing certificates or snapshots are counted '
        'as incomplete. Fixed-grid coverage and zero observed differences are required for G1 and G2.', '',
        *safe_table(('Coverage', 'Check', 'Expected', 'Exact matches', 'Mismatches', 'Incomplete'), comparisons),
        '', 'See `results/grammar_gate/topk_correctness.csv` and `results/grammar_gate/agreement_correctness.csv` for original formal row details.',
        *(['', 'Separately sealed longer-limit correctness runs apply only to formal fixed-grid limits. '
                'The merged evidence is in `topk_correctness_combined.csv` and `agreement_correctness_combined.csv`. '
                'G3/G4 and all work distributions retain the original formal measurements.', '',
           *safe_table(('Mode', 'Replayed queries', 'New exact checks', 'New differences'),
                       [(r['mode'], r['cases'], r['newly_matched'], r['mismatches']) for r in supplements])]
          if supplements else []),
    ])

    per_cohort = []
    work = {}
    for name, ids in (('Fixed grid', fixed), ('842 targets', targets), ('Rich depth2', rich), ('>=100k', large)):
        rows = [row for row in top_queries if row['instance_id'] in ids]
        measurements = {field: distribution(rows, field) for field in ('partial_generated', 'partial_expanded',
                        'frontier_peak', 'complete_syntax', 'unique_semantics', 'scores', 'duplicates',
                        'scores_over_full_graph', 'wall_s', 'peak_memory_bytes')}
        work[name] = dict(expected=len(ids), attempted=len(rows), certified=len(ids & top_ready), **measurements)
        per_cohort.append((name, len(rows), len(ids & top_ready), len(ids), display(measurements['partial_generated']),
                           display(measurements['partial_expanded']), display(measurements['frontier_peak']),
                           display(measurements['complete_syntax']), display(measurements['scores']),
                           display(measurements['duplicates']), display(measurements['scores_over_full_graph'], pct=True),
                           display(measurements['wall_s']), display(measurements['peak_memory_bytes'])))
    runtime_table = [
        (scope, kind, metrics['n'], display(metrics))
        for scope, lanes in (('Full historical cohort', historic_runtime),
                             ('Same attempted IDs', dict(grammar=measured_runtime, **measured_baselines)),
                             ('Same certified IDs', dict(grammar=done_runtime, **done_baselines)))
        for kind, metrics in lanes.items()
    ]
    syntax_limited = [r for r in top_queries if r['status'] == 'LIMIT'
                      and r['complete_syntax'] and r['duplicates'] is not None]
    duplicate_share = [r['duplicates'] / r['complete_syntax'] for r in syntax_limited]
    example = max(syntax_limited, key=lambda row: row['duplicates'], default=None)
    bottleneck = dict(limited_k500_with_syntax_counts=len(syntax_limited),
                      limited_duplicate_fraction_min=min(duplicate_share, default=None),
                      limited_duplicate_fraction_max=max(duplicate_share, default=None),
                      largest_duplicate_count_example=None if not example else {
                          key:example[key] for key in ('instance_id', 'complete_syntax', 'duplicates', 'emitted')})
    write_doc('GRAMMAR_SEARCH_COST_REPORT.md', [
        '# Grammar search work and public search time', '',
        'Work summaries below describe measured online Top-K attempts, including limited queries. '
        'A scored-complete ratio divides exact public scores by the original 1,394,064 graph classes. '
        'The recorded `partial_generated` counter measures enqueues into the bound frontier, including '
        'structurally complete leaves awaiting transfer. `partial_expanded` counts unresolved hole expansions. '
        '`complete_syntax` counts complete leaf transfers and `scores` counts exact scores of unique eligible signatures. '
        'Quantiles use linear interpolation. '
        'Memory is the sampled or reported process working set. The bound permanently prunes zero subtrees. '
        'Unexpanded frontier nodes remain available to extend a certified prefix. The raw metric payload is '
        'retained in `per_query.csv`. Production and protocol consumption have separate columns. A stopped '
        'protocol run can lack the counters returned at its terminal budget.', '',
        *safe_table(('Cohort', 'Attempted', 'Exact K500', 'Expected', 'Frontier enqueues median/p95', 'Partial expanded median/p95',
                    'Frontier median/p95', 'Syntax leaves median/p95', 'Exact scores median/p95', 'Duplicates median/p95',
                    'Score ratio median/p95', 'Elapsed s median/p95', 'Peak memory B median/p95'), per_cohort), '',
        'The ≥100k comparison uses saved public-search timings from `INDEX-GATE-01`, including the original full '
        'FLAT score and sort. All three reference lanes depend on the pre-enumerated graph. The grammar lane '
        'consumes the typed DSL, public model and registry. It excludes independent reference work. '
        'Attempted-but-limited timings describe work until interruption, so G4 requires separately certified K=500 comparisons.', '',
        *safe_table(('Coverage', 'Lane', 'Measured instances', 'Public search seconds median/p95'), runtime_table), '',
        f'G3 uses p95 score ratio ≤ {G3_CAP:.0%} on all {len(rich)} rich-depth2 targets. '
        f'G4 requires full K=500 coverage of the same {len(large)} large instances and p95 no greater than '
        f'{G4_INDEX_MULTIPLIER:g}× the contract-aware index and {G4_FLAT_FRACTION:.0%} of FLAT. '
        'The FLAT percentage is the previous 30% engineering margin applied descriptively. It has no inferential claim.', '',
        'For a failed or censored comparison, elapsed time and score counts at the observed cutoff are lower bounds '
        'on completion for the same cursor. Filling missing entries with the nonnegative lower bound zero gives '
        'a mathematical lower bound on full-cohort p95, even when no full descriptive p95 can be reported. '
        'This calculation cannot establish a pass with incomplete coverage.', '',
        *safe_table(('Gate', 'Observations', 'Expected', 'Observed above threshold', 'Lower bound on full p95', 'Threshold'), [
            (gate, b['observed_n'], b['cohort_n'], b['observed_above_threshold'],
             f"{b['p95_lower_bound']:.6g}", f"{b['threshold']:.6g}")
            for gate, b in (('G3', g3_bound), ('G4', g4_bound))]), '',
        *([f'Among {len(syntax_limited)} limited K=500 attempts with a leaf count, '
           f'{min(duplicate_share):.2%}–{max(duplicate_share):.2%} of transferred syntax leaves duplicated an already seen '
           'semantic signature. Semantic duplication is the primary observed work bottleneck. '
           f'`{example["instance_id"]}` transferred {example["complete_syntax"]:,} complete syntax leaves, '
           f'of which {example["duplicates"]:,} were duplicates, and certified {example["emitted"]} outputs. '
           'The measurements quantify duplicated work and frontier growth. They do not separately attribute wall time '
           'to each cause.', '']
          if syntax_limited else []),
    ])
    write_doc('DEPTH3_FEASIBILITY_REPORT.md', [
        '# Depth 3 feasibility', '',
        ('Depth3 execution was gated off because the required depth2 gates did not all pass.' if not depth2 else
         'Depth3 outcomes use the fixed existing public query selection and require an exact frontier certificate.'),
        '', *safe_table(('K', 'Attempts', 'Certified', 'Certification rate'), [
            (k, len(rows), sum(r['status'] == 'EXACT_TOPK_CERTIFIED' for r in rows),
             format(sum(r['status'] == 'EXACT_TOPK_CERTIFIED' for r in rows) / len(rows), '.2%') if rows else 'NA')
            for k in (10, 100, 500) for rows in [[r for r in depth3 if int(r['k']) == k]]
        ]), '', 'See `results/grammar_gate/depth3.csv`. NA indicates absence of an eligible run.',
    ])
    write_doc('ON_DEMAND_GRAMMAR_GATE_REPORT.md', [
        '# ON-DEMAND-GRAMMAR-SEARCH-01', '', f'**{status}**', '',
        *safe_table(('Gate', 'Result'), list(gates.items())), '',
        *([f'G4 was ruled out after {g4_bound["observed_above_threshold"]} of the measured large-cohort cases '
           f'exceeded the {g4_threshold:.6f} s threshold. Even with a zero lower bound for unmeasured '
           f'cases, the full-cohort p95 is at least {g4_bound["p95_lower_bound"]:.6f} s. '
           f'With G4 ruled out, the main batch stopped at {sum(r["instance_id"] in targets for r in top_queries)} '
           f'of {len(targets)} target queries. Longer-limit retries '
           'serve fixed-grid correctness coverage only and do not alter the formal performance measurements.', '']
          if g4 == 'FAIL' and g4_bound['p95_lower_bound'] > g4_threshold else []),
        *(['Semantic duplication was the primary observed work bottleneck. '
           f'All {len(syntax_limited)} capped K=500 attempts with leaf counts spent '
           f'{min(duplicate_share):.2%}–{max(duplicate_share):.2%} of complete syntax transfers on duplicates.', '']
          if syntax_limited else []),
        'This is a feasibility gate on the fixed development DSL and frozen FLAT ranking. '
        'Top-down partial-program search, A*/best-first search, admissible abstract-interpretation bounds and '
        'hole filling are generic techniques. The tested domain-specific components are the contract '
        'state/time/resource envelope, capability-aware pruning, FLAT-compatible bounds and a lazy stream '
        'consumed by the existing bilateral protocol.', '',
        'See `GRAMMAR_BOUND_SPEC.md`, `PARTIAL_CONTRACT_ABSTRACT_SEMANTICS.md`, '
        '`GRAPH_INDEPENDENCE_AUDIT.md`, `GRAMMAR_CORRECTNESS_REPORT.md` and `GRAMMAR_SEARCH_COST_REPORT.md`. '
        'The execution scope is development only. CONFIRM was not invoked.',
        *(['', f'The preservation audit checked {preservation["historical"]["files_checked"]:,} historical files, '
                f'and recorded the clean graph-independence seal for {preservation["online"]["sealed_cases"]} cases.']
          if g5 == 'PASS' else []),
    ])
    result = dict(status=status, gates=gates, online_sealed_cases=len(cases), depth2_pass=depth2,
                  depth3_rows=len(depth3), work=work,
                  large_runtime_separate=dict(grammar_attempted=measured_runtime, grammar_certified=done_runtime,
                                              attempted_baselines=measured_baselines, certified_baselines=done_baselines,
                                              **historic_runtime), lower_bounds=dict(G3=g3_bound, G4=g4_bound),
                  bottleneck=bottleneck, sorted_reference=references, correctness_supplements=supplements)
    (HERE / 'gate_summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=status, gates=gates, online_sealed_cases=len(cases)), indent=2), flush=True)


if __name__ == '__main__':
    main()

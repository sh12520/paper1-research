"""Compare sealed depth-two regressions to archived exact FLAT evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from audit_common import (HERE, ROOT, csv_rows, digest, distribution, markdown_table,
                          prior_comparator, read_json, sealed_payloads, write_csv,
                          write_json, write_report)

TOP_K = (10,50,100,500)
BUDGETS = (100,500,5000)


def same_bits(left,right):
    return struct.pack('>d',float(left))==struct.pack('>d',float(right))


def report_compare(path, fresh_graph):
    seal,cases,seal_sha = sealed_payloads(path)
    legacy_dir = ROOT/'results/grammar_dedup'
    old_path = legacy_dir/'correctness'/'search_seal.json'
    _,old,old_sha = sealed_payloads(old_path,archive_root=legacy_dir)
    archived = read_json(old_path.parent/'offline'/'correctness_evidence.json')
    if (archived['instance_count']!=96 or archived.get('performance_allowed') is not True
            or archived['seal_sha256']!=old_sha):
        raise ValueError('depth-two predecessor has no matching exact FLAT clearance')
    for label,name in (('topk','topk_correctness.csv'),('protocol','agreement_correctness.csv')):
        if archived['files_sha256'][label]!=digest((old_path.parent/'offline'/name).read_bytes()):
            raise ValueError('archived depth-two FLAT comparison differs from its clearance digest')
    if set(cases)!=set(old) or len(cases)!=96:
        raise ValueError('depth-two regression requires the entire archived exact 96-query fixed grid')
    rows=[]
    for iid,case in cases.items():
        expected=old[iid]
        if case['serialized_sha256']!=expected['serialized_sha256'] or case['configuration']!=expected['configuration']:
            raise ValueError(f'depth-two regression fixture changed: {iid}')
        for k in TOP_K:
            actual=case.get('topk',[])[:k]
            reference=expected['topk'][:k]
            prefix=min(len(actual),len(reference))
            match=all(a['key']==b['key'] and same_bits(a['score'],b['score']) and a.get('witness')==b.get('witness')
                      for a,b in zip(actual,reference))
            if not match or len(actual)>len(reference):
                status='MISMATCH'
            elif len(actual)==len(reference) and (len(actual)==k or case.get('topk_status')=='COMPLETE'):
                status='MATCH'
            else:
                status='INCOMPLETE'
            rows.append(dict(instance_id=iid,depth=case['configuration']['composition_depth'],check='topk',value=k,
                             archived_length=len(reference),compared_length=prefix,status=status))
        if case.get('protocol') or seal['manifest'].get('mode')=='both':
            for budget in BUDGETS:
                key=str(budget)
                actual=case.get('protocol',{}).get(key)
                reference=expected['protocol'][key]
                if actual is None:
                    status='INCOMPLETE'
                else:
                    fields=('agreement','signature','representative','verification_calls','proposals')
                    n=2*reference['proposals']
                    if (any(actual[f]!=reference[f] for f in fields)
                            or case['history'][:n]!=expected['history'][:n]):
                        status='MISMATCH'
                    else:
                        status='MATCH'
                rows.append(dict(instance_id=iid,depth=case['configuration']['composition_depth'],check='protocol',value=budget,
                                 archived_length=reference['verification_calls'],
                                 compared_length=None if actual is None else actual['verification_calls'],status=status))

    offline=None
    if fresh_graph:
        module,reference_source=prior_comparator()
        slots=read_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
        cohort={row['instance_id']:row for row in csv_rows(ROOT/'results/flat_audit/per_instance.csv')}
        # This opt-in lane is only for a sealed regression worker, with the
        # depth-three online worker also absent. It loads the old depth≤2 graph.
        topk,protocol,loaded=module.compare_offline(cases,slots,cohort)
        direct=[row for row in topk+protocol if row['instance_id'] in cases]
        n=len(cases)
        expected_checks=len(TOP_K)*n + (len(BUDGETS)*n if seal['manifest'].get('mode')=='both' else 0)
        applicable=[row for row in direct if 'k' in row or seal['manifest'].get('mode')=='both']
        offline=dict(compared=len(applicable),source_sha256=reference_source,graph_loaded=loaded,
                     exact=sum(row['status']=='MATCH' for row in applicable),
                     mismatches=sum(row['status']=='MISMATCH' for row in applicable),
                     pass_checks=len(applicable)==expected_checks and all(row['status']=='MATCH' for row in applicable))

    pass_checks=all(row['status']=='MATCH' for row in rows) and (offline is None or offline['pass_checks'])
    observations=distribution(case.get('topk_metrics',{}).get('wall_s') for case in cases.values())
    prior_observations=distribution(old[iid].get('topk_metrics',{}).get('wall_s') for iid in cases)
    output=dict(status='PASS' if pass_checks else 'FAIL',query_count=len(cases),seal_sha256=seal_sha,
                archived_seal_sha256=old_sha,archived_reference_evidence_sha256=digest(
                    (old_path.parent/'offline'/'correctness_evidence.json').read_bytes()),
                topk_and_protocol_checks=len(rows),exact_matches=sum(row['status']=='MATCH' for row in rows),
                mismatches=sum(row['status']=='MISMATCH' for row in rows),
                incomplete=sum(row['status']=='INCOMPLETE' for row in rows),
                direct_flat=offline,measurements=observations,archived_measurements_same_ids=prior_observations)
    write_csv(HERE/'depth2_regression.csv',tuple(rows[0]),rows)
    write_json(HERE/'depth2_regression.json',output)
    grouped=[]
    for check in ('topk','protocol'):
        for value in (TOP_K if check=='topk' else BUDGETS):
            subset=[row for row in rows if row['check']==check and row['value']==value]
            if subset:
                grouped.append((check,value,len(subset),sum(r['status']=='MATCH' for r in subset),
                                sum(r['status']=='MISMATCH' for r in subset),sum(r['status']=='INCOMPLETE' for r in subset)))
    write_report(ROOT/'DEPTH2_REGRESSION_REPORT.md',[
        '# Depth≤2 regression against the frozen FLAT comparator', '',f'**{output["status"]}** on {len(cases)} sealed queries.', '',
        'The regression compares compact signature order, binary64 score bits and canonical witnesses with the '
        'previous graph-free deduplication replay. That archived replay passed the independent FLAT comparisons '
        'on all 96 fixed existing cases. Both seals and the prior reference CSV hashes were checked before use.', '',
        *markdown_table(('Check', 'K or budget', 'Compared fixtures', 'Exact', 'Mismatch', 'Incomplete'),grouped), '',
        *( ['The independent original FLAT graph comparator was also rerun offline after both online workers exited. '
            f'It recorded {offline["exact"]}/{offline["compared"]} exact comparisons.', ''] if offline else []),
        'Online regression uses existing serialized development queries and the original structural ranking domain. '
        'Its goal is the depth-two score and order check. The archive already contains separate exact agreement checks. '
        'Median and p95 search seconds are reported descriptively on the same fixed IDs.', '',
        *markdown_table(('Lane','n','Median s','p95 s'),[
            (label,m['n'],m['median'],m['p95']) for label,m in
            (('Archived deduplication',prior_observations),('Current depth≤2 regression',observations))]), '',
    ])
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',type=Path,required=True)
    parser.add_argument('--fresh-flat',action='store_true')
    args=parser.parse_args()
    result=report_compare(args.seal,args.fresh_flat)
    print(result,flush=True)
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':
    raise SystemExit(main())

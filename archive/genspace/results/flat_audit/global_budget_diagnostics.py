"""Combine historical budget outcomes with post-hoc GLOBAL ranks."""
import csv
import json
from pathlib import Path

P = Path(__file__).resolve().parent
with (P/'scaling_record_extract.csv').open(encoding='utf8', newline='') as f:
    rows = [r for r in csv.DictReader(f) if r['recoverable'] == '1']
with (P/'rank_topk_records.jsonl').open(encoding='utf8') as f:
    ranks = {r['instance_id']: r for r in map(json.loads, f)}
if len(rows) != 842 or len(ranks) != 842:
    raise ValueError('incomplete target cohort')

budgets = (100, 500, 5000)
historical = P.parent / 'method_dev_v1' / 'run_protocol_fixed'
for row in rows:
    instance_id = row['instance_id']
    rank = ranks[instance_id]
    record = json.loads((historical / instance_id / 'record.json').read_text(encoding='utf8'))
    checkpoints = record['methods']['GLOBAL-FREQUENCY']['budgets']
    final = checkpoints['10000']
    if rank['global_agreement'] != final['agreement']:
        raise ValueError('GLOBAL replay outcome differs from original: ' + instance_id)
    for budget in budgets:
        checkpoint = checkpoints[str(budget)]
        if (row[f'global_{budget}_agreement'] == '1') != checkpoint['agreement']:
            raise ValueError('GLOBAL extracted outcome differs from original: ' + instance_id)
        if checkpoint['agreement']:
            first = rank['global_first_mutual_actual_verification_ordinal']
            selected = rank['global_selected_actual_verification_ordinal']
            if (checkpoint['class_id'] != final['class_id'] or first is None or
                    first != selected or first + 27 > checkpoint['verification_calls']):
                raise ValueError('GLOBAL first mutually acceptable candidate differs from the checkpoint selection: ' + instance_id)

def quantile(values, q):
    a = sorted(values)
    if not a:
        return None
    i = (len(a)-1)*q
    lo = int(i); hi = min(lo+1, len(a)-1)
    return a[lo] + (a[hi]-a[lo])*(i-lo)

out = []
for budget in budgets:
    subset = [r for r in rows if r[f'global_{budget}_agreement'] == '1']
    ordinal = [ranks[r['instance_id']]['global_first_mutual_actual_verification_ordinal'] for r in subset]
    if any(x is None for x in ordinal):
        raise ValueError('missing post-hoc first-mutual ordinal for a successful run')
    grouped = [ranks[r['instance_id']]['global_selected_full_grouped_rank'] for r in subset]
    off = sum(bool(int(r[f'global_{budget}_selected_group_mask']) & 8) for r in subset)
    flat = [r for r in rows if r[f'flat_{budget}_agreement'] == '1']
    fids = {r['instance_id'] for r in flat}; gids = {r['instance_id'] for r in subset}
    out.append({'budget': budget, 'successful': len(subset), 'offload_footprint': off,
                'offload_share': off/len(subset),
                'first_mutual_ordinal_median': quantile(ordinal,.5),
                'first_mutual_ordinal_p95': quantile(ordinal,.95),
                'first_mutual_ordinal_p99': quantile(ordinal,.99),
                'first_mutual_ordinal_max': max(ordinal),
                'selected_grouped_rank_median': quantile(grouped,.5),
                'selected_grouped_rank_p95': quantile(grouped,.95),
                'both': len(fids & gids), 'flat_only': len(fids-gids),
                'global_only': len(gids-fids), 'neither': 842-len(fids|gids)})
with (P/'global_budget_diagnostics.csv').open('w', encoding='utf8', newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(json.dumps(out, indent=2))

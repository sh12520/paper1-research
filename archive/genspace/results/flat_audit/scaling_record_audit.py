"""Read-only extraction from existing method records; no benchmark imports or seeds."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'results' / 'method_dev_v1' / 'run_protocol_fixed'
OUTPUT = ROOT / 'results' / 'flat_audit' / 'scaling_record_extract.csv'

rows = []
digest = hashlib.sha256()
for path in sorted(DATA.glob('*/record.json')):
    raw = path.read_bytes()
    digest.update(path.parent.name.encode('utf-8') + b'\0' + hashlib.sha256(raw).digest())
    entry = json.loads(raw)
    row = {'instance_id': entry['instance_id'], 'family': entry['family'],
           'recoverable': int(entry['oracle']['recoverable']),
           'o1_candidate_count': entry['oracle']['O1_candidate_count']}
    for method, prefix in [('FLAT-FEASIBILITY', 'flat'), ('GLOBAL-FREQUENCY', 'global')]:
        budgets = entry['methods'][method]['budgets']
        for budget in ('100', '500', '5000'):
            record = budgets[budget]
            row[f'{prefix}_{budget}_agreement'] = int(record['agreement'])
            row[f'{prefix}_{budget}_selected_group_mask'] = record['selected_group_mask']
        record = budgets['5000']
        for field in ('b2_agreement', 'public_ranked_count', 'verification_calls',
                      'public_probe_count', 'b2_proxy_count'):
            row[f'{prefix}_{field}'] = record[field]
    rows.append(row)
assert len(rows) == 1920 and sum(x['recoverable'] for x in rows) == 842
with OUTPUT.open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f'input aggregate sha256: {digest.hexdigest()}')
print(f'output sha256: {hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}')

import csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'results/flat_audit'
rows=list(csv.DictReader((OUT/'family_summary.csv').open(encoding='utf8')))
items=[]
for population in ('TARGET','ALL'):
 r=next(x for x in rows if x['population']==population and x['family']=='ALL')
 def pair(k):return f"{float(r[k+'_median']):,.0f} / {float(r[k+'_p95']):,.0f}"
 items.append('| '+('B2 deadlock / O1 agreement' if population=='TARGET' else 'All')+f" | {r['n']} | {pair('conditioned_structural_method_eligible')} | {pair('flat_structural_score_evaluations')} | {pair('flat_exact_verification_calls')} |")
table='| Cohort | N | Public conditioned candidates median / p95 | Actual scored median / p95 | Exact calls median / p95 |\n|---|---:|---:|---:|---:|\n'+'\n'.join(items)
text=(OUT/'baseline_report_template.md').read_text(encoding='utf-8-sig').replace('@@ACCOUNTING_TABLE@@',table)
text=text.replace('@@INTERPRETATION@@','The current implementation scans the whole rich-graph metadata before B2 and again when B2 fails. The large p95 conditional score and sorting workload exposes an engineering scaling problem; the lower median and variation across depth/availability require the disaggregated timings in the runtime report before judging whether the full scan dominates typical latency. This audit does not establish that scanning is necessary to obtain FLAT’s agreements.')
(ROOT/'FLAT_BASELINE_AUDIT_REPORT.md').write_text(text,encoding='utf8')

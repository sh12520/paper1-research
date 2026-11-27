"""Summarize the separately collected timing sample; no execution/replay."""
import sys
sys.dont_write_bytecode=True
import csv,json,statistics
from pathlib import Path
import numpy as np

here=Path(__file__).resolve().parent
root=here.parents[1]
rows=list(csv.DictReader((here/'runtime_main.csv').open(encoding='utf8',newline='')))
phases=['public_view_setup','plan_public_setup','conditioning','feature_calculation','proxy_score_calculation',
        'sorting_topk','mechanism_probes','stage_construction','exact_verification','bilateral_protocol',
        'representative_reconstruction','residual','total']
if len(rows)!=192 or len({r['instance_id'] for r in rows})!=96:
    raise ValueError('expected 96 instances and two methods')
if any(r['output_equality']!='True' or r['plan_equality'] not in ('PASS','NOT_APPLICABLE_B2_STOP') for r in rows):
    raise ValueError('replay equality failed')
def describe(xs):
    x=np.asarray(xs,dtype=float)
    return {'n':len(x),'median':float(np.median(x)),'p90':float(np.quantile(x,.90)),
            'p95':float(np.quantile(x,.95)),'mean':float(np.mean(x))}
results={}
for cohort in ('all','recoverable'):
    results[cohort]={}
    for method in ('FLAT-FEASIBILITY','DG-PCE'):
        selected=[r for r in rows if r['method']==method and (cohort=='all' or r['target']=='True')]
        denominator=sum(float(r['total']) for r in selected)
        results[cohort][method]={p:{**describe([float(r[p]) for r in selected]),
                                  'percent_of_total':100*sum(float(r[p]) for r in selected)/denominator}
                                 for p in phases}
        results[cohort][method]['plan_checks']=sum(r['plan_equality']=='PASS' for r in selected)
(here/'runtime_summary.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
lines=['# V1 runtime decomposition — development diagnostics','',
       'Measured 96 existing PILOT serialized instances, one seed-index 0 per public configuration; '
       'no instance or seed generation. Every timed method run was checked against the historical '
       'history prefix through the B=5,000 checkpoint and all non-timing fields for each checkpoint '
       'through 5,000, including offline uA/uN/Nash. '
       'For every expansion run, timed candidate order and public-plan fields were separately compared '
       'with the unmodified original make_plan. Timing reflects the instrumented implementation, '
       'so wrappers add overhead; the residual includes instrumentation overhead and unclassified work.', '',
       'Online timing starts immediately before public view, public compatibility and private agent setup, '
       'and ends after runtime.run returns. It excludes instance file reads/deserialization, semantic '
       'library load/basis initialization, hook construction, offline witness re-verification, '
       'and the independent repeat of original public ranking. Exact verification is public V1–V4; '
       'bilateral protocol covers local private decisions. Mechanism probes include their own proxy '
       'features and scoring. Stage construction includes DG group ordering and quota-compatible '
       'candidate grouping. No full-space private evaluator is part of online timing.', '',
       'The replay uses the original V1 fixed checkpoints through stop budget 5,000; a method can '
       'terminate earlier at agreement or exhaustion. Values in seconds. '
       'Percentages are sums of each exclusive phase divided by sum of total times, '
       'not an average of per-instance percentages. All-config cohort includes early B2 exits; '
       'recoverable cohort is the sampled B2-no-agreement/full-O1-agreement subset.', '']
for cohort in ('all','recoverable'):
    for method in ('FLAT-FEASIBILITY','DG-PCE'):
        d=results[cohort][method]
        lines += [f"## {cohort}: {method} (n={d['total']['n']}; public plan equality checks={d['plan_checks']})",'',
                  '| Phase | Median | p90 | p95 | Mean | Share of total |',
                  '|---|---:|---:|---:|---:|---:|']
        for p in phases:
            q=d[p];lines.append(f"| {p} | {q['median']:.6f} | {q['p90']:.6f} | {q['p95']:.6f} | {q['mean']:.6f} | {q['percent_of_total']:.2f}% |")
        lines.append('')
memory=json.loads((here/'runtime_main_memory.json').read_text(encoding='utf8'))
lines += ['Memory telemetry (sampled every 250 ms): `'+json.dumps(memory,sort_keys=True)+'`.','',
          'These measurements are development engineering diagnostics, not confirmation evidence.']
(root/'METHOD_RUNTIME_DECOMPOSITION.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps(results,indent=2))

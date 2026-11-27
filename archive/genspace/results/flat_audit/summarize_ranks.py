"""Summarize exact offline rank/Top-K reconstructions on the 842 targets."""
import sys
sys.dont_write_bytecode=True
import collections,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
rows=[json.loads(x) for x in (ROOT/'results/flat_audit/rank_topk_records.jsonl').read_text(encoding='utf8').splitlines()]
if len(rows)!=842 or len({r['instance_id'] for r in rows})!=842:raise ValueError('expected exactly 842 unique targets')
def dist(rs,field):
    x=[r[field] for r in rs if r[field] is not None]
    if not x:return 'NA'
    return ', '.join(f'{z:g}' for z in np.percentile(x,[50,75,90,95,99,100]))+f' (n={len(x)})'
def label(mask):
    return '+'.join(n for b,n in [(1,'C'),(2,'D'),(4,'P'),(8,'O')] if int(mask)&b) or 'STATIC'
families=['ALL','F1','F2','F3','F4']
parts={f:[r for r in rows if f=='ALL' or r['family']==f] for f in families}
lines=['# FLAT successful-rank analysis','',
 'Post-hoc developmental diagnostics on the 842 existing B2-deadlock / full-O1-agreement PILOT instances. The public ordering was reconstructed before private acceptance was inspected; none of these offline results is available online or fed back to either method. These ranks are not confirmation evidence.', '',
 'Ranks are one-based in the structural candidate ordering, after the 27 B2 verifications. For each target FLAT did find an agreement; therefore scanning through its verified prefix suffices to establish the exact first public-feasible and first mutually acceptable ranks. `best verified Nash` means the best among the candidates actually verified by FLAT, not the complete oracle space.', '',
 'Percentiles: median / p75 / p90 / p95 / p99 / max, NumPy linear interpolation.','',
 '| Family | First public feasible | First mutually acceptable | FLAT selected | Best Nash among actually verified agreements |',
 '|---|---:|---:|---:|---:|']
for f,rs in parts.items():
 lines.append('| '+f+' | '+' | '.join(dist(rs,k) for k in ('rank_first_public_feasible','rank_first_mutually_acceptable','rank_selected_agreement','rank_best_nash_actually_verified'))+' |')
lines+=['','GLOBAL has an untruncated grouped ranking and a different quota-truncated verification sequence. Its selected candidate’s grouped rank and actual structural verification ordinal, and the first mutually acceptable candidate found in the actual verification sequence, are below. Their totals exclude 27 B2 checks; a failed run can have no selected/first-success rank.','',
 '| Family | GLOBAL selected grouped rank | GLOBAL selected actual ordinal | First mutual actual ordinal |', '|---|---:|---:|---:|']
for f,rs in parts.items():
 lines.append('| '+f+' | '+' | '.join(dist(rs,k) for k in ('global_selected_full_grouped_rank','global_selected_actual_verification_ordinal','global_first_mutual_actual_verification_ordinal'))+' |')
(ROOT/'FLAT_SUCCESS_RANK_ANALYSIS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

lines=['# FLAT top-K composition', '',
 'Offline descriptive diagnostics on 842 recoverable development instances, using the original public-only FLAT score and exact V1–V4 and private acceptance checks strictly after ordering. K may be clipped to available candidates; percentages pool candidate appearances within each family (one instance may contribute multiple candidates). C/D/P/O describe whole-contract capability-group footprints, which need not equal behavior-derived mechanism labels. `O` percentage means footprint includes O, not necessarily a distinct realized behavioral label.', '',
 'Proxy public violation, margin, mean quality and capability cost are the original public-ranking proxy quantities; they omit exact hard checks and capability resource surcharge. Complexity is the number of capability groups. Actual public feasibility and mutual acceptance are exact, post-hoc checks.', '']
for f,rs in parts.items():
 lines+=['## '+f, '', '| K | Candidates | OFFLOAD footprint | Public-feasible | Mutual accepted | Mean violation | Mean margin | Mean cost | Mean group complexity |', '|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 agg={}
 for k in ('10','50','100','500'):
  items=[r['topk'][k] for r in rs];n=sum(x['n'] for x in items); masks=collections.Counter();quality=collections.Counter()
  for x in items:masks.update(x['group_masks']);quality.update(x['quality'])
  agg[k]=(masks,quality,n)
  def p(key):return sum(x[key] for x in items)/n
  lines.append(f"| {k} | {n} | {p('offload'):.4%} | {p('public_feasible'):.4%} | {p('mutually_acceptable'):.4%} | {p('public_violation_sum'):.6f} | {p('feasibility_margin_sum'):.6f} | {p('capability_cost_sum'):.6f} | {p('complexity_sum'):.6f} |")
 lines+=['', 'Mechanism footprint composition (candidate counts and within-K percentages):','']
 for k,(masks,quality,n) in agg.items():
  lines.append('- K='+k+': '+', '.join(f'{label(mask)} {cnt} ({cnt/n:.2%})' for mask,cnt in sorted(masks.items(),key=lambda x:int(x[0]))))
 lines+=['','Horizon/state mean quality proxy distribution (inactive cells contribute zero) (candidate counts):','']
 for k,(masks,quality,n) in agg.items():
  lines.append('- K='+k+': '+', '.join(f'{value}: {cnt}' for value,cnt in sorted(quality.items(),key=lambda x:float(x[0]))))
 lines.append('')
(ROOT/'FLAT_TOPK_COMPOSITION.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('wrote rank and top-K reports for',len(rows),'targets')

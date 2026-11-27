"""Plot existing complete development summaries without statistical inference."""
import csv,json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parent
def main():
    gate=json.loads((BASE/'development_gate.json').read_text(encoding='utf8'))
    if gate.get('development_only') is not True:raise ValueError('development gate evidence required')
    provenance=json.loads((BASE/'report_provenance.json').read_text(encoding='utf8'))
    run=(BASE/'run_protocol_fixed').resolve()
    if Path(provenance.get('run_directory','')).resolve()!=run:raise ValueError('plot summary not bound to protocol-fixed run')
    manifest=json.loads((run/'run_manifest.json').read_text(encoding='utf8'))
    digest=hashlib.sha256((json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()
    if digest!=provenance.get('run_manifest_sha256'):raise ValueError('plot manifest mismatch')
    with (BASE/'summary.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    methods=('B2','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY','SINGLETON-ONLY','DG-PCE','FULL-O1')
    colors={'B2':'#1f77b4','RANDOM-BUDGET':'#ff7f0e','FLAT-FEASIBILITY':'#2ca02c','GLOBAL-FREQUENCY':'#d62728','SINGLETON-ONLY':'#9467bd','DG-PCE':'#8c564b','FULL-O1':'#e377c2'}
    budgets=(100,500,1000,5000,10000)
    charts=(('orc','oracle_recovery_coverage','Oracle recovery coverage', 'RECOVERABLE'),('nash_gap','nash_gap_mean','Mean Nash gap (agreements only)', 'RECOVERABLE'),('runtime','runtime_seconds_median','Median runtime per instance (seconds)', 'ALL'))
    dest=BASE/'figures';dest.mkdir(exist_ok=True)
    for name,field,ylabel,cohort in charts:
        fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
        for method in methods:
            selected={int(r['budget']):r for r in rows if r['method']==method and r['cohort']==cohort}
            if set(selected)!=set(budgets):raise ValueError('incomplete plot data')
            ys=[float(selected[b][field]) if selected[b][field] else float('nan') for b in budgets]
            if all(v!=v for v in ys):continue
            label=method+' (historical, not comparable)' if method=='FULL-O1' and name=='runtime' else method
            ax.plot(budgets,ys,marker='o',label=label,color=colors[method],linewidth=2 if method=='DG-PCE' else 1.2)
        ax.set_xscale('log');ax.set_xticks(budgets,labels=[str(b) for b in budgets]);ax.set_xlabel('Budget: exact candidate verification calls');ax.set_ylabel(ylabel);ax.grid(alpha=.25)
        ax.legend(fontsize=7,ncol=2);fig.suptitle('Development data only; not confirmation evidence');fig.savefig(dest/('budget_'+name+'.png'),dpi=180);fig.savefig(dest/('budget_'+name+'.pdf'));plt.close(fig)
    (BASE/'figure-catalog.md').write_text('# Development budget curves\n\n- `figures/budget_orc.pdf`: ORC against the 842 oracle-recoverable B2 deadlocks.\n- `figures/budget_nash_gap.pdf`: mean gap conditional on an agreement; consult summary.csv for varying denominators.\n- `figures/budget_runtime.pdf`: median per-instance recorded runtime; shared graph loading is not included. FULL-O1 line uses its historical PILOT stage time, excludes B2 and is not directly comparable to development timings.\n\nFULL-O1 is an unlimited offline reference. No confidence intervals or significance claims are shown.\n',encoding='utf8')
if __name__=='__main__':main()

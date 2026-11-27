"""Descriptive figures from existing audit files; no experiment is run."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
DEST = HERE / 'figures'
DEST.mkdir(exist_ok=True)

with (HERE / 'scaling_record_extract.csv').open(encoding='utf8', newline='') as f:
    rows = [r for r in csv.DictReader(f) if r['recoverable'] == '1']
if len(rows) != 842:
    raise ValueError('target population must have 842 rows')
with (HERE / 'rank_topk_records.jsonl').open(encoding='utf8') as f:
    ranks = [json.loads(line) for line in f if line.strip()]
if len(ranks) != 842 or len({x['instance_id'] for x in ranks}) != 842:
    raise ValueError('complete unique rank audit required')

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'figure.dpi': 140})
fig, ax = plt.subplots(figsize=(7.5, 4.4), layout='constrained')
for field, label, color in [('flat_public_ranked_count', 'Structural candidates scored', '#145c9e'),
                            ('flat_verification_calls', 'Exact verification calls (incl. B2)', '#c46b24')]:
    a = np.sort(np.array([int(r[field]) for r in rows]))
    ax.step(a, np.arange(1, len(a)+1)/len(a), where='post', label=label, color=color)
ax.axvline(1394064, color='#666', linestyle='--', label='Full-graph metadata rows')
ax.set(xscale='log', xlim=(20, 2e6), ylim=(0, 1.02),
       xlabel='Number of candidates / metadata rows (log scale)',
       ylabel='Empirical fraction of target instances',
       title='FLAT work is not captured by exact calls alone')
ax.grid(axis='y', alpha=.2)
ax.legend(loc='lower right', fontsize=8)
for ext in ('png', 'pdf'):
    fig.savefig(DEST / ('figure_01_candidate_work.' + ext))
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 4.4), layout='constrained')
for family, color in zip(('F1', 'F2', 'F3', 'F4'), ('#145c9e', '#ba5525', '#3a8b5d', '#8d5899')):
    a = np.sort([r['rank_first_mutually_acceptable'] for r in ranks if r['family'] == family])
    if len(a) == 0 or a[0] is None:
        raise ValueError('missing first-mutual rank')
    ax.step(a, np.arange(1, len(a)+1)/len(a), where='post', label=f'{family} (n={len(a)})', color=color)
ax.set(xscale='log', ylim=(0, 1.02), xlabel='First mutually acceptable rank, 1-based (log scale)',
       ylabel='Empirical fraction within family', title='First successful rank in the offline FLAT ordering')
ax.grid(axis='y', alpha=.2)
ax.legend(loc='lower right', fontsize=8)
for ext in ('png', 'pdf'):
    fig.savefig(DEST / ('figure_02_first_mutual_rank.' + ext))
plt.close(fig)
print('two figures saved from 842 completed target records')

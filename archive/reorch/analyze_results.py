"""Summarize paired outcomes and write a prespecified conservative gate."""
import argparse
import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ('ALL_SEQUENTIAL', 'ALL_CONCURRENT', 'STATIC_CLUSTER', 'OPTIMAL_STATIC_PARTITION')
ORACLE = 'RUNTIME_REPARTITION_ORACLE'
METRICS = ('welfare', 'completion_rate', 'agreement_A', 'agreement_B', 'agreement_C',
           'agreement_D', 'deadline_miss_rate', 'wall_time', 'rounds', 'messages',
           'rejected_at_commit')
KEYS = ('family', 'strength', 'tightness', 'kappa')


def ci(values, seed=137, draws=2000):
    if not values:
        return (float('nan'), float('nan'))
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(sum(rng.choices(values, k=n)) / n for _ in range(draws))
    return samples[int(.025 * draws)], samples[int(.975 * draws)]


def plot(data, path):
    # SVG is portable and renders without a plotting-library dependency.
    w, h = 860, 470
    families = ('STATIC_COUPLING', 'COUPLING_SHIFT')
    colors = ('#64748b', '#d45a32')
    curves = []
    for family in families:
        curves.append([statistics.mean(v['mean'] for k,v in data.items()
                                      if k[0] == family and float(k[3]) == x)
                       for x in (0, .15, .30, .45)])
    vals = [v for curve in curves for v in curve] + [0.0]
    low, high = min(vals), max(vals)
    pad = max((high-low)*.2, .02)
    low -= pad; high += pad
    xs = [110, 310, 510, 710]
    def y(v): return 360 - (v-low)/(high-low)*280
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<text x="55" y="35" font-family="sans-serif" font-size="20">Oracle vs best static: mean paired welfare difference</text>',
           '<text x="55" y="58" font-family="sans-serif" font-size="13" fill="#475569">Averaged across deadline and shift-strength settings</text>',
           f'<line x1="90" y1="{y(0):.1f}" x2="750" y2="{y(0):.1f}" stroke="#94a3b8" stroke-dasharray="5 4"/>',
           '<line x1="90" y1="80" x2="90" y2="360" stroke="#334155"/><line x1="90" y1="360" x2="750" y2="360" stroke="#334155"/>']
    for i in range(5):
        v = low + (high-low)*i/4
        out.append(f'<text x="80" y="{y(v)+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{v:.3f}</text>')
    for x,label in zip(xs,('0','0.15','0.30','0.45')):
        out.append(f'<text x="{x}" y="382" text-anchor="middle" font-family="sans-serif" font-size="13">{label}</text>')
    for family,color,curve in zip(families,colors,curves):
        points = ' '.join(f'{x},{y(v):.1f}' for x,v in zip(xs,curve))
        out.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x,v in zip(xs,curve): out.append(f'<circle cx="{x}" cy="{y(v):.1f}" r="4" fill="{color}"/>')
    out += ['<text x="420" y="414" text-anchor="middle" font-family="sans-serif" font-size="14">Coordination cost κ</text>',
            '<text x="110" y="448" font-family="sans-serif" font-size="13" fill="#64748b">● STATIC_COUPLING</text>',
            '<text x="310" y="448" font-family="sans-serif" font-size="13" fill="#d45a32">● COUPLING_SHIFT</text>', '</svg>']
    path.write_text('\n'.join(out), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT/'results'/'raw_results.csv')
    p.add_argument('--output-dir', type=Path, default=ROOT/'results')
    a = p.parse_args()
    grouped = defaultdict(lambda: defaultdict(dict))
    with a.input.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            key = tuple(row[k] for k in KEYS)
            seed = int(row['seed']); method = row['method']
            if seed in grouped[key][method]: raise ValueError(f'duplicate {key} {method} {seed}')
            grouped[key][method][seed] = row
    if not grouped: raise ValueError('empty input')
    a.output_dir.mkdir(exist_ok=True, parents=True)
    with (a.output_dir/'summary.csv').open('w', newline='', encoding='utf-8') as f:
        fields = list(KEYS) + ['method','n'] + [m+'_mean' for m in METRICS]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for key, methods in sorted(grouped.items()):
            for method, seeds in sorted(methods.items()):
                item = dict(zip(KEYS,key)); item.update(method=method,n=len(seeds))
                item.update({m+'_mean': statistics.mean(float(r[m]) for r in seeds.values()) for m in METRICS})
                writer.writerow(item)
    effects = {}; family_seed = defaultdict(lambda: defaultdict(list))
    for key, methods in grouped.items():
        if any(m not in methods for m in (*STATIC, ORACLE)): raise ValueError(f'missing methods for {key}')
        common = set(methods[ORACLE])
        for m in STATIC: common &= set(methods[m])
        if any(set(methods[m]) != common for m in (*STATIC, ORACLE)):
            raise ValueError(f'unpaired seeds for {key}')
        best = max(STATIC, key=lambda m: statistics.mean(float(r['welfare']) for r in methods[m].values()))
        diffs = {s: float(methods[ORACLE][s]['welfare']) - float(methods[best][s]['welfare']) for s in sorted(common)}
        values = list(diffs.values()); lo, hi = ci(values)
        effects[key] = dict(best=best,mean=statistics.mean(values),lo=lo,hi=hi,
                            win=sum(x>1e-12 for x in values)/len(values))
        for seed,v in diffs.items(): family_seed[key[0]][seed].append(v)
    with (a.output_dir/'paired_effects.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=list(KEYS)+['best','mean','lo','hi','win']); writer.writeheader()
        for key,v in sorted(effects.items()): writer.writerow(dict(zip(KEYS,key)) | v)
    shift = [v for k,v in effects.items() if k[0]=='COUPLING_SHIFT']
    if not shift or not family_seed['STATIC_COUPLING']: raise ValueError('both experiment families are required')
    # Gate is deliberately demanding: at least 75% of shift settings have a
    # positive bootstrap CI, >0.04 welfare advantage, and >55% seed wins.
    qualified = lambda v: v['lo'] > 0 and v['mean'] > .04 and v['win'] > .55
    frac = sum(qualified(v) for v in shift)/len(shift)
    test_a = frac >= .75
    common_seeds = sorted(set(family_seed['COUPLING_SHIFT']) & set(family_seed['STATIC_COUPLING']))
    if not common_seeds: raise ValueError('families must share seeds')
    paired_family = [statistics.mean(family_seed['COUPLING_SHIFT'][s])-statistics.mean(family_seed['STATIC_COUPLING'][s]) for s in common_seeds]
    b_lo,b_hi=ci(paired_family); b_mean=statistics.mean(paired_family)
    shift_seed_means = [statistics.mean(family_seed['COUPLING_SHIFT'][s]) for s in common_seeds]
    shift_mean = statistics.mean(shift_seed_means)
    control_mean = statistics.mean(statistics.mean(family_seed['STATIC_COUPLING'][s]) for s in common_seeds)
    shift_lo, _ = ci(shift_seed_means)
    test_b = b_lo > 0 and b_mean > .04 and shift_mean > .04 and shift_lo > 0
    # Four adjacent cells form a 2x2 block of strength × deadline at a fixed κ.
    strengths=('weak','medium','strong'); deadlines=('loose','medium','tight')
    blocks=0
    for kap in ('0.0','0.15','0.3','0.45'):
        for i in range(2):
            for j in range(2):
                keys=[('COUPLING_SHIFT',s,d,kap) for s in strengths[i:i+2] for d in deadlines[j:j+2]]
                if all(k in effects and qualified(effects[k]) for k in keys): blocks+=1
    positive_seed_rate=sum(statistics.mean(family_seed['COUPLING_SHIFT'][s])>0 for s in common_seeds)/len(common_seeds)
    test_c=blocks>=1 and positive_seed_rate>=.60
    result='REORCH_FAILURE_CASE_SURVIVES' if test_a and test_b and test_c else 'REORCH_GAP_WEAK'
    report = (f'# GATE REPORT\n\nA. {"是" if test_a else "否"}：COUPLING_SHIFT 中 {frac:.1%} 的配置满足预设稳定优势标准。\n\n'
              f'B. {"是" if test_b else "否"}：shift 中平均差值为 {shift_mean:.4f}，其 95% 区间下界为 {shift_lo:.4f}；static 中平均差值为 {control_mean:.4f}；两 family 的配对平均差值之差为 {b_mean:.4f}，95% 区间 [{b_lo:.4f}, {b_hi:.4f}]。\n\n'
              f'C. {"是" if test_c else "否"}：相邻参数 2×2 区块有 {blocks} 个通过，{positive_seed_rate:.1%} 的种子跨 shift 配置平均差值为正。\n\n'
              f'D–E. **{result}**\n\n'
              '判定口径：每个配置以样本平均福利选取最佳静态基线，按共同种子配对；稳定优势要求平均差 > 0.04、95% bootstrap 区间下界 > 0、种子胜率 > 55%，且至少 75% 的 shift 配置满足。B 要求 shift 的平均优势及其相对另一 family 的差值均 > 0.04 且各自区间下界 > 0；C 要求存在通过标准的相邻 2×2 区块，且跨配置种子平均胜率 ≥ 60%。该诊断 policy 不保证理论上界。\n')
    (ROOT/'GATE_REPORT.md').write_text(report, encoding='utf-8')
    (ROOT/'plots').mkdir(exist_ok=True)
    plot(effects, ROOT/'plots'/'welfare_gap.svg')
    print(report)


if __name__ == '__main__': main()

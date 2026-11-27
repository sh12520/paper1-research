"""Run the full paired experiment. No third-party Python packages required."""
import argparse
import csv
import itertools
import multiprocessing as mp
import os
from pathlib import Path

from config import generate_instance
from negotiation_engine import simulate

ROOT = Path(__file__).resolve().parent
METHODS = ('ALL_SEQUENTIAL', 'ALL_CONCURRENT', 'STATIC_CLUSTER',
           'OPTIMAL_STATIC_PARTITION', 'ONLINE_SEQUENTIAL_RESCHEDULE',
           'RUNTIME_REPARTITION_ORACLE')


def run_one(job):
    family, strength, tightness, kappa, seed = job
    instance = generate_instance(seed, family, strength, tightness)
    rows = []
    for method in METHODS:
        # Fresh instance protects common random inputs even if an engine mutates state.
        instance = generate_instance(seed, family, strength, tightness)
        result = simulate(instance, method, kappa)
        result.update(family=family, strength=strength, tightness=tightness,
                      kappa=kappa, seed=seed, method=method)
        rows.append(result)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instances', type=int, default=100)
    p.add_argument('--seed-start', type=int, default=0)
    p.add_argument('--workers', type=int, default=max(1, min(8, os.cpu_count() or 1)))
    p.add_argument('--output', type=Path, default=ROOT / 'results' / 'raw_results.csv')
    args = p.parse_args()
    if args.instances < 1 or args.workers < 1:
        p.error('instances and workers must be positive')
    jobs = itertools.product(('COUPLING_SHIFT', 'STATIC_COUPLING'),
                             ('weak', 'medium', 'strong'), ('loose', 'medium', 'tight'),
                             (0.0, 0.15, 0.30, 0.45),
                             range(args.seed_start, args.seed_start + args.instances))
    total = 2 * 3 * 3 * 4 * args.instances
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as f:
        with mp.Pool(args.workers) as pool:
            writer = None
            for count, rows in enumerate(pool.imap(run_one, jobs, chunksize=4), 1):
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                    writer.writeheader()
                writer.writerows(rows)
                if count % 100 == 0 or count == total:
                    f.flush()
                    print(f'{count}/{total} instances completed', flush=True)


if __name__ == '__main__':
    mp.freeze_support()
    main()

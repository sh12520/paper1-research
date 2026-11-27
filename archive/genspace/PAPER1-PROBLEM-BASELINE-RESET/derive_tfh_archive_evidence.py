"""Read TFH archives and regenerate the reset's descriptive evidence."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import median

PRESUBMISSION = Path(
    'D:/msys2/home/16043/research/TFH03R3-PRESUBMISSION-20261110-150106/data'
)
DATAGRAMS = Path(
    'D:/msys2/home/16043/research/OJCOMS-SUBMISSION-MECH-FINAL-20261112-113922'
    '/artifact/data/OPTIMIZE_MCS_DATAGRAMS.csv.gz'
)
DEADLINE_NS = 10_000_000
APP_START_NS = 400_000_000
BIN_NS = 100_000_000
METHODS = ('OptimizeMcs', 'OptimizeRBs', 'Postponing')
COHORT_FILES = (
    ('TFH02_PRIMARY_RUN_LEVEL_RESULTS.csv', 'C2000'),
    ('TFH02_RECOVERY_RUN_LEVEL_RESULTS.csv', None),
)
RESOURCE_FILE = 'TFH02_RESOURCE_SHAPING_FINAL.csv'
MANIFEST_FILE = 'TFH02_RUN_MANIFEST.csv'
CAPACITY_FILE = 'TFH02_CAPACITY_PROFILES.csv'
RECOVERY_FILE = 'TFH02_DEADLINE_RECOVERY_TIME.csv'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values):
    values = list(values)
    if not values:
        return None
    return dict(n=len(values), median=median(values), min=min(values), max=max(values))


def index(rows, keys):
    by_key = {tuple(row[field] for field in keys): row for row in rows}
    if len(by_key) != len(rows):
        raise ValueError(f'Duplicate archive key {keys}')
    return by_key


def load_cohorts(archive, manifest):
    rows = []
    for filename, fixed_control in COHORT_FILES:
        for source in read_csv(archive / filename):
            run = int(source['rng_run'])
            method, profile = source['method'], source['profile']
            control = fixed_control or source['control']
            for member in (profile, control):
                if manifest[(run, method, member)]['status'] != 'PASS':
                    raise ValueError(f'Non-complete run in cohort source: {member}/{method}/{run}')
            row = dict(
                rng_run=run, method=method, profile=profile, control=control,
                traffic=source['traffic'], cohort=source['cohort'],
                input_guard=source['input_guard'],
            )
            for side, prefix in (
                ('transient', 'T'), ('control', fixed_control or 'control')
            ):
                counts = {
                    key: int(source[f'{prefix}_{key}'])
                    for key in ('generated', 'timely', 'late', 'unobserved')
                }
                generated = counts['generated']
                if generated == 0 or sum(counts[key] for key in (
                    'timely', 'late', 'unobserved'
                )) != generated:
                    raise ValueError(f'Invalid datagram accounting: {row}')
                row.update({f'{side}_{key}': value for key, value in counts.items()})
                row[f'{side}_violation_pp'] = (
                    100 * (counts['late'] + counts['unobserved']) / generated
                )
            row['violation_delta_pp_transient_minus_control'] = (
                row['transient_violation_pp'] - row['control_violation_pp']
            )
            row['full_ip_rx_bytes_transient'] = source.get('T_rx_bytes', '')
            row['full_ip_rx_bytes_control'] = source.get('C2000_rx_bytes', '')
            rows.append(row)
    return sorted(rows, key=lambda row: (
        row['profile'], row['cohort'], row['method'], row['rng_run'], row['traffic']
    ))


def audit_between_modes(cohorts, resources):
    lookup = index(
        [row for row in cohorts if row['cohort'] == 'LOW' and row['control'] == 'C2000'],
        ('profile', 'method', 'rng_run', 'traffic'),
    )
    rows = []
    for profile in ('T1', 'T2'):
        for lhs, rhs in combinations(METHODS, 2):
            for run in range(7, 17):
                for traffic in ('VR', 'CG', 'AR_Video'):
                    left = lookup.get((profile, lhs, run, traffic))
                    right = lookup.get((profile, rhs, run, traffic))
                    if left is None or right is None:
                        continue
                    lhs_resource = resources[(profile, lhs, run)]
                    rhs_resource = resources[(profile, rhs, run)]
                    row = dict(
                        rng_run=run, profile=profile, traffic=traffic,
                        lhs_method=lhs, rhs_method=rhs,
                        lhs_generated=left['transient_generated'],
                        rhs_generated=right['transient_generated'],
                        generated_counts_equal=left['transient_generated'] == right['transient_generated'],
                        lhs_violation_pp=left['transient_violation_pp'],
                        rhs_violation_pp=right['transient_violation_pp'],
                        violation_delta_pp_rhs_minus_lhs=(
                            right['transient_violation_pp'] - left['transient_violation_pp']
                        ),
                        lhs_unobserved=left['transient_unobserved'],
                        rhs_unobserved=right['transient_unobserved'],
                    )
                    for metric, key, factor in (
                        ('modeled_fh_mbit', 'MODELED_FH_BIT_EQUIVALENT_Mbit', 1),
                        ('air_rb_sample_sum', 'air_sum', 1),
                        ('fh_active_p95_mbps', 'fh_active_p95', 1e-6),
                    ):
                        lvalue = float(lhs_resource[key]) * factor
                        rvalue = float(rhs_resource[key]) * factor
                        row[f'lhs_{metric}'] = lvalue
                        row[f'rhs_{metric}'] = rvalue
                        row[f'{metric}_delta_rhs_minus_lhs'] = rvalue - lvalue
                    rows.append(row)
    return rows


def audit_t1_ip_bins(path):
    counts = defaultdict(Counter)
    seen = set()
    with gzip.open(path, mode='rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['profile'] != 'T1':
                continue
            if row['rng_seed'] != '1' or row['method'] != 'OptimizeMcs':
                raise ValueError('Unexpected historical seed or control in datagram archive')
            tx = int(row['tx_time_ns'])
            relative = tx - APP_START_NS
            if not 2_000_000_000 <= relative < 4_000_000_000:
                continue
            key = (row['identity'], row['flow_id'], row['packet_id'])
            if key in seen:
                raise ValueError(f'Duplicate datagram {key}')
            seen.add(key)
            group = counts[(int(row['rng_run']), row['traffic'], relative // BIN_NS)]
            group['generated'] += 1
            if not row['rx_time_ns']:
                status = 'unobserved'
            else:
                delay_ns = int(row['rx_time_ns']) - tx
                if delay_ns < 0:
                    raise ValueError(f'Negative IP delay {key}')
                status = 'timely' if delay_ns <= DEADLINE_NS else 'late'
            group[status] += 1
    return [
        dict(
            rng_run=run, method='OptimizeMcs', profile='T1', traffic=traffic,
            cohort='LOW' if bin_index < 30 else 'RECOVERY-1',
            source_bin_start_ms=bin_index * 100, source_bin_end_ms=(bin_index + 1) * 100,
            generated=group['generated'], timely=group['timely'], late=group['late'],
            unobserved=group['unobserved'],
            zero_timely_delivery=group['generated'] > 0 and group['timely'] == 0,
        )
        for (run, traffic, bin_index), group in sorted(counts.items())
    ]


def grouped(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return groups.items()


def verify_bins(cohorts, bins):
    expected = index(
        [row for row in cohorts if row['profile'] == 'T1' and row['method'] == 'OptimizeMcs'
         and row['cohort'] in ('LOW', 'RECOVERY-1')],
        ('rng_run', 'traffic', 'cohort'),
    )
    observed = dict(grouped(bins, ('rng_run', 'traffic', 'cohort')))
    for key, original in expected.items():
        for column in ('generated', 'timely', 'late', 'unobserved'):
            if sum(row[column] for row in observed[key]) != original[f'transient_{column}']:
                raise ValueError(f'Datagram rebinned count disagrees on {key}: {column}')


def summarize(cohorts, pairs, bins, failures, recovery, capacities):
    cohort_summaries = []
    fields = ('profile', 'control', 'cohort', 'method', 'traffic')
    for key, rows in grouped(cohorts, fields):
        identical_rx = sum(row['full_ip_rx_bytes_transient'] == row['full_ip_rx_bytes_control']
                           for row in rows if row['full_ip_rx_bytes_transient'])
        cohort_summaries.append(dict(
            zip(fields, key),
            paired_rng_runs=[row['rng_run'] for row in rows],
            transient_violation_pp=describe(row['transient_violation_pp'] for row in rows),
            control_violation_pp=describe(row['control_violation_pp'] for row in rows),
            paired_violation_delta_pp=describe(
                row['violation_delta_pp_transient_minus_control'] for row in rows
            ),
            **{f'{side}_{metric}_sum': sum(row[f'{side}_{metric}'] for row in rows)
               for side in ('transient', 'control')
               for metric in ('generated', 'timely', 'late', 'unobserved')},
            pairs_full_ip_rx_bytes_equal=identical_rx if key[2] == 'LOW' else None,
        ))
    pair_summaries = []
    fields = ('profile', 'traffic', 'lhs_method', 'rhs_method')
    for key, rows in grouped(pairs, fields):
        pair_summaries.append(dict(
            zip(fields, key),
            paired_rng_runs=[row['rng_run'] for row in rows],
            identical_generated_count_pairs=sum(row['generated_counts_equal'] for row in rows),
            **{field: describe(row[field] for row in rows) for field in (
                'violation_delta_pp_rhs_minus_lhs', 'modeled_fh_mbit_delta_rhs_minus_lhs',
                'air_rb_sample_sum_delta_rhs_minus_lhs', 'fh_active_p95_mbps_delta_rhs_minus_lhs',
            )},
        ))
    availability = []
    fields = ('traffic', 'cohort')
    for key, rows in grouped(bins, fields):
        run_groups = list(grouped(rows, ('rng_run',)))
        zero_bins = [sum(row['zero_timely_delivery'] for row in run_rows)
                     for _, run_rows in run_groups]
        availability.append(dict(
            zip(fields, key),
            zero_timely_bins_per_run=describe(zero_bins),
            nonempty_bins_per_run=describe(len(run_rows) for _, run_rows in run_groups),
            missed_deadline_pp=describe(
                100 * sum(row['late'] + row['unobserved'] for row in run_rows) /
                sum(row['generated'] for row in run_rows) for _, run_rows in run_groups
            ),
        ))
    recovery_summaries = []
    fields = ('profile', 'method', 'traffic')
    for key, rows in grouped(recovery, fields):
        observed = [row for row in rows if row['status'] == 'OBSERVED']
        recovery_summaries.append(dict(
            zip(fields, key),
            observed_rng_runs=[int(row['rng_run']) for row in observed],
            status_counts=dict(Counter(row['status'] for row in rows)),
            observed_recovery_time_s=describe(float(row['recovery_time_s']) for row in observed),
        ))
    return {
        'scope': 'Historical TFH development reuse, descriptive only',
        'uncertainty': 'No confidence interval or significance test. Medians and observed ranges across complete runs. Paired mode comparisons use the joint-complete intersection of archived RngRun indices. Execution failures may be informative.',
        'deadline_ns': DEADLINE_NS,
        'phase_bin_ns': BIN_NS,
        'capacity_profiles': capacities,
        'run_failures': failures,
        'cohorts': cohort_summaries,
        'between_modes': pair_summaries,
        'optimize_mcs_t1_ip_availability_proxy': availability,
        'observed_recovery': recovery_summaries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=PRESUBMISSION)
    parser.add_argument('--datagrams', type=Path, default=DATAGRAMS)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    manifest = read_csv(args.archive / MANIFEST_FILE)
    for row in manifest:
        row['rng_run'] = int(row['rng_run'])
    cohorts = load_cohorts(args.archive, index(manifest, ('rng_run', 'method', 'profile')))
    resource_rows = read_csv(args.archive / RESOURCE_FILE)
    for row in resource_rows:
        row['rng_run'] = int(row['rng_run'])
    resources = index(resource_rows, ('profile', 'method', 'rng_run'))
    pairs = audit_between_modes(cohorts, resources)
    bins = audit_t1_ip_bins(args.datagrams)
    verify_bins(cohorts, bins)
    failures = [row for row in manifest if row['status'] != 'PASS']
    summary = summarize(
        cohorts, pairs, bins, failures,
        read_csv(args.archive / RECOVERY_FILE), read_csv(args.archive / CAPACITY_FILE),
    )
    summary['archive_run_status_counts'] = dict(Counter(row['status'] for row in manifest))
    inputs = [args.archive / name for name in (
        *(name for name, _ in COHORT_FILES), RESOURCE_FILE, MANIFEST_FILE,
        CAPACITY_FILE, RECOVERY_FILE,
    )] + [args.datagrams]
    summary['input_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in inputs}
    write_csv(args.output / 'tfh_archived_cohorts.csv', cohorts)
    write_csv(args.output / 'tfh_archived_method_pairs.csv', pairs)
    write_csv(args.output / 'tfh_archived_ip_bins.csv', bins)
    (args.output / 'TFH_ARCHIVED_METRICS.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )


if __name__ == '__main__':
    main()

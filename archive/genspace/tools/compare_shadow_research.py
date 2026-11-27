"""Compare research outputs of two already serialized SHADOW runs.

Does not generate instances or access research namespaces.  Snapshot hashes
and runtime are execution metadata and intentionally differ after refactoring.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def scientific_rows(data):
    return [{key: value for key, value in row.items()
             if key not in ('runtime_seconds', 'snapshot_hash')}
            for row in data['rows']]


def compare(old_dir, new_dir, identities):
    old_dir, new_dir = Path(old_dir), Path(new_dir)
    results = []
    for iid in identities:
        old = json.loads((old_dir / iid / 'result.json').read_text(encoding='utf8'))
        new = json.loads((new_dir / iid / 'result.json').read_text(encoding='utf8'))
        # The detailed validation includes the exact first-failure digest.
        result = {'instance_id': iid,
                  'method_fields_equal': scientific_rows(old) == scientific_rows(new),
                  'independent_validation_equal': old['check'] == new['check']}
        result['equal'] = all(result[x] for x in ('method_fields_equal', 'independent_validation_equal'))
        results.append(result)
    return {'count': len(results), 'matched': sum(r['equal'] for r in results),
            'all_equal': all(r['equal'] for r in results), 'instances': results,
            'excluded_execution_metadata': ['runtime_seconds', 'snapshot_hash']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    plan = json.loads((ROOT / 'SMOKE02_SHADOW_PLAN.json').read_text(encoding='utf8'))
    identities = [entry['instance_id'] for entry in plan['instances']]
    result = compare(args.old, args.new, identities)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    if not result['all_equal']:
        raise SystemExit('SHADOW research outputs differ')
    print(f"exact research equality {result['matched']}/{result['count']}")


if __name__ == '__main__':
    main()

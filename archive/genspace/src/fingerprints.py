"""Reproducibility fingerprints; never creates or runs experimental instances."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import sysconfig

ROOT = Path(__file__).resolve().parent.parent


def _file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def _object_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def fingerprint():
    """Digest source, tests and config separately, plus stdlib runtime identity.

    No non-stdlib runtime dependencies are declared. This records the Python
    implementation and ABI, not a guarantee about host OS or hardware behavior.
    """
    paths = sorted([*ROOT.glob('src/**/*.py'), *ROOT.glob('tests/**/*.py'), *ROOT.glob('tools/**/*.py')],
                   key=lambda p: p.relative_to(ROOT).as_posix())
    sources = {p.relative_to(ROOT).as_posix(): _file_hash(p) for p in paths}
    deps = {'runtime_dependencies': [], 'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation(),
            'python_cache_tag': sys.implementation.cache_tag,
            'python_soabi': sysconfig.get_config_var('SOABI')}
    return {'version': 1, 'sources': sources, 'source_hash': _object_hash(sources),
            'config_hash': _file_hash(ROOT / 'config.yaml'),
            'dependency_environment': deps, 'dependency_hash': _object_hash(deps)}


def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group()
    group.add_argument('--write', type=Path)
    group.add_argument('--check', type=Path)
    args = p.parse_args()
    current = fingerprint()
    if args.check:
        previous = json.loads(args.check.read_text(encoding='utf-8'))
        if previous != current:
            raise SystemExit('Fingerprint mismatch')
        print('Fingerprint match')
    elif args.write:
        args.write.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    else:
        print(json.dumps(current, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

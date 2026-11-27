"""Rehash the original benchmark/development evidence after this audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
before = json.loads((HERE / 'baseline_hashes.json').read_text(encoding='utf8'))
changed, missing = [], []
for name, old_digest in before.items():
    path = ROOT / name
    if not path.is_file():
        missing.append(name)
        continue
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != old_digest:
        changed.append(name)
roots = ('src', 'schemas', 'tests', 'results/method_dev_v1', 'results/pilot',
         'results/pilot_attribution', 'results/pilot_attribution_work')
after = {p.relative_to(ROOT).as_posix()
         for name in roots if (ROOT / name).exists()
         for p in (ROOT / name).rglob('*') if p.is_file()}
additional = sorted(after - set(before))
auth_path = ROOT / 'PILOT_AUTHORIZATION_STATE.json'
auth = json.loads(auth_path.read_text(encoding='utf8'))
auth_sha = hashlib.sha256(auth_path.read_bytes()).hexdigest()
report = {'files_checked': len(before), 'changed': changed, 'missing': missing,
          'unexpected_files_in_input_roots': additional,
          'confirm_allowed': auth['namespace_authorizations']['CONFIRM']['allowed'],
          'pilot_authorization_sha256': auth_sha,
          'pilot_authorization_unchanged': auth_sha == '85c56a9326e5431eba77cb011370b64bdb32f1d6e7c1b1987014d605492fb8ff',
          'frozen_config_exists': (ROOT / 'FROZEN_CONFIG.yaml').exists()}
report['pass'] = (not changed and not missing and not additional and
                  report['confirm_allowed'] is False and
                  report['pilot_authorization_unchanged'] and not report['frozen_config_exists'])
(HERE / 'preservation_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(report, ensure_ascii=False))
if not report['pass']:
    raise SystemExit(1)

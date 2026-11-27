"""File and seal checks shared by the staged depth-three engineering audits."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path, lines):
    path.write_text('\n'.join(lines).rstrip()+'\n', encoding='utf-8')


def write_json(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    pending.replace(path)


def markdown_table(headers, body):
    def row(values):
        return '| ' + ' | '.join(str(v).replace('|','\\|') for v in values) + ' |'
    return [row(headers), row(['---']*len(headers)), *(row(values) for values in body)]


def quantile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*q
    bottom = math.floor(position)
    top = math.ceil(position)
    return ordered[bottom]+(ordered[top]-ordered[bottom])*(position-bottom)


def distribution(values):
    sample = [float(v) for v in values if v not in (None,'')]
    if any(not math.isfinite(v) or v<0 for v in sample):
        raise ValueError('work and time measurements must be finite and nonnegative')
    return dict(n=len(sample),median=quantile(sample,.5),p95=quantile(sample,.95),
                minimum=min(sample,default=None),maximum=max(sample,default=None))


def prior_comparator():
    """Import the archived comparator without loading its reference graph."""
    path = ROOT/'results/grammar_gate/reference.py'
    spec = importlib.util.spec_from_file_location('depth3_archived_flat_reference',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,digest(path.read_bytes())


def sealed_payloads(path, archive_root=HERE):
    """Validate a process-wide clean, complete manifest and each sealed output."""
    path = path.resolve()
    archive_root = archive_root.resolve()
    if not path.is_relative_to(archive_root):
        raise ValueError('seal is outside the designated artifact directory')
    raw = path.read_bytes()
    seal = json.loads(raw)
    if seal.get('complete_batch') is not True or not isinstance(seal.get('cases'),dict):
        raise ValueError('complete process seal is required')
    guard = seal.get('guard',{})
    counters = guard.get('forbidden_call_counts',{})
    if (guard.get('pass') is not True or not counters
            or any(v!=0 for v in counters.values()) or guard.get('blocked')):
        raise ValueError('online guard seal records a forbidden or missing observation')
    manifest = seal['manifest']
    cases = {}
    for iid,entry in seal['cases'].items():
        case_path = (archive_root/entry['path']).resolve()
        if not case_path.is_relative_to(path.parent) or not case_path.is_file():
            raise ValueError(f'case escapes the process output directory: {iid}')
        payload = case_path.read_bytes()
        if digest(payload)!=entry['sha256']:
            raise ValueError(f'case bytes differ from seal: {iid}')
        case = json.loads(payload)
        if case['instance_id']!=iid:
            raise ValueError(f'case identity differs from seal: {iid}')
        cases[iid] = case
    if not cases or list(cases)!=manifest['instance_ids']:
        raise ValueError('case order/scope differs from sealed manifest')
    return seal,cases,digest(raw)

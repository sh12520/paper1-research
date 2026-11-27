"""SMOKE-02 orchestration scaffold, fail-closed pending a valid FAST namespace.

No fixtures are generated or evaluated here. In particular, this module must
not rename a shadow instance to another namespace to get through FAST guards.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

SHADOW = 'GENSPACE-FAIL-01-ENGINEERING-SHADOW'
SMOKE = 'GENSPACE-FAIL-01-SMOKE'
ALLOWED = frozenset((SHADOW, SMOKE))
PHASES = ('PLAN_CREATED', 'MAIN_RUNNING', 'MAIN_PAUSED', 'MAIN_COMPLETE',
          'AUDIT_ARTIFACTS', 'RERUN8', 'FRESH_REPEAT16', 'AGGREGATION',
          'SMOKE_COMPLETE')


class PipelineBlocked(RuntimeError):
    pass


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('xb') as f:
        f.write(canonical_bytes(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def validate_plan(plan, namespace):
    if namespace not in ALLOWED:
        raise ValueError('namespace not permitted')
    if not isinstance(plan, list) or not plan:
        raise ValueError('empty or invalid plan')
    ids = [x['instance_id'] for x in plan]
    if any(not isinstance(i, str) or not i or '/' in i or '\\' in i for i in ids):
        raise ValueError('invalid identity')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate identity')
    return digest(plan)


def ensure_native_fast_namespace(namespace):
    """Refuse execution before generation when native FAST support is absent.

    The existing FAST evaluator allows ENGINEERING and SMOKE, but not the
    required ENGINEERING-SHADOW namespace. The current user explicitly forbids
    modifying that evaluator. We intentionally do not rewrite identities,
    monkey-patch checks, or generate a different instance.
    """
    if namespace not in ALLOWED:
        raise ValueError('namespace not permitted')
    if namespace == SHADOW:
        raise PipelineBlocked('FAST evaluator and runner do not support the required ENGINEERING-SHADOW namespace; user prohibits evaluator modification')
    raise PipelineBlocked('SMOKE execution is not authorized in this turn; full orchestration remains unvalidated')


class Orchestrator:
    """Persist immutable plan identity and provide a strict execution boundary.

    This deliberately does not mark any runtime phase complete without the
    real implementation and its independent verification. Both ENGINEERING
    shadow and future SMOKE go through the same method and guard.
    """
    def __init__(self, directory, namespace, plan, snapshot_hash):
        self.directory = Path(directory)
        self.namespace = namespace
        self.plan_hash = validate_plan(plan, namespace)
        if not isinstance(snapshot_hash, str) or len(snapshot_hash) != 64:
            raise ValueError('invalid snapshot hash')
        int(snapshot_hash, 16)
        self.snapshot_hash = snapshot_hash
        self.plan = plan

    def initialize(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        statefile = self.directory / 'state.json'
        if statefile.exists():
            return self.read_state()
        state = {'format': 'GENSPACE-SMOKE02-STATE-v1', 'phase': 'PLAN_CREATED',
                 'namespace': self.namespace, 'plan_hash': self.plan_hash,
                 'snapshot_hash': self.snapshot_hash, 'complete_ids': [],
                 'execution_authorized': False}
        _atomic_json(statefile, state)
        return state

    def read_state(self):
        state = json.loads((self.directory / 'state.json').read_text(encoding='utf8'))
        if (state.get('namespace'), state.get('plan_hash'), state.get('snapshot_hash')) != (
                self.namespace, self.plan_hash, self.snapshot_hash):
            raise ValueError('resume identity, plan or snapshot mismatch')
        if state.get('phase') not in PHASES:
            raise ValueError('invalid persisted state')
        return state

    def execute(self):
        # Never persist misleading MAIN_RUNNING or generate any instance when
        # the evaluator's native namespace boundary cannot be honored.
        ensure_native_fast_namespace(self.namespace)
        raise PipelineBlocked('real execution backend not implemented')

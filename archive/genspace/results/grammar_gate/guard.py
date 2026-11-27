"""Online process guard for graph-free development searches.

This checks paths and known Python entrypoints inside the trusted worker. The
reference comparator belongs to a different process and is never imported or
called while this guard is active.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import os
import sys


class GuardViolation(RuntimeError):
    pass


@dataclass
class GuardReport:
    counts: dict[str, int] = field(default_factory=dict)
    blocked: list[dict[str, str]] = field(default_factory=list)

    def deny(self, operation, target):
        self.counts[operation] = self.counts.get(operation, 0) + 1
        self.blocked.append({'operation': operation, 'target': str(target)})
        raise GuardViolation(f'graph-free online worker rejected {operation}: {target}')

    def snapshot(self):
        return {'forbidden_call_counts': dict(self.counts), 'blocked': list(self.blocked),
                'pass': not self.blocked}


_active = None
_hook_installed = False


def _resolve(value):
    return Path(os.path.realpath(os.fsdecode(value)))


def _open_audit(event, args):
    if _active is None or event != 'open':
        return
    path, mode, flags = args
    # Python may wrap already-open worker stdout/stderr descriptors. The
    # process launcher must not pass through research artifact descriptors.
    if not isinstance(path, (str, bytes, os.PathLike)):
        return
    root, output, declared, report = _active
    p = _resolve(path)
    if p.name.lower() == 'semantic_library.graph.gz' or p.name.lower().endswith('.graph.gz'):
        report.deny('semantic_graph_file', p)
    if not p.is_relative_to(root):
        return
    rel = p.relative_to(root).as_posix().lower()
    write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
    if rel.startswith('results/index_gate/') or rel == 'results/index_gate':
        report.deny('index_gate_artifact', p)
    if rel.startswith('results/engineering/availability_indices/'):
        report.deny('availability_index_artifact', p)
    if p.is_relative_to(output):
        return
    if write:
        report.deny('write_outside_current_output', p)
    if p in declared or rel == 'config.yaml':
        return
    if p.suffix.lower() in ('.py','.pyc') and rel.startswith(('src/', 'tools/')):
        return
    if (p.suffix.lower() in ('.py','.pyc') and rel.startswith('results/grammar_gate/') and
            p.parent.relative_to(root).as_posix().lower() in
            ('results/grammar_gate','results/grammar_gate/__pycache__')):
        return
    if rel in ('results/method_dev_v1/private_protocol.py', 'results/method_dev_v1/runtime.py',
               'results/method_dev_v1/public_search.py'):
        return
    historical_code = ('private_protocol.','runtime.','public_search.')
    if (rel.startswith('results/method_dev_v1/__pycache__/') and p.suffix.lower() == '.pyc' and
            p.name.lower().startswith(historical_code)):
        return
    report.deny('unlisted_workspace_input', p)


@contextmanager
def graph_guard(root, *, allowed_inputs, output_dir):
    """Allow only declared serialized inputs, code/config and current outputs."""
    global _active, _hook_installed
    if _active is not None:
        raise GuardViolation('graph guard already active')
    root = _resolve(root)
    output = _resolve(output_dir)
    scope = root/'results'/'grammar_gate'
    if not output.is_relative_to(scope) or output == scope:
        raise GuardViolation('output must be an isolated subdirectory of results/grammar_gate')
    data_root = root/'results'/'pilot'/'instances'
    declared = frozenset(_resolve(path) for path in allowed_inputs)
    if any(path.parent != data_root or path.suffix.lower() != '.json' for path in declared):
        raise GuardViolation('only explicitly declared serialized PILOT instance JSON files may enter online')
    report = GuardReport(counts={
        key: 0 for key in ('semantic_graph_file','index_gate_artifact','availability_index_artifact',
                           'unlisted_workspace_input','write_outside_current_output','FastLibrary.from_graph',
                           'FastLibrary.__init__','AvailabilityBundle.load','read_graph','graph_library',
                           'compact_dp.compact_library','compact_graph.compact_library',
                           'semantic_dp.library','semantic_dp.streaming_reference',
                           'enumeration.candidates','engine.enumerate_compositions',
                           'generate_instance','derive_seed')
    })
    if not _hook_installed:
        sys.addaudithook(_open_audit)
        _hook_installed = True
    _active = (root, output, declared, report)
    old_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    originals = []

    def block(holder, attr, name):
        original = holder.__dict__[attr]
        originals.append((holder, attr, original))

        def denied(*args, **kwargs):
            report.deny(name, name)

        setattr(holder, attr, denied)

    try:
        from src import compact_dp, compact_graph, engine, engineering_depth2, enumeration, instances, semantic_dp
        from src.availability_index import AvailabilityBundle
        from src.fast_exact import FastLibrary

        block(FastLibrary,'from_graph','FastLibrary.from_graph')
        block(FastLibrary,'__init__','FastLibrary.__init__')
        block(AvailabilityBundle,'load','AvailabilityBundle.load')
        block(engineering_depth2,'read_graph','read_graph')
        block(compact_graph,'graph_library','graph_library')
        block(compact_dp,'compact_library','compact_dp.compact_library')
        block(compact_graph,'compact_library','compact_graph.compact_library')
        block(semantic_dp,'library','semantic_dp.library')
        block(semantic_dp,'streaming_reference','semantic_dp.streaming_reference')
        block(enumeration,'candidates','enumeration.candidates')
        block(engineering_depth2,'candidates','enumeration.candidates')
        block(engine,'enumerate_compositions','engine.enumerate_compositions')
        block(compact_dp,'enumerate_compositions','engine.enumerate_compositions')
        if 'enumerate_compositions' in enumeration.__dict__:
            block(enumeration,'enumerate_compositions','engine.enumerate_compositions')
        block(instances,'generate_instance','generate_instance')
        block(engineering_depth2,'generate_instance','generate_instance')
        block(instances,'derive_seed','derive_seed')
        yield report
    finally:
        for holder, attr, original in reversed(originals):
            setattr(holder, attr, original)
        sys.dont_write_bytecode = old_bytecode
        _active = None

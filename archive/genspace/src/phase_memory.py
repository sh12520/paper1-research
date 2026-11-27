"""Read-only Windows process and system memory event recorder.

Values are diagnostic metadata only; this module never receives candidates,
utilities or mutable evaluator state. A low-memory event is recorded before
raising, so its caller can durably record PAUSED_MEMORY and stop dispatch.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
from pathlib import Path

EMERGENCY_FLOOR = 768 * 1024 * 1024
TELEMETRY_NAMESPACES = frozenset((
    'GENSPACE-FAIL-01-ENGINEERING-SHADOW',
    'GENSPACE-FAIL-01-PILOT',
    'GENSPACE-FAIL-01-CONFIRM',
))


def telemetry_enabled(namespace, environ=None):
    """Require PILOT telemetry; allow SHADOW's explicit equivalence switch."""
    if namespace == 'GENSPACE-FAIL-01-PILOT':
        return True
    env = os.environ if environ is None else environ
    return namespace in TELEMETRY_NAMESPACES and env.get('GENSPACE_TELEMETRY', 'on').lower() != 'off'


class _MemoryStatus(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                ('total_page', ctypes.c_ulonglong), ('avail_page', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                ('avail_extended', ctypes.c_ulonglong)]


class _Counters(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong),
                ('peak', ctypes.c_size_t), ('current', ctypes.c_size_t),
                ('qpp', ctypes.c_size_t), ('qp', ctypes.c_size_t),
                ('qnpp', ctypes.c_size_t), ('qnp', ctypes.c_size_t),
                ('pagefile', ctypes.c_size_t), ('peakpagefile', ctypes.c_size_t)]


class _FileTime(ctypes.Structure):
    _fields_ = [('low', ctypes.c_ulong), ('high', ctypes.c_ulong)]


def process_info(pid):
    """Return (identity, current, peak); creation time is raw FILETIME ticks."""
    k = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    k.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    k.OpenProcess.restype = ctypes.c_void_p
    k.CloseHandle.argtypes = (ctypes.c_void_p,)
    k.GetProcessTimes.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.c_void_p)
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
    h = k.OpenProcess(0x1000 | 0x10, False, int(pid))
    if not h:
        raise OSError('cannot query process identity/memory')
    try:
        created, exited, kernel, user = (_FileTime() for _ in range(4))
        if not k.GetProcessTimes(h, ctypes.byref(created), ctypes.byref(exited),
                                 ctypes.byref(kernel), ctypes.byref(user)):
            raise OSError('GetProcessTimes failed')
        counters = _Counters(); counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(h, ctypes.byref(counters), counters.cb):
            raise OSError('GetProcessMemoryInfo failed')
        identity = {'pid': int(pid), 'creation_time': (int(created.high) << 32) | int(created.low)}
        return identity, int(counters.current), int(counters.peak)
    finally:
        k.CloseHandle(h)


def system_memory():
    m = _MemoryStatus(); m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError('GlobalMemoryStatusEx failed')
    return int(m.total_phys - m.avail_phys), int(m.avail_phys)


def memory_event(name, orchestrator_pid, *, worker_pid=None):
    pid = os.getpid() if worker_pid is None else int(worker_pid)
    identity, rss, peak = process_info(pid)
    parent_identity, parent_rss, _ = process_info(orchestrator_pid)
    used, available = system_memory()
    return {'event': name, 'timestamp_ns': time.time_ns(), 'pid': pid,
            'process_identity': identity, 'worker_rss': rss, 'worker_peak_rss': peak,
            'orchestrator_identity': parent_identity, 'orchestrator_rss': parent_rss,
            'system_used_physical': used, 'system_available_physical': available}


class PhaseMemoryObserver:
    """Callable event sink; logs one JSON line then enforces emergency floor."""
    def __init__(self, destination, orchestrator_pid, instance_id, *, floor=EMERGENCY_FLOOR):
        if floor < EMERGENCY_FLOOR:
            raise ValueError('emergency memory floor cannot be lowered')
        self.destination = Path(destination)
        self.orchestrator_pid = int(orchestrator_pid)
        self.instance_id = instance_id
        self.floor = int(floor)

    def __call__(self, name):
        record = memory_event(name, self.orchestrator_pid)
        record['instance_id'] = self.instance_id
        with self.destination.open('a', encoding='utf8') as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
        if record['system_available_physical'] < self.floor:
            raise MemoryError('PAUSED_MEMORY: emergency floor reached')


class ReadOnlyTelemetry:
    """Best-effort observations; failures never change FAST control flow."""
    def __init__(self, destination, orchestrator_pid, snapshot_hash, batch_ids):
        self.destination = Path(destination)
        self.orchestrator_pid = int(orchestrator_pid)
        self.snapshot_hash = snapshot_hash
        self.batch_ids = list(batch_ids)

    def emit(self, name, instance_id, *, worker_pid=None, metadata=None):
        try:
            record = memory_event(name, self.orchestrator_pid, worker_pid=worker_pid)
            record.update(instance_id=instance_id, batch_instance_ids=self.batch_ids,
                          timestamp=record['timestamp_ns']/1_000_000_000,
                          worker_peak_working_set=record['worker_peak_rss'],
                          execution_snapshot_hash=self.snapshot_hash)
            if metadata is not None:
                record['lifecycle'] = metadata
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            with self.destination.open('a', encoding='utf8') as stream:
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
                stream.flush()
        except Exception as exc:
            try:
                self.destination.parent.mkdir(parents=True, exist_ok=True)
                with self.destination.open('a', encoding='utf8') as stream:
                    stream.write(json.dumps({'event':'TELEMETRY_ERROR','failed_event':name,
                        'instance_id':instance_id,'timestamp_ns':time.time_ns(),
                        'execution_snapshot_hash':self.snapshot_hash,'error':repr(exc)}, sort_keys=True) + '\n')
                    stream.flush()
            except Exception:
                pass

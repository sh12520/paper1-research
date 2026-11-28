"""Durable concurrent CPU slots for the G1-A development comparison."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import subprocess
import sys
import threading
import time


@dataclass
class Worker:
    process: subprocess.Popen
    source: Path
    result: Path
    trace: Path
    cpu_ns: int | None = None
    stop_requested: bool = False


class ConcurrentStore:
    """A fenced execution store with one supervised process per occupied CPU slot.

    All task timestamps must be readings of the same host-boot monotonic clock.
    The worker is pure calculation and can publish only to a private scratch file.
    Only this store can publish the durable result. A reopened store will preserve
    any active row whose previous owner handle was lost.
    """

    def __init__(self, path: Path, tasks: dict, slots: int, lease_ns: int, emit):
        if type(slots) is not int or slots not in (1, 2):
            raise ValueError("slots must be 1 or 2")
        if type(lease_ns) is not int or not 0 < lease_ns < 2**63 or not tasks:
            raise ValueError("a positive lease and nonempty task plan are required")
        rows = []
        for task_id, plan in sorted(tasks.items()):
            digest = plan["input_sha256"]
            release, fallback, deadline = (plan[k] for k in ("release_ns", "fallback_ns", "deadline_ns"))
            public = plan.get("public_fallback", True)
            if (not isinstance(task_id, str) or not task_id
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                    or any(type(x) is not int for x in (release, fallback, deadline))
                    or not 0 <= release <= fallback <= deadline < 2**63
                    or type(public) is not bool):
                raise ValueError("invalid task binding")
            rows.append((task_id, digest, release, fallback if public else deadline, deadline))
        self._emit = emit
        self._slots = slots
        self._lease_ns = lease_ns
        self._lock = threading.RLock()
        self._wake = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._workers: dict[str, Worker] = {}
        self._fatal: Exception | None = None
        self._closed = False
        self._scratch = path.resolve().with_suffix(".workers")
        self._scratch.mkdir(exist_ok=True)
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        try:
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    slots INTEGER NOT NULL, lease_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    input_sha256 TEXT NOT NULL,
                    release_ns INTEGER NOT NULL,
                    cutoff_ns INTEGER NOT NULL,
                    deadline_ns INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'ARMED'
                        CHECK (state IN ('ARMED', 'GRANTED', 'EXECUTING', 'CANCELLING',
                                        'EXPIRED', 'CANCELLED', 'RESULT', 'COMPUTE_FAILED')),
                    epoch INTEGER,
                    slot INTEGER UNIQUE,
                    lease_expires_ns INTEGER,
                    token TEXT,
                    supervised_pid INTEGER,
                    cancellation_reason TEXT,
                    result BLOB,
                    result_sha256 TEXT
                );
            """)
            with self._transaction() as events:
                prior = self._db.execute("SELECT slots, lease_ns FROM settings").fetchall()
                existing = self._db.execute("""
                    SELECT task_id,input_sha256,release_ns,cutoff_ns,deadline_ns
                    FROM tasks ORDER BY task_id
                """).fetchall()
                if prior:
                    if [tuple(row) for row in prior] != [(slots, lease_ns)] or [
                        tuple(row) for row in existing
                    ] != rows:
                        raise ValueError("persisted plan or slot/lease binding mismatch")
                    for row in self._db.execute(
                        "SELECT * FROM tasks WHERE state IN ('EXECUTING', 'CANCELLING')"
                    ):
                        events.append(("APP_OWNER_UNCONFIRMED", self._fields(row)))
                else:
                    self._db.execute("INSERT INTO settings VALUES (?,?)", (slots, lease_ns))
                    self._db.executemany("""
                        INSERT INTO tasks(task_id,input_sha256,release_ns,cutoff_ns,deadline_ns)
                        VALUES (?,?,?,?,?)
                    """, rows)
        except BaseException:
            self._db.close()
            raise
        self._monitor = threading.Thread(target=self._maintain, name="concurrent-cpu-reaper", daemon=True)
        self._monitor.start()

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("execution store closed")
            self._db.execute("BEGIN IMMEDIATE")
            events = []
            try:
                yield events
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise
            committed_ns = time.monotonic_ns()
            for event, fields in events:
                fields["commit_return_ns"] = committed_ns
                if event == "APP_RELEASE":
                    fields["release_ns"] = committed_ns
                if event == "APP_COMPLETE" and fields["success"]:
                    fields["result_commit_late"] = committed_ns >= fields["cutoff_ns"]
                self._emit(event, **fields)
            if events:
                self._wake.notify()

    def _check(self):
        if self._fatal is not None:
            raise RuntimeError("worker monitor failed") from self._fatal
        if self._closed:
            raise RuntimeError("execution store closed")

    def _row(self, task_id):
        return self._db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()

    @staticmethod
    def _fields(row):
        return {
            "task_id": row["task_id"], "epoch": row["epoch"], "slot": row["slot"],
            "cutoff_ns": row["cutoff_ns"], "lease_expires_ns": row["lease_expires_ns"],
        }

    def _reply(self, row, status=None):
        state = status or row["state"]
        reply = self._fields(row)
        reply["status"] = "IN_PROGRESS" if state == "EXECUTING" else state
        if state == "GRANTED":
            reply["token"] = row["token"]
        elif state == "RESULT":
            reply["result_sha256"] = row["result_sha256"]
            reply["result_b64"] = base64.b64encode(row["result"]).decode("ascii")
        return reply

    @staticmethod
    def _unknown(task_id):
        return {"task_id": task_id, "status": "UNKNOWN_TASK"}

    @staticmethod
    def _token_matches(row, token):
        return isinstance(token, str) and row["token"] is not None and hmac.compare_digest(
            row["token"].encode(), token.encode()
        )

    def _release(self, events, row, state, reason):
        self._db.execute("UPDATE tasks SET state=?, slot=NULL WHERE task_id=?", (state, row["task_id"]))
        fields = self._fields(row)
        fields.update(reason=reason, release_reason=reason, resulting_state=state)
        events.append(("APP_RELEASE", fields))

    def _advance_unused(self, events, now):
        for row in self._db.execute("""
            SELECT * FROM tasks WHERE (state='GRANTED' AND lease_expires_ns<=?)
              OR (state='ARMED' AND cutoff_ns<=?)
            ORDER BY task_id
        """, (now, now)).fetchall():
            if row["state"] == "ARMED":
                self._db.execute("UPDATE tasks SET state='EXPIRED' WHERE task_id=?", (row["task_id"],))
            else:
                terminal = now >= row["cutoff_ns"]
                self._release(events, row, "EXPIRED" if terminal else "ARMED", "unused_lease_expired")

    def grant(self, task_id):
        with self._transaction() as events:
            self._check()
            now = time.monotonic_ns()
            self._advance_unused(events, now)
            row = self._row(task_id)
            if row is None:
                return self._unknown(task_id)
            if row["state"] != "ARMED":
                return self._reply(row)
            if now < row["release_ns"]:
                return self._reply(row, "NOT_RELEASED")
            occupied = {x[0] for x in self._db.execute("SELECT slot FROM tasks WHERE slot IS NOT NULL")}
            slot = next((s for s in range(self._slots) if s not in occupied), None)
            if slot is None:
                events.append(("APP_BUSY", self._fields(row)))
                return self._reply(row, "BUSY")
            epoch = self._db.execute("SELECT COALESCE(MAX(epoch),0)+1 FROM tasks").fetchone()[0]
            expiry = min(now + self._lease_ns, row["cutoff_ns"])
            self._db.execute("""
                UPDATE tasks SET state='GRANTED', epoch=?, slot=?, lease_expires_ns=?, token=?
                WHERE task_id=?
            """, (epoch, slot, expiry, secrets.token_hex(24), task_id))
            granted = self._row(task_id)
            events.append(("APP_GRANT", {**self._fields(granted), "decision_ns": now}))
            return self._reply(granted)

    def status(self, task_id):
        with self._transaction() as events:
            self._check()
            self._advance_unused(events, time.monotonic_ns())
            row = self._row(task_id)
            return self._reply(row) if row else self._unknown(task_id)

    def execute(self, task_id, token, payload_bytes):
        digest = hashlib.sha256(payload_bytes).hexdigest()
        with self._lock:
            with self._transaction() as events:
                self._check()
                self._advance_unused(events, time.monotonic_ns())
                row = self._row(task_id)
                if row is None:
                    return self._unknown(task_id)
                if digest != row["input_sha256"]:
                    return self._reply(row, "WRONG_INPUT")
                if not self._token_matches(row, token):
                    return self._reply(row, "INVALID_TOKEN")
                if row["state"] != "GRANTED":
                    return self._reply(row)
                self._db.execute("UPDATE tasks SET state='EXECUTING' WHERE task_id=?", (task_id,))
                events.append(("APP_EXECUTION_ELIGIBLE", self._fields(row)))
            return self._launch(row, payload_bytes)

    def _launch(self, row, payload):
        task_id = row["task_id"]
        epoch = str(row["epoch"])
        source = self._scratch / f"{epoch}.input"
        result = self._scratch / f"{epoch}.result"
        trace = self._scratch / f"{epoch}.trace"
        cutoff = row["cutoff_ns"]
        # A lease governs the first start, whereas the task cutoff governs the
        # full computation. Recheck after the durable transition and input copy.
        try:
            source.write_bytes(payload)
            if time.monotonic_ns() >= min(cutoff, row["lease_expires_ns"]):
                state = "EXPIRED" if time.monotonic_ns() >= cutoff else "ARMED"
                with self._transaction() as events:
                    self._release(events, row, state, "expired_before_process_start")
                source.unlink()
                return self._reply(self._row(task_id))
            process = subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__).resolve()), str(source), str(result), str(trace),
                 str(cutoff), str(row["lease_expires_ns"])],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            with self._transaction() as events:
                events.append(("APP_WORKER_LAUNCH_FAILURE", {
                    **self._fields(row), "error_type": type(error).__name__
                }))
                self._release(events, row, "COMPUTE_FAILED", "worker_launch_failure")
            source.unlink(missing_ok=True)
            return self._reply(self._row(task_id))
        activation_ns = time.monotonic_ns()
        self._workers[task_id] = Worker(process, source, result, trace)
        with self._transaction() as events:
            self._db.execute("UPDATE tasks SET supervised_pid=? WHERE task_id=?", (process.pid, task_id))
            events.append(("APP_START", {
                **self._fields(row), "worker_pid": process.pid, "activation_ns": activation_ns,
            }))
        return self._reply(self._row(task_id))

    def cancel(self, task_id, token=None, reason="terminal_fallback"):
        with self._lock:
            with self._transaction() as events:
                self._check()
                row = self._row(task_id)
                if row is None:
                    return self._unknown(task_id)
                if token is not None and not self._token_matches(row, token):
                    return self._reply(row, "INVALID_TOKEN")
                if time.monotonic_ns() < row["release_ns"]:
                    return self._reply(row, "NOT_RELEASED")
                self._cancel_in_transaction(events, row, reason)
            row = self._row(task_id)
            if row["state"] == "CANCELLING":
                self._request_stop(task_id)
            return self._reply(row)

    def _cancel_in_transaction(self, events, row, reason):
        state = row["state"]
        if state not in ("ARMED", "GRANTED", "EXECUTING"):
            return
        task_id = row["task_id"]
        events.append(("APP_CANCEL_ACCEPTED", {**self._fields(row), "reason": reason}))
        self._db.execute("UPDATE tasks SET cancellation_reason=? WHERE task_id=?", (reason, task_id))
        if state == "GRANTED":
            self._release(events, row, "CANCELLED", reason)
        else:
            self._db.execute("UPDATE tasks SET state=? WHERE task_id=?", (
                "CANCELLING" if state == "EXECUTING" else "CANCELLED", task_id
            ))

    @staticmethod
    def _poll_worker(worker):
        process = worker.process
        if process.returncode is not None or not hasattr(os, "wait4"):
            return process.poll()
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = os.waitstatus_to_exitcode(status)
            worker.cpu_ns = round((usage.ru_utime + usage.ru_stime) * 1_000_000_000)
        return process.returncode

    def _request_stop(self, task_id, *, force=False):
        worker = self._workers.get(task_id)
        if worker is None or (worker.stop_requested and not force) or self._poll_worker(worker) is not None:
            return
        process = worker.process
        requested_ns = time.monotonic_ns()
        if hasattr(os, "wait4"):
            # This supervisor owns the sole wait for this child under _lock.
            # An exited but unreaped child still reserves this PID.
            try:
                os.kill(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif force:
            process.kill()
        else:
            process.terminate()
        worker.stop_requested = True
        self._emit("APP_STOP_REQUESTED", **self._fields(self._row(task_id)), worker_pid=process.pid,
                   stop_requested_ns=requested_ns, force=force)

    def _await_worker(self, worker, timeout):
        limit = time.monotonic() + timeout
        while True:
            code = self._poll_worker(worker)
            if code is not None:
                return code
            if time.monotonic() >= limit:
                raise subprocess.TimeoutExpired(worker.process.args, timeout)
            time.sleep(0.002)

    def _reap(self, task_id, worker, code):
        # This wait is on the supervisor-owned handle. A PID lookup is inadequate.
        if worker.process.wait() != code:
            raise RuntimeError("worker process exit status changed")
        confirmed_ns = time.monotonic_ns()
        with self._transaction() as events:
            row = self._row(task_id)
            if row["state"] not in ("EXECUTING", "CANCELLING") or row["supervised_pid"] != worker.process.pid:
                raise RuntimeError("worker ownership or epoch mismatch")
            fields = self._fields(row)
            if worker.trace.is_file():
                with worker.trace.open(encoding="utf-8") as handle:
                    lines = handle.readlines()
                for line in lines:
                    # A termination can interrupt the last write.
                    if line.endswith("\n"):
                        data = json.loads(line)
                        events.append((data["event"], {
                            **fields, "worker_pid": worker.process.pid, "worker_event_ns": data["time_ns"]
                        }))
            events.append(("APP_WORKER_EXIT_CONFIRMED", {
                **fields, "worker_pid": worker.process.pid, "exit_code": code, "confirmed_ns": confirmed_ns,
                "worker_cpu_ns": worker.cpu_ns
            }))
            if row["state"] == "CANCELLING":
                self._release(events, row, "CANCELLED", row["cancellation_reason"])
            elif code == 0 and confirmed_ns < row["cutoff_ns"]:
                data = worker.result.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                self._db.execute("UPDATE tasks SET result=?,result_sha256=? WHERE task_id=?",
                                 (data, digest, task_id))
                events.append(("APP_COMPLETE", {**fields, "success": True, "result_sha256": digest}))
                self._release(events, row, "RESULT", "completed")
            elif code == 74 and confirmed_ns < row["cutoff_ns"]:
                self._release(events, row, "ARMED", "lease_expired_before_compute")
            elif code in (0, 74, 75):
                self._release(events, row, "EXPIRED", "execution_cutoff")
            else:
                events.append(("APP_COMPLETE", {**fields, "success": False, "exit_code": code}))
                self._release(events, row, "COMPUTE_FAILED", "confirmed_abnormal_exit")
        self._workers.pop(task_id)
        for path in (worker.source, worker.result, worker.trace):
            path.unlink(missing_ok=True)

    def _tick(self):
        with self._lock:
            with self._transaction() as events:
                now = time.monotonic_ns()
                self._advance_unused(events, now)
                for row in self._db.execute(
                    "SELECT * FROM tasks WHERE state='EXECUTING' AND cutoff_ns<=?", (now,)
                ).fetchall():
                    self._cancel_in_transaction(events, row, "public_execution_cutoff")
            for task_id, worker in tuple(self._workers.items()):
                if self._row(task_id)["state"] == "CANCELLING":
                    self._request_stop(task_id)
                code = self._poll_worker(worker)
                if code is not None:
                    self._reap(task_id, worker, code)

    def _maintain(self):
        try:
            with self._wake:
                while not self._stop.is_set():
                    self._tick()
                    due = self._db.execute('''
                        SELECT MIN(CASE WHEN state='GRANTED' THEN lease_expires_ns ELSE cutoff_ns END)
                        FROM tasks WHERE state IN ('GRANTED','EXECUTING')
                    ''').fetchone()[0]
                    delays = [0.005] if self._workers else []
                    if due is not None:
                        delays.append(max(0.0, (due - time.monotonic_ns()) / 1_000_000_000))
                    # Known cutoffs can preempt the exit-probe interval.
                    # Changes to reservations and runs notify this condition.
                    self._wake.wait(min(delays) if delays else None)
        except Exception as error:
            self._fatal = error
            self._emit("APP_MONITOR_FAILURE", error_type=type(error).__name__, error=str(error))

    def close(self):
        if self._closed:
            return
        with self._wake:
            self._stop.set()
            self._wake.notify()
        self._monitor.join()
        with self._lock:
            try:
                for task_id, worker in tuple(self._workers.items()):
                    with self._transaction() as events:
                        self._cancel_in_transaction(events, self._row(task_id), "supervised_shutdown")
                    self._request_stop(task_id)
                    try:
                        code = self._await_worker(worker, 2)
                    except subprocess.TimeoutExpired:
                        self._request_stop(task_id, force=True)
                        code = self._await_worker(worker, 5)
                    self._reap(task_id, worker, code)
            finally:
                self._closed = True
                self._db.close()
        if self._fatal is not None:
            raise RuntimeError("worker monitor failed") from self._fatal


def _worker(source, result, trace, cutoff, lease_expires):
    # The process start counts against the lease. The image workload itself
    # has a separate effect cutoff after it has become eligible to execute.
    if time.monotonic_ns() >= min(cutoff, lease_expires):
        return 74
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service-worker"))
    from image_workload import compute_edge

    if time.monotonic_ns() >= min(cutoff, lease_expires):
        return 74
    payload = source.read_bytes()
    with trace.open("x", encoding="utf-8", buffering=1) as handle:
        handle.write(json.dumps({"event": "WORKER_COMPUTE_START", "time_ns": time.monotonic_ns()}) + "\n")
        data = compute_edge(payload)
        handle.write(json.dumps({"event": "WORKER_COMPUTE_END", "time_ns": time.monotonic_ns()}) + "\n")
    if time.monotonic_ns() >= cutoff:
        return 75
    result.write_bytes(data)
    return 0


if __name__ == "__main__":
    _, source_arg, result_arg, trace_arg, cutoff_arg, lease_arg = sys.argv
    raise SystemExit(_worker(Path(source_arg), Path(result_arg), Path(trace_arg), int(cutoff_arg), int(lease_arg)))

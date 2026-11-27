"""Durable single-worker execution slot for the same-host development experiment."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from typing import Callable


class TaskStore:
    """A durable reservation gate, one actual CPU worker, and replayable results.

    Cutoffs are monotonic nanosecond readings on a single host boot. A restarted
    uncompleted EXECUTING row remains occupied and is never silently retried.
    Call close only after the service has stopped accepting and drained RPCs.
    """

    def __init__(
        self,
        path: Path,
        input_hashes: dict[str, str],
        compute: Callable[[bytes], bytes],
        emit: Callable,
    ):
        if not input_hashes:
            raise ValueError("at least one task input must be bound")
        for task_id, digest in input_hashes.items():
            if not isinstance(task_id, str) or not task_id:
                raise ValueError("task IDs must be nonempty strings")
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(ch not in "0123456789abcdef" for ch in digest)):
                raise ValueError("inputs must be bound to lowercase SHA-256")
        self._compute = compute
        self._emit = emit
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._closed = False
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        try:
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    input_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN (
                        'UNARMED', 'ARMED', 'GRANTED', 'EXECUTING',
                        'EXPIRED', 'RESULT', 'COMPUTE_FAILED'
                    )),
                    cutoff_ns INTEGER,
                    token TEXT,
                    result BLOB,
                    result_sha256 TEXT
                )
            """)
            with self._transaction(sweep=False):
                existing = {
                    row["task_id"]: row["input_sha256"]
                    for row in self._db.execute("SELECT task_id, input_sha256 FROM tasks")
                }
                if existing and existing != input_hashes:
                    raise ValueError("persisted task binding mismatch")
                if not existing:
                    self._db.executemany(
                        "INSERT INTO tasks (task_id, input_sha256, state) VALUES (?, ?, 'UNARMED')",
                        input_hashes.items(),
                    )
        except BaseException:
            self._db.close()
            raise
        self._sweeper = threading.Thread(target=self._sweep, name="task-slot-expiry", daemon=True)
        self._sweeper.start()

    @contextmanager
    def _transaction(self, *, sweep=True):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            events = []
            try:
                if sweep:
                    self._expire_unused(events, time.monotonic_ns())
                yield events
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise
            # Publish only committed events, under the same lock as the change.
            for event, fields in events:
                self._emit(event, **fields)

    def _expire_unused(self, events, now_ns):
        rows = list(self._db.execute(
            "SELECT * FROM tasks WHERE state = 'GRANTED' AND cutoff_ns <= ?", (now_ns,)
        ))
        for row in rows:
            self._set_state(row["task_id"], "EXPIRED")
            self._release_event(events, row["task_id"], "expired_unused", row["cutoff_ns"], now_ns)

    def _sweep(self):
        while not self._stop.wait(0.01):
            try:
                with self._transaction():
                    pass
            except Exception as error:
                self._emit("APP_SWEEP_ERROR", error_type=type(error).__name__)

    def _row(self, task_id):
        return self._db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    def _set_state(self, task_id, state):
        self._db.execute("UPDATE tasks SET state = ? WHERE task_id = ?", (state, task_id))

    @staticmethod
    def _reply(task_id, state, **fields):
        return {"status": state, "task_id": task_id, **fields}

    def _reject(self, events, task_id, reason):
        events.append(("APP_REJECT", {"task_id": task_id, "reason": reason}))
        return self._reply(task_id, reason)

    @staticmethod
    def _release_event(events, task_id, reason, cutoff_ns, release_ns):
        events.append(("APP_RELEASE", {
            "task_id": task_id, "reason": reason, "release_reason": reason,
            "cutoff_ns": cutoff_ns, "release_ns": release_ns,
        }))

    def _status(self, row):
        task_id, state, cutoff_ns = row["task_id"], row["state"], row["cutoff_ns"]
        if state == "GRANTED":
            return self._reply(task_id, state, token=row["token"], cutoff_ns=cutoff_ns)
        if state == "RESULT":
            return self._reply(
                task_id, state, result_sha256=row["result_sha256"],
                result_b64=base64.b64encode(row["result"]).decode("ascii"),
            )
        if state == "ARMED" and time.monotonic_ns() >= cutoff_ns:
            return self._reply(task_id, "EXPIRED")
        if state == "EXECUTING":
            return self._reply(task_id, "IN_PROGRESS")
        return self._reply(task_id, state)

    def arm(self, task_id, cutoff_ns):
        with self._transaction() as events:
            row = self._row(task_id)
            if row is None:
                return self._reject(events, task_id, "UNKNOWN_TASK")
            if type(cutoff_ns) is not int or not 0 < cutoff_ns < 2**63:
                return self._reject(events, task_id, "INVALID_CUTOFF")
            if row["cutoff_ns"] is not None:
                if row["cutoff_ns"] != cutoff_ns:
                    return self._reject(events, task_id, "CUTOFF_MISMATCH")
                return self._status(row)
            if time.monotonic_ns() >= cutoff_ns:
                return self._reject(events, task_id, "EXPIRED")
            self._db.execute(
                "UPDATE tasks SET state = 'ARMED', cutoff_ns = ? WHERE task_id = ?",
                (cutoff_ns, task_id),
            )
            return self._reply(task_id, "ARMED", cutoff_ns=cutoff_ns)

    def grant(self, task_id):
        with self._transaction() as events:
            row = self._row(task_id)
            if row is None:
                return self._reject(events, task_id, "UNKNOWN_TASK")
            if row["state"] != "ARMED":
                return self._status(row)
            cutoff_ns = row["cutoff_ns"]
            now_ns = time.monotonic_ns()
            if now_ns >= cutoff_ns:
                self._set_state(task_id, "EXPIRED")
                return self._reject(events, task_id, "EXPIRED")
            active = self._db.execute(
                "SELECT 1 FROM tasks WHERE state IN ('GRANTED', 'EXECUTING') LIMIT 1"
            ).fetchone()
            if active:
                return self._reject(events, task_id, "BUSY")
            token = secrets.token_hex(16)
            self._db.execute(
                "UPDATE tasks SET state = 'GRANTED', token = ? WHERE task_id = ?", (token, task_id)
            )
            events.append(("APP_GRANT", {
                "task_id": task_id, "cutoff_ns": cutoff_ns, "granted_ns": now_ns,
            }))
            return self._reply(task_id, "GRANTED", token=token, cutoff_ns=cutoff_ns)

    def status(self, task_id):
        with self._transaction() as events:
            row = self._row(task_id)
            if row is None:
                return self._reject(events, task_id, "UNKNOWN_TASK")
            return self._status(row)

    def execute(self, task_id, token, payload: bytes):
        raw_hash = hashlib.sha256(payload).hexdigest()
        with self._transaction() as events:
            row = self._row(task_id)
            if row is None:
                return self._reject(events, task_id, "UNKNOWN_TASK")
            if raw_hash != row["input_sha256"]:
                return self._reject(events, task_id, "WRONG_INPUT")
            if not isinstance(token, str) or not row["token"] or not hmac.compare_digest(
                token.encode("utf-8"), row["token"].encode("ascii")
            ):
                return self._reject(events, task_id, "INVALID_TOKEN")
            state, cutoff_ns = row["state"], row["cutoff_ns"]
            if state in ("EXECUTING", "RESULT", "COMPUTE_FAILED"):
                return self._status(row)
            if state == "EXPIRED" or time.monotonic_ns() >= cutoff_ns:
                return self._reject(events, task_id, "EXPIRED")
            if state != "GRANTED":
                return self._reject(events, task_id, "NOT_GRANTED")
            self._set_state(task_id, "EXECUTING")

        # SQLite persistence is on the first-start path. Fail closed if it
        # consumed the remaining grant window before the calculation begins.
        activation_ns = time.monotonic_ns()
        if activation_ns >= cutoff_ns:
            with self._transaction() as events:
                self._set_state(task_id, "EXPIRED")
                self._release_event(events, task_id, "expired_unused", cutoff_ns, activation_ns)
                return self._reject(events, task_id, "EXPIRED")
        self._emit(
            "APP_START", task_id=task_id, activation_ns=activation_ns,
            cutoff_ns=cutoff_ns, input_bytes=len(payload),
        )
        compute_started_ns = time.monotonic_ns()
        try:
            result = self._compute(payload)
            compute_wall_ns = time.monotonic_ns() - compute_started_ns
            if not isinstance(result, bytes):
                raise TypeError("compute must return bytes")
        except Exception as error:
            compute_wall_ns = time.monotonic_ns() - compute_started_ns
            with self._transaction() as events:
                self._set_state(task_id, "COMPUTE_FAILED")
                events.append(("APP_COMPLETE", {
                    "task_id": task_id, "compute_wall_ns": compute_wall_ns,
                    "success": False, "error_type": type(error).__name__,
                }))
                self._release_event(events, task_id, "compute_failed", cutoff_ns, time.monotonic_ns())
                return self._reply(task_id, "COMPUTE_FAILED")

        result_sha256 = hashlib.sha256(result).hexdigest()
        with self._transaction() as events:
            self._db.execute(
                "UPDATE tasks SET state = 'RESULT', result = ?, result_sha256 = ? WHERE task_id = ?",
                (result, result_sha256, task_id),
            )
            events.append(("APP_COMPLETE", {
                "task_id": task_id, "compute_wall_ns": compute_wall_ns,
                "success": True, "result_sha256": result_sha256,
            }))
            self._release_event(events, task_id, "completed", cutoff_ns, time.monotonic_ns())
            return self._status(self._row(task_id))

    def close(self):
        self._stop.set()
        self._sweeper.join()
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True


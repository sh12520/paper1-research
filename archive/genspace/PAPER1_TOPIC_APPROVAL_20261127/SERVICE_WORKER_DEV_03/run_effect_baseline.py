"""Controlled local experiment with an independently visible SQLite output."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import sqlite3
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
DEV01 = HERE.parent / "SERVICE_WORKER_DEV_01"
sys.path.insert(0, str(DEV01))
from run_study import compute_edge


POLICIES = ("IDEMPOTENCY_ONLY", "FENCE_AND_IDEMPOTENCY", "FENCE_DEADLINE_IDEMPOTENCY")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def setup(db_path):
    with connection(db_path) as db:
        db.executescript("""
        CREATE TABLE target (id INT PRIMARY KEY CHECK (id = 1), generation INT NOT NULL);
        INSERT INTO target VALUES (1, 0);
        CREATE TABLE permits (
            task_id TEXT PRIMARY KEY,
            generation INT NOT NULL,
            cutoff_ns INT NOT NULL,
            input_sha TEXT NOT NULL,
            token TEXT NOT NULL
        );
        CREATE TABLE effects (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            generation INT NOT NULL,
            result_sha TEXT NOT NULL,
            checked_ns INT NOT NULL
        );
        CREATE TABLE visible (
            id INT PRIMARY KEY CHECK (id = 1),
            event_id INT NOT NULL,
            task_id TEXT NOT NULL,
            generation INT NOT NULL,
            result_sha TEXT NOT NULL,
            result BLOB NOT NULL
        );
        """)


@contextmanager
def connection(db_path):
    db = sqlite3.connect(db_path, isolation_level=None, timeout=5)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        yield db
    finally:
        db.close()


def grant(db_path, task, bound_input_sha, duration_ms):
    with connection(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        generation = db.execute("SELECT generation FROM target").fetchone()[0] + 1
        db.execute("UPDATE target SET generation=?", (generation,))
        cutoff_ns = time.monotonic_ns() + duration_ms * 1_000_000
        token = secrets.token_hex(16)
        db.execute(
            "INSERT INTO permits VALUES (?, ?, ?, ?, ?)",
            (task, generation, cutoff_ns, bound_input_sha, token),
        )
        db.commit()
    return {"task": task, "generation": generation, "cutoff_ns": cutoff_ns, "token": token}


def publish(db_path, policy, permit, input_sha, output):
    digest = sha(output)
    task, generation = permit["task"], permit["generation"]
    with connection(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        known = db.execute("SELECT * FROM permits WHERE task_id=?", (task,)).fetchone()
        previous = db.execute("SELECT * FROM effects WHERE task_id=?", (task,)).fetchone()
        current_generation = db.execute("SELECT generation FROM target").fetchone()[0]
        checked_ns = time.monotonic_ns()
        result = {
            "task": task, "generation": generation, "current_generation": current_generation,
            "check_ns": checked_ns, "commit_observed_ns": None, "result_sha": digest,
            "pid": os.getpid(), "event_id": None,
            "cutoff_ns": known["cutoff_ns"] if known else None,
        }
        if (known is None or known["generation"] != generation or known["input_sha"] != input_sha
                or not secrets.compare_digest(known["token"], permit["token"])):
            result["status"] = "INVALID_PERMIT"
        elif previous:
            if previous["generation"] != generation or previous["result_sha"] != digest:
                result["status"] = "IDEMPOTENCY_CONFLICT"
            else:
                result.update(status="REPLAY", event_id=previous["event_id"])
        elif policy != "IDEMPOTENCY_ONLY" and generation != current_generation:
            result["status"] = "STALE_GENERATION"
        elif policy == "FENCE_DEADLINE_IDEMPOTENCY" and not checked_ns < known["cutoff_ns"]:
            result["status"] = "DEADLINE_EXPIRED"
        else:
            cursor = db.execute(
                "INSERT INTO effects(task_id,generation,result_sha,checked_ns) VALUES(?,?,?,?)",
                (task, generation, digest, checked_ns),
            )
            event_id = cursor.lastrowid
            db.execute(
                "INSERT OR REPLACE INTO visible VALUES (1,?,?,?,?,?)",
                (event_id, task, generation, digest, output),
            )
            db.commit()
            result.update(status="APPLIED", event_id=event_id, commit_observed_ns=time.monotonic_ns())
            return result
        db.rollback()
    return result


def visible(db_path):
    with connection(db_path) as db:
        row = db.execute("SELECT * FROM visible").fetchone()
        count = db.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
    if row is None:
        return {"task": None, "result_sha": None, "effects": count}
    assert sha(row["result"]) == row["result_sha"]
    return {"task": row["task_id"], "result_sha": row["result_sha"], "effects": count}


def tell(data):
    print(json.dumps(data), flush=True)


def worker_main(db_path, policy, asset):
    payload = asset.read_bytes()
    tell({"event": "BOOT", "pid": os.getpid(), "monotonic_ns": time.monotonic_ns()})
    permit = json.loads(sys.stdin.readline())
    begin = time.monotonic_ns()
    output = compute_edge(payload)
    tell({"event": "COMPUTED_AND_HELD", "pid": os.getpid(), "task": permit["task"],
          "result_sha": sha(output), "cpu_begin_ns": begin, "monotonic_ns": time.monotonic_ns()})
    for command in sys.stdin:
        if command.rstrip() == "PUBLISH":
            tell({"event": "SINK_REPLY", **publish(db_path, policy, permit, sha(payload), output)})
        else:
            raise ValueError("unexpected worker command")


class Worker:
    def __init__(self, folder, name, policy, asset):
        self.log = (folder / (name + "_stderr.log")).open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--worker",
             str(folder / "sink.sqlite"), policy, str(asset)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        self.mailbox = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        for line in self.process.stdout:
            self.mailbox.put(line)
        self.mailbox.put(None)

    def event(self, kind):
        message = self.mailbox.get(timeout=20)
        if message is None:
            raise RuntimeError("worker exited before " + kind)
        row = json.loads(message)
        assert row["event"] == kind and row["pid"] == self.process.pid
        return row

    def send(self, value):
        self.process.stdin.write(value + "\n")
        self.process.stdin.flush()

    def close(self):
        try:
            self.process.stdin.close()
            assert self.process.wait(timeout=3) == 0
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=3)
            self.reader.join(timeout=3)
            self.process.stdout.close()
            self.log.close()


def without_token(permit):
    return {key: val for key, val in permit.items() if key != "token"}


def run_case(out, condition, policy, assets, expected):
    folder = out / (condition + "_" + policy.lower())
    folder.mkdir()
    database = folder / "sink.sqlite"
    setup(database)
    report = []
    workers = []

    def spawn(name, asset):
        worker = Worker(folder, name, policy, assets[asset])
        workers.append(worker)
        report.append(worker.event("BOOT"))
        return worker

    def start(worker, task, asset, duration):
        permit = grant(database, task, sha(assets[asset].read_bytes()), duration)
        report.append({"event": "PERMIT", **without_token(permit), "monotonic_ns": time.monotonic_ns()})
        worker.send(json.dumps(permit))
        done = worker.event("COMPUTED_AND_HELD")
        assert done["result_sha"] == expected[asset]
        report.append(done)
        return permit

    try:
        old = spawn("A", "camera")
        new = spawn("B", "coffee") if condition == "STALE_AFTER_NEW" else None
        first = start(old, "A", "camera", 10_000 if new else 1_500)
        b_reply = None
        if new:
            start(new, "B", "coffee", 10_000)
            new.send("PUBLISH")
            b_reply = new.event("SINK_REPLY")
            assert b_reply["status"] == "APPLIED"
            assert b_reply["commit_observed_ns"] < first["cutoff_ns"]
            report.append(b_reply)
        else:
            time.sleep(max(0, (first["cutoff_ns"] - time.monotonic_ns()) / 1e9) + 0.025)
        snapshot_before_a = visible(database)
        assert old.process.poll() is None
        report.append({"event": "RELEASE_OLD", "pid": old.process.pid, "old_process_alive": True,
                       "monotonic_ns": time.monotonic_ns(), "visible_before": snapshot_before_a})
        old.send("PUBLISH")
        a_reply = old.event("SINK_REPLY")
        report.append(a_reply)
        if new:
            assert a_reply["check_ns"] < first["cutoff_ns"]
            assert a_reply["check_ns"] > b_reply["commit_observed_ns"]
            wanted = "APPLIED" if policy == "IDEMPOTENCY_ONLY" else "STALE_GENERATION"
        else:
            assert a_reply["check_ns"] >= first["cutoff_ns"]
            wanted = "DEADLINE_EXPIRED" if policy == "FENCE_DEADLINE_IDEMPOTENCY" else "APPLIED"
        assert a_reply["status"] == wanted
        after_a = visible(database)
        replay_worker = new if new else (old if wanted == "APPLIED" else None)
        if replay_worker:
            replay_worker.send("PUBLISH")
            replay = replay_worker.event("SINK_REPLY")
            assert replay["status"] == "REPLAY"
            assert replay["commit_observed_ns"] is None and visible(database) == after_a
            report.append(replay)
        assert after_a["task"] == ("A" if wanted == "APPLIED" else "B" if new else None)
        if after_a["task"]:
            key = "camera" if after_a["task"] == "A" else "coffee"
            assert after_a["result_sha"] == expected[key]
        summary = {
            "condition": condition, "policy": policy, "old_worker_alive_at_release": True,
            "old_publish_attempt": a_reply["status"], "visible_before_old": snapshot_before_a["task"],
            "visible_after_old": after_a["task"], "effect_count": after_a["effects"],
            "matched_reference_output": True if after_a["task"] else None,
            "duplicate_replay_without_write": True if replay_worker else None,
        }
        report.append({"event": "FINAL_VISIBLE", **after_a})
    finally:
        for worker in reversed(workers):
            worker.close()
        (folder / "events.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in report), encoding="utf-8",
        )
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(HERE) or out == HERE:
        raise ValueError("out must be fresh and inside DEV03")
    out.mkdir(exist_ok=False)
    assets = {name: (args.assets / (name + ".png")).resolve() for name in ("camera", "coffee")}
    expected = {name: sha(compute_edge(path.read_bytes())) for name, path in assets.items()}
    cases = [run_case(out, condition, policy, assets, expected)
             for condition in ("STALE_AFTER_NEW", "LATE_SAME_GENERATION") for policy in POLICIES]
    result = {
        "scope": "controlled same-host live-paused worker and sandbox SQLite publication",
        "policy_timing_scope": "deadline check is a local observe-before-commit gate, not a hard commit bound",
        "asset_sha256": {name: sha(path.read_bytes()) for name, path in assets.items()},
        "reference_result_sha256": expected,
        "source_sha256": {"run_effect_baseline.py": sha(Path(__file__).read_bytes()),
                          "DEV01/run_study.py": sha((DEV01 / "run_study.py").read_bytes())},
        "cases": cases,
    }
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker_main(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    else:
        main()


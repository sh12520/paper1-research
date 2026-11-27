"""Reference control for a pure task when the sole owner is known dead."""

import argparse
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import threading
import time

from offload_server import DurableLog
from probe_inflight import inputs
from run_pairs import ROOT, compute_edge, digest, json_save
from task_store import TaskStore


def retire_first_if_confirmed_dead(owned_process, db_path):
    """Use the supervisor's existing handle, never a pid-only state guess."""
    code = owned_process.poll()
    if code is None:
        return "OWNER_ALIVE"
    if code == 0:
        return "NO_ABNORMAL_EXIT"
    with sqlite3.connect(db_path, isolation_level=None) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT state,result,result_sha256 FROM tasks WHERE task_id='first'"
        ).fetchone()
        if row != ("EXECUTING", None, None):
            db.rollback()
            return "NO_UNPUBLISHED_EXECUTION"
        db.execute("""
            CREATE TABLE IF NOT EXISTS supervisor_retirements(
                task_id TEXT PRIMARY KEY, old_state TEXT NOT NULL, reason TEXT NOT NULL,
                supervised_pid INTEGER NOT NULL, exit_code INTEGER NOT NULL)
        """)
        db.execute(
            "INSERT INTO supervisor_retirements VALUES ('first','EXECUTING',?,?,?)",
            ("PURE_TASK_ABANDONED_AFTER_CONFIRMED_EXIT", owned_process.pid, code),
        )
        # Compatibility terminal for the unchanged gate, with exact reason in the ledger above.
        db.execute("UPDATE tasks SET state='COMPUTE_FAILED' WHERE task_id='first'")
        db.commit()
    return "RETIRED"


def run(case, asset):
    case.mkdir(exist_ok=False)
    prior_fixture = ROOT / "probe_inflight.py"
    db_path = case / "worker.sqlite"
    with (case / "child_stderr.log").open("ab") as err:
        child = subprocess.Popen(
            [sys.executable, "-B", str(prior_fixture), str(case), str(asset), "--child"],
            stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        try:
            mailbox = queue.Queue(1)
            threading.Thread(target=lambda: mailbox.put(child.stdout.readline()), daemon=True).start()
            notice = json.loads(mailbox.get(timeout=20))
            assert notice["pid"] == child.pid
            while_alive = retire_first_if_confirmed_dead(child, db_path)
            assert while_alive == "OWNER_ALIVE"
            child.kill()
            assert child.wait(timeout=5) != 0
            after_exit = retire_first_if_confirmed_dead(child, db_path)
            assert after_exit == "RETIRED"
            assert retire_first_if_confirmed_dead(child, db_path) == "NO_UNPUBLISHED_EXECUTION"
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()

    payload, bindings = inputs(asset)
    emit = DurableLog(case / "inflight_events.jsonl")
    gate = TaskStore(db_path, bindings, compute_edge, emit)
    try:
        assert gate.status("first")["status"] == "COMPUTE_FAILED"
        assert gate.arm("next", time.monotonic_ns() + 1_500_000_000)["status"] == "ARMED"
        proof = gate.grant("next")
        assert proof["status"] == "GRANTED"
        result = gate.execute("next", proof["token"], payload)
        assert result["status"] == "RESULT"
        assert result["result_sha256"] == digest(compute_edge(payload))
    finally:
        gate.close()
        emit.close()
    raw = [json.loads(line) for line in (case / "inflight_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["task_id"] for e in raw if e["event"] == "APP_START"] == ["first", "next"]
    assert [e["task_id"] for e in raw if e["event"] == "APP_COMPLETE"] == ["next"]
    evidence = {
        "scope": "single supervised local worker, pure calculation, sole side effect is the durable result",
        "reclamation_while_owner_live": while_alive,
        "reclamation_after_wait_confirms_exit": after_exit,
        "first_outcome": "abandoned with separate reason, not a successful result",
        "next_task": result["status"], "next_result_sha256": result["result_sha256"],
        "actual_worker_starts": 2, "durable_results": 1,
        "owner_handle_pid": notice["pid"], "exit_code": child.returncode,
    }
    json_save(case / "supervised_reclaim_result.json", evidence)
    print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("asset", type=Path)
    args = parser.parse_args()
    folder = args.output.resolve()
    if not folder.is_relative_to(ROOT) or folder == ROOT:
        raise ValueError("output must be a new directory under this study")
    run(folder, args.asset.resolve())


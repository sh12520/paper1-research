"""Controlled process exit after CPU work, before durable task result publication."""

import argparse
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time

from offload_server import DurableLog
from run_pairs import ROOT, compute_edge, digest, json_save, wait_until
from task_store import TaskStore


def inputs(asset):
    payload = asset.read_bytes()
    return payload, {"first": digest(payload), "next": digest(payload)}


def child_main(case, asset):
    payload, bindings = inputs(asset)
    evidence = DurableLog(case / "inflight_events.jsonl")
    cutoff = time.monotonic_ns() + 2_000_000_000

    def compute_unpublished(data):
        actual = compute_edge(data)
        evidence("CPU_RETURNED_BEFORE_RESULT_COMMIT", task_id="first", result_sha256=digest(actual))
        print(json.dumps({"pid": os.getpid(), "cutoff_ns": cutoff}), flush=True)
        # Fault fixture: parent kills this process after seeing the gate.
        threading.Event().wait()
        return actual

    gate = TaskStore(case / "worker.sqlite", bindings, compute_unpublished, evidence)
    gate.arm("first", cutoff)
    grant = gate.grant("first")
    assert grant["status"] == "GRANTED"
    gate.execute("first", grant["token"], payload)


def probe(case, asset):
    case.mkdir(exist_ok=False)
    with (case / "inflight_stderr.log").open("ab") as err:
        child = subprocess.Popen(
            [sys.executable, "-B", __file__, str(case), str(asset), "--child"],
            stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        try:
            inbox = queue.Queue(1)
            threading.Thread(target=lambda: inbox.put(child.stdout.readline()), daemon=True).start()
            notice = json.loads(inbox.get(timeout=20))
            assert notice["pid"] == child.pid and child.poll() is None
            child.kill()
            exit_code = child.wait(timeout=5)
            assert exit_code != 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()

    wait_until(notice["cutoff_ns"] + 20_000_000)
    payload, bindings = inputs(asset)
    evidence = DurableLog(case / "inflight_events.jsonl")

    def unexpected_compute(_):
        raise AssertionError("no new execution is expected in the default recovery policy")

    gate = TaskStore(case / "worker.sqlite", bindings, unexpected_compute, evidence)
    try:
        prior = gate.status("first")
        assert prior["status"] == "IN_PROGRESS"
        assert gate.arm("next", time.monotonic_ns() + 1_500_000_000)["status"] == "ARMED"
        later = gate.grant("next")
        assert later["status"] == "BUSY"
    finally:
        gate.close()
        evidence.close()
    raw = [json.loads(x) for x in (case / "inflight_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(e["event"] == "CPU_RETURNED_BEFORE_RESULT_COMMIT" for e in raw) == 1
    assert sum(e["event"] == "APP_START" for e in raw) == 1
    assert not any(e["event"] in {"APP_COMPLETE", "APP_RELEASE"} for e in raw)
    result = {
        "scope": "controlled local process kill before committing pure calculation result",
        "initial_process_waited": True, "initial_process_exit_code": exit_code,
        "original_activation_cutoff_passed": time.monotonic_ns() > notice["cutoff_ns"],
        "first_state_after_restart": prior["status"], "next_attempt": later["status"],
        "original_worker_pid": notice["pid"], "recovery_process_pid": os.getpid(),
        "application_starts": 1, "durable_results": 0, "asset_sha256": digest(payload),
    }
    json_save(case / "inflight_result.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    case = args.output.resolve()
    if not case.is_relative_to(ROOT) or case == ROOT:
        raise ValueError("output must be a new directory under the study")
    if args.child:
        child_main(case, args.asset)
    else:
        probe(case, args.asset)


"""Execute one-worker, two-task pairs with independent application and edge processes."""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
import csv
import hashlib
import http.client
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time

from signed_rpc import Authenticator
from offload_server import KEY_ENV

ROOT = Path(__file__).resolve().parent
C2 = ROOT.parent.parent / "protocol" / "c2"
DEV1 = ROOT.parent / "service-worker"
sys.path[:0] = [str(C2), str(DEV1)]

from contracts import example_contract
from crypto import Identity, Trust
from events import Clock, Trace
from initiator import Initiator
from offload_server import DurableLog
from run_study import compute_edge, compute_local, digest, json_save

METHODS = ("C2_AUTH_QUERY", "DIRECT_LEASE")
CONDITIONS = ("clean", "first_proof_blackout")
ASSETS = ("astronaut.png", "camera.png", "coffee.png")
DEADLINE_MS = 800
FALLBACK_MS = 550
NEXT_RELEASE_MS = 900
NS_PER_MS = 1_000_000


class Rpc:
    def __init__(self, port, auth, log):
        self.port = port
        self.auth = auth
        self.log = log

    def transmit(self, route, body, timeout):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request("POST", route, body=body, headers={"Content-Type": "application/json"})
            reply = connection.getresponse()
            return reply.status, reply.read(2_500_001)
        finally:
            connection.close()

    def call(self, route, payload, timeout=1):
        nonce, request = self.auth.pack_request(route, payload)
        task = payload.get("task_id")
        self.log("APP_RPC_SEND", route=route, task_id=task, body_bytes=len(request))
        try:
            code, reply = self.transmit(route, request, timeout)
        except (OSError, http.client.HTTPException) as exc:
            self.log("APP_RPC_FAILURE", route=route, task_id=task, error=type(exc).__name__)
            return None
        if code != 200:
            raise AssertionError((route, code, reply[:150]))
        outcome = self.auth.unpack_reply(route, nonce, reply)
        self.log("APP_RPC_RECEIVE", route=route, task_id=task, body_bytes=len(reply), status=outcome["status"])
        return outcome


@contextmanager
def service(directory, key, log):
    child_env = {**os.environ, KEY_ENV: key.hex(), "PYTHONDONTWRITEBYTECODE": "1"}
    with (directory / "server_stderr.log").open("ab") as error:
        child = subprocess.Popen(
            [sys.executable, "-B", str(ROOT / "offload_server.py"), str(directory)],
            cwd=directory, env=child_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=error, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        try:
            mailbox = queue.Queue(1)
            reader = threading.Thread(target=lambda: mailbox.put(child.stdout.readline()), daemon=True)
            reader.start()
            line = mailbox.get(timeout=20)
            if not line:
                raise RuntimeError("edge process exited before readiness; see server_stderr.log")
            ready = json.loads(line)
            assert ready["pid"] == child.pid and child.pid != os.getpid()
            rpc = Rpc(ready["worker_port"], Authenticator(key), log)
            yield ready, rpc
            stopped = rpc.call("/shutdown", {})
            assert stopped and stopped["status"] == "STOPPING"
            assert child.wait(timeout=8) == 0
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()


def wait_until(target_ns):
    time.sleep(max(0.0, (target_ns - time.monotonic_ns()) / 1e9))


def exchange(rpc, route, payload, cutoff_ns):
    remain = (cutoff_ns - time.monotonic_ns()) / 1e9
    if remain <= 0:
        return None
    return rpc.call(route, payload, timeout=min(remain, 0.15))


def remote_attempt(rpc, task, payload, expected, cutoff, method, control, log):
    message = {"task_id": task}
    permit = exchange(rpc, "/grant", message, cutoff) if method == "DIRECT_LEASE" else None
    while not permit or permit["status"] != "GRANTED":
        if time.monotonic_ns() >= cutoff:
            return None
        if control is not None and control.done() and control.result()["status"] == "REJECTED":
            log("C2_APPLICATION_REJECT", task_id=task)
            return None
        permit = exchange(rpc, "/status", message, cutoff)
        if not permit or permit["status"] != "GRANTED":
            time.sleep(0.045)
    if permit["task_id"] != task:
        raise AssertionError("wrong task in proof")
    response = exchange(rpc, "/execute", {
        **message, "token": permit["token"], "payload_b64": base64.b64encode(payload).decode(),
    }, cutoff)
    if not response or response["status"] != "RESULT":
        return None
    data = base64.b64decode(response["result_b64"], validate=True)
    if expected != digest(data) or response["result_sha256"] != expected or response["task_id"] != task:
        raise AssertionError("wrong input or stale result")
    log("EDGE_OUTPUT_VERIFIED", task_id=task, result_sha256=expected)
    return time.monotonic_ns()


def run_task(executor, rpc, ready, c2_identity, case, task, payload, refs, method, log):
    release = time.monotonic_ns()
    cutoff = release + FALLBACK_MS * NS_PER_MS
    deadline = release + DEADLINE_MS * NS_PER_MS
    log("RELEASE", task_id=task, release_ns=release, cutoff_ns=cutoff, deadline_ns=deadline)
    armed = rpc.call("/arm", {"task_id": task, "cutoff_ns": cutoff})
    assert armed and armed["status"] == "ARMED"
    control = None
    client = None
    if method == "C2_AUTH_QUERY":
        trust = Trust([c2_identity.pin(), ready["authority_pin"]])
        clock = Clock("DEV02-LOCAL", "c2-initiator")
        trace = Trace("initiator", clock, case / (task + "_c2_client.jsonl"))
        client = Initiator(case / (task + "_c2_client.sqlite"), example_contract(), c2_identity, trust, clock, trace)
        control = executor.submit(client.run, "127.0.0.1", ready["c2_port"], task, task, 1)
    operation = executor.submit(
        remote_attempt, rpc, task, payload, refs["edge"], cutoff, method, control, log
    )
    try:
        remote_ns = operation.result(timeout=max(0, (cutoff - time.monotonic_ns()) / 1e9))
    except TimeoutError:
        remote_ns = None
    if remote_ns is not None and remote_ns < cutoff and time.monotonic_ns() < cutoff:
        mode = "edge"
        selected_hash = refs["edge"]
    else:
        wait_until(cutoff)
        mode = "local"
        log("LOCAL_START", task_id=task)
        selected_hash = digest(compute_local(payload))
        assert selected_hash == refs["local"]
        log("LOCAL_COMPLETE", task_id=task, result_sha256=selected_hash)
    published = time.monotonic_ns()
    log("PUBLISHED", task_id=task, mode=mode, result_sha256=selected_hash, publish_ns=published)
    row = {
        "task_id": task, "published_source": mode, "on_time": published < deadline,
        "latency_ms": (published - release) / NS_PER_MS, "result_sha256": selected_hash,
        "release_ns": release, "publish_ns": published,
    }
    return row, (client, control, operation)


def run_pair(path, method, condition, pair):
    path.mkdir()
    identity = Identity("initiator", "initiator") if method == "C2_AUTH_QUERY" else None
    config = {"method": method, "condition": condition,
              "inputs": {t: digest(sample[1]) for t, sample in pair.items()}}
    if identity:
        config["initiator_pin"] = identity.pin()
    json_save(path / "config.json", config)
    log = DurableLog(path / "app_events.jsonl")
    rows = []
    try:
        with service(path, secrets.token_bytes(32), log) as (ready, rpc):
            json_save(path / "endpoint_pids.json", {"app_pid": os.getpid(), "worker_pid": ready["pid"]})
            with ThreadPoolExecutor(max_workers=4) as executor:
                pending = []
                try:
                    for task, (name, input_bytes, refs) in pair.items():
                        if task == "next":
                            wait_until(rows[0]["release_ns"] + NEXT_RELEASE_MS * NS_PER_MS)
                        row, state = run_task(executor, rpc, ready, identity, path, task,
                                              input_bytes, refs, method, log)
                        row.update({"pair_id": path.name, "method": method,
                                    "condition": condition, "asset": name, "worker_pid": ready["pid"]})
                        rows.append(row)
                        pending.append(state)
                    for row, (client, control, operation) in zip(rows, pending):
                        operation.result(timeout=2)
                        row["c2_state"] = control.result(timeout=7)["status"] if control else None
                finally:
                    for client, control, _ in pending:
                        if client is not None:
                            if control is not None:
                                control.result(timeout=7)
                            client.close()
            for row in rows:
                outcome = rpc.call("/status", {"task_id": row["task_id"]})
                assert outcome is not None
                row["application_slot_final"] = outcome["status"]
    finally:
        log.close()
    json_save(path / "pair.json", rows)
    print(path.name, [(r["task_id"], r["published_source"], r["on_time"], r["c2_state"]) for r in rows], flush=True)
    return rows


def load_assets(root):
    result = []
    for name in ASSETS:
        payload = (root / name).read_bytes()
        result.append((name, payload, {"edge": digest(compute_edge(payload)), "local": digest(compute_local(payload))}))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT:
        raise ValueError("out must be a new directory under the study")
    out.mkdir(exist_ok=False)
    assets = load_assets(args.assets)
    json_save(out / "manifest.json", {
        "scope": "two_windows_processes_localhost_application_faults_development",
        "deadline_ms": DEADLINE_MS, "fallback_ms": FALLBACK_MS, "next_release_ms": NEXT_RELEASE_MS,
        "methods": METHODS, "conditions": CONDITIONS, "command": sys.argv,
        "assets": {name: {"sha256": digest(payload), "outputs": refs} for name,payload,refs in assets},
        "files": {p.name: digest(p.read_bytes()) for p in ROOT.glob("*.py")},
        "frozen_c2": {p.name: digest(p.read_bytes()) for p in C2.iterdir() if p.is_file()},
        "workload_sha256": digest((DEV1 / "run_study.py").read_bytes()),
        "spec_sha256": digest((ROOT / "STUDY_SPEC.md").read_bytes()),
    })
    rows = []
    for c, condition in enumerate(CONDITIONS):
        for index, first in enumerate(assets):
            pair = {"first": first, "next": assets[(index + 1) % len(assets)]}
            methods = METHODS if (c + index) % 2 == 0 else METHODS[::-1]
            for method in methods:
                rows.extend(run_pair(out / f"{c}-{index}-{method.lower()}", method, condition, pair))
    with (out / "per_task.csv").open("x", newline="", encoding="utf-8") as handle:
        table = csv.DictWriter(handle, fieldnames=list(rows[0]))
        table.writeheader()
        table.writerows(rows)


if __name__ == "__main__":
    main()


"""Paired development experiment with actual CPU work and injected loopback faults."""

from __future__ import annotations

import argparse
import base64
import csv
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import hashlib
import http.client
import io
import json
from pathlib import Path
import platform
import sqlite3
import sys
import threading
import time

from PIL import Image, ImageFilter, __version__ as pillow_version

from edge_worker import EdgeEndpoint

ROOT = Path(__file__).resolve().parent
C2_PATH = ROOT.parent / "RDINP_PREFLIGHT_20261127-123820" / "runs" / "source"
sys.path.insert(0, str(C2_PATH))

from contracts import example_contract
from crypto import Identity, Trust
from authority import Authority
from endpoint import Responder
from events import Clock, Trace
from initiator import Initiator

IMAGES = ("astronaut.png", "camera.png", "coffee.png")
METHODS = ("C2_CONFIRM", "C2_QUERY", "IDEMPOTENT_LEASE")
SCENARIOS = ("clean", "first_reply_lost", "commit_replies_lost", "commit_and_status_unavailable")
DEADLINE_MS = 800
LOCAL_BUDGET_MS = 250
QUERY_FIRST_MS = 100
QUERY_INTERVAL_MS = 60
NANOSECONDS_PER_MS = 1_000_000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ms(duration_ns: int) -> float:
    return duration_ns / NANOSECONDS_PER_MS


def json_save(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_edges(payload: bytes, side: int) -> bytes:
    with Image.open(io.BytesIO(payload)) as image:
        gray = image.convert("L").resize((side, side), Image.Resampling.BILINEAR)
    edge_map = gray.filter(ImageFilter.GaussianBlur(radius=1)).filter(ImageFilter.FIND_EDGES)
    result = io.BytesIO()
    edge_map.save(result, format="PNG", compress_level=1)
    return result.getvalue()


def compute_edge(payload: bytes) -> bytes:
    return detect_edges(payload, 512)


def compute_local(payload: bytes) -> bytes:
    return detect_edges(payload, 256)


class EventLog:
    def __init__(self):
        self.lock = threading.Lock()
        self.events = []

    def emit(self, event, **fields):
        with self.lock:
            self.events.append({
                "index": len(self.events),
                "monotonic_ns": time.monotonic_ns(),
                "event": event,
                **fields,
            })

    def save(self, path: Path):
        path.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in self.events),
            encoding="utf-8",
        )


def call_worker(edge, log, route, payload, cutoff_ns, status_unavailable=False):
    if time.monotonic_ns() >= cutoff_ns:
        return None
    if route == "/status" and status_unavailable:
        log.emit("STATUS_REQUEST_SUPPRESSED", route=route)
        return None
    body = json.dumps(payload, separators=(",", ":")).encode()
    seconds_left = (cutoff_ns - time.monotonic_ns()) / 1_000_000_000
    if seconds_left <= 0:
        return None
    connection = http.client.HTTPConnection(edge.host, edge.port, timeout=min(seconds_left, 0.15))
    try:
        log.emit("WORKER_CALL", route=route, body_bytes=len(body))
        connection.request("POST", route, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("worker response too large")
        result = json.loads(raw)
        log.emit("WORKER_REPLY", route=route, body_bytes=len(raw), status=result["status"])
        return result
    except (OSError, http.client.HTTPException) as exc:
        log.emit("WORKER_IO_FAULT", route=route, error_type=type(exc).__name__)
        return None
    finally:
        connection.close()


def grant_and_status(edge, log, request, cutoff, status_unavailable):
    for _ in range(2):
        direct = call_worker(edge, log, "/grant", request, cutoff)
        if direct and direct["status"] == "GRANTED":
            return direct
        queried = call_worker(edge, log, "/status", request, cutoff, status_unavailable)
        if queried and queried["status"] == "GRANTED":
            return queried
        if time.monotonic_ns() >= cutoff:
            break
    return None


def wait_c2_or_query(edge, log, request, cutoff, control, method, release_ns, status_unavailable):
    next_query = release_ns + QUERY_FIRST_MS * NANOSECONDS_PER_MS
    while time.monotonic_ns() < cutoff:
        if control.done():
            result = control.result()
            if result["confirmationComplete"] and result["effectKnowledge"] == "COMMITTED":
                return call_worker(edge, log, "/status", request, cutoff, status_unavailable)
            if method == "C2_CONFIRM":
                return None
        if method == "C2_QUERY" and time.monotonic_ns() >= next_query:
            result = call_worker(edge, log, "/status", request, cutoff, status_unavailable)
            if result and result["status"] == "GRANTED":
                return result
            next_query = time.monotonic_ns() + QUERY_INTERVAL_MS * NANOSECONDS_PER_MS
        time.sleep(0.004)
    return None


def run_remote(edge, log, source, expected, request, cutoff, control, method, release_ns, scenario):
    status_unavailable = scenario == "commit_and_status_unavailable"
    if method == "IDEMPOTENT_LEASE":
        grant = grant_and_status(edge, log, request, cutoff, status_unavailable)
    else:
        grant = wait_c2_or_query(
            edge, log, request, cutoff, control, method, release_ns, status_unavailable
        )
    if not grant or grant["status"] != "GRANTED" or grant["task_id"] != request["task_id"]:
        return None
    log.emit("APP_GRANT_EVIDENCE", task_id=grant["task_id"])
    payload = {**request, "token": grant["token"], "payload_b64": base64.b64encode(source).decode()}
    result = call_worker(edge, log, "/execute", payload, cutoff)
    if not result or result["status"] != "RESULT":
        return None
    result_bytes = base64.b64decode(result["result_b64"], validate=True)
    if result["task_id"] != request["task_id"] or digest(result_bytes) != expected:
        raise AssertionError("wrong task or wrong result")
    if result["result_sha256"] != expected:
        raise AssertionError("wrong edge digest")
    received = time.monotonic_ns()
    log.emit("APP_REMOTE_VALIDATED", output_sha256=expected, result_bytes=len(result_bytes))
    return received


def run_case(case_root, method, scenario, source, reference, task_id):
    case_root.mkdir()
    log = EventLog()
    request = {"task_id": task_id}
    grant_fault = {
        "clean": "none",
        "first_reply_lost": "drop_once",
        "commit_replies_lost": "drop",
        "commit_and_status_unavailable": "drop",
    }[scenario]
    control_result = None
    with EdgeEndpoint(
        task_id, digest(source), compute_edge, log.emit,
        grant_reply_fault=grant_fault if method == "IDEMPOTENT_LEASE" else "none",
    ) as edge:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responder = client = None
            if method != "IDEMPOTENT_LEASE":
                contract = example_contract()
                initiator_id = Identity("initiator", "initiator")
                responder_id = Identity("authority", "responder")
                trust = Trust([initiator_id.pin(), responder_id.pin()])
                sc = Clock("LOCAL-EDGE-STUDY", "server-monotonic")
                cc = Clock("LOCAL-EDGE-STUDY", "client-monotonic")
                st = Trace("responder", sc, case_root / "rdinp_server.jsonl")
                ct = Trace("initiator", cc, case_root / "rdinp_client.jsonl")
                authority = Authority(case_root / "quota.sqlite", contract, sc, st)
                commit_replies = 0
                response_lock = threading.Lock()

                def response_policy(message, kind, body):
                    nonlocal commit_replies
                    if kind != "RECEIPT" or body["status"] != "COMMITTED":
                        return {}
                    edge.grant(task_id)
                    with response_lock:
                        commit_replies += 1
                        drop = grant_fault == "drop" or (
                            grant_fault == "drop_once" and commit_replies == 1
                        )
                    if drop:
                        log.emit("C2_COMMIT_REPLY_SUPPRESSED", phase=message["phase"])
                    return {"drop": drop}

                responder = Responder(authority, responder_id, trust, st, response_policy).start()
                client = Initiator(case_root / "client.sqlite", contract, initiator_id, trust, cc, ct)

            try:
                release = time.monotonic_ns()
                deadline = release + DEADLINE_MS * NANOSECONDS_PER_MS
                cutoff = release + (DEADLINE_MS - LOCAL_BUDGET_MS) * NANOSECONDS_PER_MS
                edge.arm(cutoff)
                log.emit("APP_RELEASE", release_ns=release, deadline_ns=deadline, fallback_cutoff_ns=cutoff)
                if client:
                    control = executor.submit(client.run, responder.host, responder.port, task_id, task_id, 1)
                else:
                    control = None
                remote = executor.submit(
                    run_remote, edge, log, source, reference["edge_sha256"], request,
                    cutoff, control, method, release, scenario,
                )
                try:
                    received = remote.result(timeout=max(0, (cutoff - time.monotonic_ns()) / 1e9))
                except TimeoutError:
                    received = None
                if received is not None and received < cutoff and time.monotonic_ns() < cutoff:
                    selected = "edge"
                    selected_hash = reference["edge_sha256"]
                else:
                    # All arms use the same application fallback time.
                    time.sleep(max(0, (cutoff - time.monotonic_ns()) / 1e9))
                    log.emit("LOCAL_START")
                    output = compute_local(source)
                    selected = "local"
                    selected_hash = digest(output)
                    if selected_hash != reference["local_sha256"]:
                        raise AssertionError("local result differs from reference")
                    log.emit("LOCAL_COMPLETE", output_sha256=selected_hash, result_bytes=len(output))
                published = time.monotonic_ns()
                log.emit("APP_FINAL", selected=selected, publish_ns=published, output_sha256=selected_hash)
                if control:
                    control_result = control.result(timeout=8)
                    client.drain()
                    log.emit("C2_TERMINAL_OBSERVED", value=control_result)
                remote.result(timeout=3)
            finally:
                if client:
                    client.close()
                if responder:
                    responder.close()

    log.save(case_root / "events.jsonl")
    starts = [e for e in log.events if e["event"] == "EDGE_START"]
    grants = [e for e in log.events if e["event"] == "EDGE_GRANT"]
    releases = [e for e in log.events if e["event"] == "EDGE_RELEASE"]
    assert len(starts) <= 1 and len(grants) <= 1
    assert len(grants) == len(releases)
    assert not starts or starts[0]["monotonic_ns"] < cutoff
    assert sum(e["event"] == "APP_FINAL" for e in log.events) == 1
    selected_on_time = published < deadline
    missed_occupancy = sum(
        ms(e["monotonic_ns"] - g["monotonic_ns"])
        for e, g in zip(releases, grants) if e["release_reason"] == "expired_unused"
    )
    control_bytes = sum(
        e["body_bytes"] for e in log.events
        if e["event"] in ("WORKER_CALL", "WORKER_REPLY") and e["route"] in ("/grant", "/status")
    )
    # Count observed application body bytes. No HTTP headers, retransmissions below HTTP,
    # or responses deliberately suppressed before UDP/TCP egress are counted.
    if control_result is not None:
        for event in map(json.loads, (case_root / "rdinp_server.jsonl").read_text().splitlines()):
            if event["event"] in ("INGRESS", "RESPONSE_EGRESS"):
                control_bytes += len(base64.urlsafe_b64decode(event["rawBase64"] + "=" * (-len(event["rawBase64"]) % 4)))
    result = {
        "task_id": task_id,
        "method": method,
        "scenario": scenario,
        "selected": selected,
        "on_time": selected_on_time,
        "end_to_end_ms": ms(published - release),
        "edge_starts": len(starts),
        "edge_grants": len(grants),
        "unused_lease_ms": missed_occupancy,
        "granted_slot_ms": ms(releases[0]["monotonic_ns"] - grants[0]["monotonic_ns"]) if grants else 0,
        "output_side_pixels": 512 if selected == "edge" else 256,
        "valid_output_sha256": selected_hash,
        "source_bytes": len(source),
        "control_body_bytes": control_bytes,
        "data_body_bytes": sum(
            e["body_bytes"] for e in log.events
            if e["event"] in ("WORKER_CALL", "WORKER_REPLY") and e["route"] == "/execute"
        ),
        "rdinp_terminal": control_result["effectKnowledge"] if control_result else None,
    }
    json_save(case_root / "result.json", result)
    return result


def snapshot_inputs(asset_root):
    samples = {}
    for name in IMAGES:
        payload = (asset_root / name).read_bytes()
        edge = compute_edge(payload)
        local = compute_local(payload)
        samples[name] = (payload, {"edge_sha256": digest(edge), "local_sha256": digest(local)})
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError("--out must be a fresh directory under this study")
    output.mkdir(exist_ok=False)
    samples = snapshot_inputs(args.assets)
    json_save(output / "manifest.json", {
        "evidence_scope": "development_only_cpu_loopback_injected_message_faults",
        "deadline_ms": DEADLINE_MS, "local_budget_ms": LOCAL_BUDGET_MS,
        "query_first_ms": QUERY_FIRST_MS, "query_interval_ms": QUERY_INTERVAL_MS,
        "scenarios": SCENARIOS, "methods": METHODS,
        "python": sys.version, "pillow": pillow_version, "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(), "command": sys.argv,
        "sources": {p.name: digest(p.read_bytes()) for p in sorted(C2_PATH.iterdir()) if p.is_file()},
        "experiment_sources": {
            name: digest((ROOT / name).read_bytes()) for name in ("run_study.py", "edge_worker.py")
        },
        "assets": {name: {"source_sha256": digest(body), "bytes": len(body), **ref}
                   for name, (body, ref) in samples.items()},
    })
    rows = []
    for s, scenario in enumerate(SCENARIOS):
        for i, (name, (source, reference)) in enumerate(samples.items()):
            offset = (s + i) % len(METHODS)
            for method in METHODS[offset:] + METHODS[:offset]:
                run_id = f"{s}-{i}-{method.lower()}"
                row = run_case(output / run_id, method, scenario, source, reference, run_id)
                row["asset"] = name
                rows.append(row)
                print(run_id, row["selected"], row["on_time"], round(row["end_to_end_ms"], 3), flush=True)
    with (output / "per_case.csv").open("w", encoding="utf-8", newline="") as destination:
        csv_writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        csv_writer.writeheader()
        csv_writer.writerows(rows)


if __name__ == "__main__":
    main()


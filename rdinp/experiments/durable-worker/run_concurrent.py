"""G1-A development runner. All clocks are on one host, with actual CPU work."""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import ExitStack
import csv
import hashlib
from itertools import permutations
import json
from pathlib import Path
import platform
import secrets
import sys
import threading
import time
from uuid import uuid4

from concurrent_store import ConcurrentStore
from concurrent_transport import Client, Events, FaultWindows, serve

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "service-worker"))
from image_workload import compute_edge, compute_local

NS_PER_MS = 1_000_000
DEADLINE_NS = 800 * NS_PER_MS
FALLBACK_NS = 550 * NS_PER_MS
LEASE_NS = 150 * NS_PER_MS
RTO_NS = 25 * NS_PER_MS
METHODS = ("B0", "B1", "B2-info")
LOADS = (0.4, 0.7, 0.9)
CONDITIONS = ("clean", "uplink", "downlink", "both")
DECISION_PROTOCOL = "rdinp-g1a-20261127-v1"
DECISION_SHAPES = {(4, 1), (8, 2)}
DECISION_REPLICATES = 6
DECISION_TASKS = 12
REMOTE_TERMINAL = {"CANCELLED", "EXPIRED", "COMPUTE_FAILED", "CANCELLING"}
CANCEL_ACK = REMOTE_TERMINAL | {"RESULT"}


def wait_until(timestamp_ns):
    time.sleep(max(0.0, (timestamp_ns - time.monotonic_ns()) / 1_000_000_000))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def make_pair(pair_id, load, condition, terminals, slots, task_count, service_ns, digest, expected,
              use_c2=False, replicate=None):
    interval_ns = max(1, round(service_ns / (load * slots)))
    tasks = [
        {
            "task_id": f"{pair_id}-t{i:04d}",
            "terminal": i % terminals,
            "release_offset_ns": i * interval_ns,
            "deadline_ns": DEADLINE_NS,
            "fallback_ns": FALLBACK_NS,
            "input_sha256": digest,
            "expected_output_sha256": expected,
        }
        for i in range(task_count)
    ]
    if replicate is not None:
        for i in range(1, task_count - 1, 2):
            key = f"{terminals}/{slots}/{load:.1f}/{replicate}/{i}".encode("ascii")
            sign = 1 if hashlib.sha256(key).digest()[0] & 1 else -1
            tasks[i]["release_offset_ns"] += sign * (55 * interval_ns // 100)
    center = FALLBACK_NS
    if replicate is not None:
        center += tasks[replicate % 3]["release_offset_ns"]
        center += -RTO_NS if replicate < 3 else RTO_NS
    windows = []
    routes = ["/grant", "/status", "/execute", "/cancel"]
    if use_c2:
        routes.extend(("/rdinp/intent", "/rdinp/commit"))
    if condition != "clean":
        # A fixed outage window centered on the first fallback check. It does
        # not depend on the number of RPCs or outcomes in any arm.
        if condition in {"uplink", "both"}:
            windows.append({
                "direction": "uplink",
                "routes": routes,
                "start_ns": center - 120 * NS_PER_MS,
                "end_ns": center + 120 * NS_PER_MS,
            })
        if condition in {"downlink", "both"}:
            windows.append({
                "direction": "downlink",
                "routes": routes,
                "start_ns": center - 120 * NS_PER_MS,
                "end_ns": center + 120 * NS_PER_MS,
            })
    return {
        "pair_id": pair_id,
        **({"replicate": replicate, "method_order": list(permutations(METHODS))[replicate]}
           if replicate is not None else {}),
        "load": load,
        "condition": condition,
        "terminals": terminals,
        "slots": slots,
        "tasks": tasks,
        "windows": windows,
        "interrelease_ns": interval_ns,
    }


def receive_result(reply, expected_digest):
    payload = base64.b64decode(reply["result_b64"], validate=True)
    actual_digest = sha256(payload)
    if actual_digest != reply["result_sha256"] or actual_digest != expected_digest:
        raise ValueError("edge output differs from the frozen workload reference")
    return actual_digest


def seek_edge(client, task_id, encoded, expected, cutoff_ns, log):
    poll_status = False
    while time.monotonic_ns() < cutoff_ns:
        attempt_ns = time.monotonic_ns()
        first_route = "/status" if poll_status else "/grant"
        outcome = client.call(first_route, task_id, cutoff_ns)
        poll_status = outcome is None or outcome["status"] == "IN_PROGRESS"
        if outcome:
            status = outcome["status"]
            if status == "GRANTED":
                token = outcome["token"]
                outcome = client.call("/execute", task_id, cutoff_ns, token=token, payload_b64=encoded)
                # Query persisted status even if submit failed or its receipt was lost.
                poll_status = True
            elif status == "BUSY":
                log("READMISSION_WAIT", task_id=task_id, rto_ns=RTO_NS)
            elif status == "NOT_RELEASED":
                poll_status = False
        if outcome:
            if outcome["status"] == "RESULT":
                verified = receive_result(outcome, expected)
                observed_ns = time.monotonic_ns()
                log("EDGE_READBACK_VERIFIED", task_id=task_id, result_sha256=verified,
                    observed_ns=observed_ns, epoch=outcome.get("epoch"))
                if observed_ns < cutoff_ns:
                    return verified
                return None
            if outcome["status"] in REMOTE_TERMINAL:
                return None
        wait_until(min(attempt_ns + RTO_NS, cutoff_ns))
    return None


def cancel_on_wire(client, task_id, deadline_ns):
    while time.monotonic_ns() < deadline_ns:
        attempt_ns = time.monotonic_ns()
        reply = client.call("/cancel", task_id, deadline_ns)
        if reply and reply["status"] in CANCEL_ACK:
            return
        wait_until(min(attempt_ns + RTO_NS, deadline_ns))


def run_task(task, origin_ns, method, payload, encoded, minimum_quality, log,
             local_lock, client, oracle, cancellation, cancel_futures,
             approval, handshakes, handshake_futures, network, remote_futures):
    task_id = task["task_id"]
    release_ns = origin_ns + task["release_offset_ns"]
    deadline_ns = release_ns + task["deadline_ns"]
    fallback_ns = release_ns + task["fallback_ns"]
    wait_until(release_ns)
    log("RELEASE", task_id=task_id, terminal=task["terminal"],
        release_ns=release_ns, deadline_ns=deadline_ns, fallback_ns=fallback_ns)
    result = None
    fallback_started_ns = None
    if method != "B0":
        if approval is not None:
            handshake_futures.append(handshakes.submit(approval.negotiate, task))
        operation = network.submit(
            seek_edge, client, task_id, encoded, task["expected_output_sha256"]["edge"], fallback_ns, log,
        )
        remote_futures.append(operation)
        try:
            remaining = max(0.0, (fallback_ns - time.monotonic_ns()) / 1_000_000_000)
            result = operation.result(timeout=remaining)
        except TimeoutError:
            # A stalled socket or verification may finish independently. The
            # terminal's original fallback timer still owns the adoption decision.
            result = None
        edge_adopted_ns = time.monotonic_ns()
        if edge_adopted_ns >= fallback_ns:
            result = None
        if result is None:
            wait_until(fallback_ns)
            fallback_started_ns = time.monotonic_ns()
            log("FALLBACK", task_id=task_id, fallback_started_ns=fallback_started_ns,
                terminal=task["terminal"])
            if oracle is not None:
                log("ORACLE_INFO_DELIVERY", task_id=task_id, observed_ns=fallback_started_ns)
                cancel_futures.append(cancellation.submit(
                    oracle.cancel, task_id, reason="oracle_observed_fallback"
                ))
            cancel_futures.append(cancellation.submit(cancel_on_wire, client, task_id, deadline_ns))
    if result is None:
        source = "local"
        with local_lock:
            log("LOCAL_START", task_id=task_id, terminal=task["terminal"])
            result = sha256(compute_local(payload))
            if result != task["expected_output_sha256"]["local"]:
                raise ValueError("local result mismatch")
            log("LOCAL_COMPLETE", task_id=task_id, result_sha256=result)
    else:
        source = "edge"
    adopted_ns = edge_adopted_ns if source == "edge" else time.monotonic_ns()
    log("ADOPT", task_id=task_id, adopted_ns=adopted_ns, source=source,
        quality=source, output_sha256=result)
    return {
        "pair_id": task["pair_id"],
        "method": method,
        "task_id": task_id,
        "terminal": task["terminal"],
        "input_sha256": task["input_sha256"],
        "release_ns": release_ns,
        "deadline_ns": deadline_ns,
        "adopted_ns": adopted_ns,
        "source": source,
        "quality": source,
        "quality_ok": int(minimum_quality == "local" or source == "edge"),
        "verified": 1,
        "fallback_ns": fallback_ns,
        "fallback_started_ns": fallback_started_ns,
        "output_sha256": result,
    }


def run_case(out, pair, method, payload, run_id, minimum_quality, use_c2=False):
    path = out / "runs" / pair["pair_id"] / method
    path.mkdir(parents=True, exist_ok=False)
    tasks = pair["tasks"]
    with Events(path / "events.jsonl", run_id, pair["pair_id"], method) as log, ExitStack() as stack:
        approval = None
        if use_c2 and method != "B0":
            from concurrent_c2 import C2Authorization

            approval = stack.enter_context(C2Authorization(path / "c2", pair, None, log))
        origin_ns = time.monotonic_ns() + 350 * NS_PER_MS
        fault = FaultWindows(origin_ns, pair["windows"])
        if approval is not None:
            approval.set_fault(fault)
        log("CASE_START", origin_ns=origin_ns, scope="application_faults_same_host",
            authorization="frozen_bilateral_c2" if use_c2 else "prebound_application")
        locals_by_terminal = {i: threading.Lock() for i in range(pair["terminals"])}
        encoded = base64.b64encode(payload).decode("ascii")
        key = secrets.token_bytes(32)

        def run_terminals(port, oracle):
            cancel_futures = []
            handshake_futures = []
            remote_futures = []
            with ExitStack() as workers:
                cancellation = workers.enter_context(ThreadPoolExecutor(max_workers=len(tasks)))
                handshakes = workers.enter_context(ThreadPoolExecutor(max_workers=len(tasks))) if approval else None
                network = workers.enter_context(ThreadPoolExecutor(max_workers=len(tasks))) if port else None
                with ThreadPoolExecutor(max_workers=len(tasks)) as releases:
                    futures = []
                    for task in tasks:
                        terminal = task["terminal"]
                        client = Client(port, key, log, terminal) if port is not None else None
                        futures.append(releases.submit(
                            run_task, {**task, "pair_id": pair["pair_id"]}, origin_ns, method,
                            payload, encoded, minimum_quality, log,
                            locals_by_terminal[terminal], client, oracle, cancellation, cancel_futures,
                            approval, handshakes, handshake_futures, network, remote_futures,
                        ))
                    rows = [future.result() for future in futures]
                for future in cancel_futures:
                    future.result()
                for future in handshake_futures:
                    future.result()
                for future in remote_futures:
                    future.result()
                return rows

        if method == "B0":
            rows = run_terminals(None, None)
        else:
            specs = {}
            for task in tasks:
                release = origin_ns + task["release_offset_ns"]
                specs[task["task_id"]] = {
                    "input_sha256": task["input_sha256"],
                    "release_ns": release,
                    "fallback_ns": release + task["fallback_ns"],
                    "deadline_ns": release + task["deadline_ns"],
                    "public_fallback": True,
                }
            store = ConcurrentStore(path / "task_store.sqlite", specs, pair["slots"], LEASE_NS, log)
            try:
                with serve(store, key, fault, log, approval=approval) as port:
                    if time.monotonic_ns() >= origin_ns:
                        raise RuntimeError("edge became ready after the first planned release")
                    rows = run_terminals(port, store if method == "B2-info" else None)
            finally:
                store.close()
        if approval is not None:
            approval.finish()
        log("CASE_END", rows=len(rows))
    return rows


def calibrate(out, payload, digest, expected, slots, run_id, use_c2):
    pair = make_pair("calibration", 0.4, "clean", 4, slots, 4, DEADLINE_NS,
                     digest, expected, use_c2)
    # Deliberately spread these releases so we measure isolated occupancy,
    # including the actual grant, worker start, wait, and durable release.
    for index, task in enumerate(pair["tasks"]):
        task["release_offset_ns"] = index * (DEADLINE_NS + RTO_NS)
    rows = run_case(out / "calibration", pair, "B1", payload, run_id, "edge", use_c2)
    if any(row["source"] != "edge" or row["adopted_ns"] >= row["deadline_ns"] for row in rows):
        raise RuntimeError("clean calibration did not deliver every edge result")
    events_path = out / "calibration" / "runs" / "calibration" / "B1" / "events.jsonl"
    with events_path.open(encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle]
    grants = {e["task_id"]: e["monotonic_ns"] for e in events if e["event"] == "APP_GRANT"}
    releases = {e["task_id"]: e["release_ns"] for e in events if e["event"] == "APP_RELEASE"}
    if set(grants) != set(releases) or len(grants) != len(rows):
        raise RuntimeError("calibration grant/release coverage mismatch")
    elapsed_ns = [releases[task_id] - grants[task_id] for task_id in grants]
    if not all(duration > 0 for duration in elapsed_ns):
        raise RuntimeError("invalid calibration duration")
    mean_ms = sum(elapsed_ns) / len(elapsed_ns) / NS_PER_MS
    write_json(out / "calibration" / "measurement.json", {
        "definition": "same-host post-commit grant to post-commit release",
        "slot_occupancy_ns": elapsed_ns,
        "mean_ms": mean_ms,
    })
    return mean_ms


def calibrate_stop(out, payload, digest, slots, run_id):
    # Separate physical cancellation measurements, not scored releases.
    for trial in range(6):
        trial_id = f"trial-{trial:02d}"
        directory = out / "stop-calibration" / trial_id
        directory.mkdir(parents=True, exist_ok=False)
        release = time.monotonic_ns()
        tasks = {
            f"{trial_id}-{slot}": {
                "input_sha256": digest, "release_ns": release,
                "fallback_ns": release + FALLBACK_NS, "deadline_ns": release + DEADLINE_NS,
            } for slot in range(slots)
        }
        with Events(directory / "events.jsonl", run_id, trial_id, "stop-calibration") as log:
            log("CASE_START", scope="stop_calibration", slots=slots, origin_ns=release,
                input_sha256=digest,
                workload_sha256=sha256((HERE.parent / "service-worker" / "image_workload.py").read_bytes()))
            store = ConcurrentStore(directory / "task_store.sqlite", tasks, slots, LEASE_NS, log)
            try:
                for task_id in tasks:
                    grant = store.grant(task_id)
                    if grant["status"] != "GRANTED":
                        raise RuntimeError("unexpected stop-calibration admission")
                    store.execute(task_id, grant["token"], payload)
                for task_id in tasks:
                    store.cancel(task_id, reason="diagnostic_stop_calibration")
            finally:
                store.close()
            log("CASE_END", attempted=len(tasks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--service-ms", type=float,
                        help="Engineering override of the normally measured slot-occupancy mean")
    parser.add_argument("--terminals", type=int, choices=(4, 8), default=4)
    parser.add_argument("--slots", type=int, choices=(1, 2), default=1)
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--condition", choices=CONDITIONS, action="append")
    parser.add_argument("--c2-authorization", action="store_true",
                        help="Require a real persisted frozen C2 confirmation before application admission")
    parser.add_argument("--minimum-quality", choices=("local", "edge"), default="edge")
    parser.add_argument("--decision-study", action="store_true",
                        help="Use the frozen, counterbalanced G1-A paired plan")
    args = parser.parse_args()
    if (args.service_ms is not None and not 0.1 <= args.service_ms <= 800) \
            or not args.terminals <= args.tasks <= 64 \
            or not 1 <= args.replicates <= 100:
        parser.error("invalid engineering plan bounds")
    if len(set(args.condition or ())) != len(args.condition or ()):
        parser.error("condition may not be repeated")
    if args.decision_study and not (
        args.c2_authorization and args.condition is None and args.service_ms is None
        and args.minimum_quality == "edge" and (args.terminals, args.slots) in DECISION_SHAPES
        and args.tasks == DECISION_TASKS and args.replicates == DECISION_REPLICATES
    ):
        parser.error("decision study requires a frozen topology, all conditions, C2 and calibrated service")
    payload = args.asset.read_bytes()
    if len(payload) > 1_000_000:
        parser.error("asset exceeds the engineering payload limit")
    digest = sha256(payload)
    expected = {"edge": sha256(compute_edge(payload)), "local": sha256(compute_local(payload))}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    run_id = uuid4().hex
    service_ms = args.service_ms
    if service_ms is None:
        service_ms = calibrate(out, payload, digest, expected, args.slots, run_id, args.c2_authorization)
    conditions = tuple(args.condition or CONDITIONS)
    pairs = [
        make_pair(f"{replicate:03d}-{load:.1f}-{condition}", load, condition, args.terminals,
                  args.slots, args.tasks, round(service_ms * NS_PER_MS), digest, expected, args.c2_authorization,
                  replicate=replicate if args.decision_study else None)
        for replicate in range(args.replicates)
        for load in LOADS for condition in conditions
    ]
    source_files = [Path(__file__), HERE / "concurrent_store.py",
                    HERE / "concurrent_transport.py", HERE / "signed_rpc.py",
                    HERE.parent / "service-worker" / "image_workload.py"]
    if args.c2_authorization:
        source_files.append(HERE / "concurrent_c2.py")
    plan = {
        "schema": "rdinp-concurrent-v1",
        "scope": "g1a" if args.decision_study else "engineering",
        **({"decision_protocol": DECISION_PROTOCOL} if args.decision_study else {}),
        "authorization": "frozen_bilateral_c2" if args.c2_authorization else "prebound_application",
        "run_id": run_id,
        "methods": METHODS,
        "transport": "directional_application_fault_windows_on_loopback",
        "pairs": pairs,
        "minimum_quality": args.minimum_quality,
        "public_fallback": True,
        "lease_ns": LEASE_NS,
        "rto_ns": RTO_NS,
        "service_ms": service_ms,
        "service_source": "calibrated" if args.service_ms is None else "engineering_override",
        "source_sha256": {file.name: sha256(file.read_bytes()) for file in source_files},
        "python": platform.python_version(),
    }
    if args.c2_authorization:
        plan["frozen_c2_sha256"] = {
            p.name: sha256(p.read_bytes()) for p in (HERE.parent.parent / "protocol" / "c2").iterdir()
            if p.is_file()
        }
    write_json(out / "plan.json", plan)
    if args.decision_study:
        calibrate_stop(out, payload, digest, args.slots, run_id)
    rows = []
    for i, pair in enumerate(pairs):
        first = i % len(METHODS)
        for method in pair.get("method_order", METHODS[first:] + METHODS[:first]):
            rows.extend(run_case(out, pair, method, payload, run_id, args.minimum_quality,
                                 args.c2_authorization))
        pair_path = out / "runs" / pair["pair_id"] / "completed_rows.json"
        write_json(pair_path, rows[-len(METHODS) * len(pair["tasks"]):])
        print(pair["pair_id"], flush=True)
    with (out / "per_task.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

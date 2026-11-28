"""Measure frozen C2 four-phase signing and confirmation over actual loopback HTTP."""
import argparse
import collections
import json
import math
import multiprocessing as mp
import sqlite3
import statistics
import sys
import time
from pathlib import Path

C2 = Path(__file__).resolve().parents[2] / "protocol" / "c2"
sys.path.insert(0, str(C2))
from authority import Authority
from contracts import PHASES, example_contract, parse, sha
from crypto import Identity, Trust, unb64
from endpoint import Responder
from events import Clock, Trace
from initiator import Initiator


def relative_clock(name, origin):
    return Clock("local-cost-fixture", name, lambda: time.perf_counter_ns() - origin)


def timing(message, raw, elapsed_ns):
    return {**{key: message[key] for key in ("negotiationId", "phase", "attempt")},
            "raw_sha256": sha(raw), "duration_ns": elapsed_ns}


class TimedIdentity(Identity):
    def __init__(self, principal, role):
        super().__init__(principal, role)
        self.timings = []

    def sign(self, message):
        start = time.perf_counter_ns()
        result = super().sign(message)
        duration = time.perf_counter_ns() - start
        self.timings.append(timing(message, result, duration))
        return result


class TimedTrust(Trust):
    def __init__(self, pins):
        super().__init__(pins)
        self.timings = []

    def verify(self, raw, contract, principal, role):
        start = time.perf_counter_ns()
        message = super().verify(raw, contract, principal, role)
        duration = time.perf_counter_ns() - start
        self.timings.append(timing(message, raw, duration))
        return message


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def edge_process(path, connection, client_pin, repetitions):
    identity = TimedIdentity("authority", "responder")
    trust = TimedTrust([client_pin, identity.pin()])
    timer = relative_clock("isolated-edge", time.perf_counter_ns())
    trace = Trace("responder", timer)
    # Each independent C2 transaction consumes one unit of the fixture's logical quota.
    authority = Authority(path / "edge.sqlite", example_contract(), timer, trace, capacity=repetitions)
    with Responder(authority, identity, trust, trace) as endpoint:
        connection.send({"host": endpoint.host, "port": endpoint.port, "pin": identity.pin()})
        if connection.recv() != "stop":
            raise ValueError("unexpected runner message")
    write_json(path / "edge-trace.json",
               {"events": trace.events, "sign": identity.timings, "verify": trust.timings})


def percentiles(values):
    if not values:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"n": len(ordered), "p50": statistics.median(ordered),
            "p95": ordered[math.ceil(0.95 * len(ordered)) - 1], "max": ordered[-1]}


def checked_body(event):
    raw = unb64(event["rawBase64"])
    if sha(raw) != event["rawSha256"]:
        raise ValueError("C2 body trace digest mismatch")
    return raw


def index_events(trace, label, key):
    index = {}
    for row in trace["events"]:
        if row["event"] == label:
            if row[key] in index:
                raise ValueError(f"duplicate C2 {label} identity")
            index[row[key]] = row
    return index


def aggregate(path, trials):
    edge = json.loads((path / "edge-trace.json").read_text(encoding="utf-8"))
    client = json.loads((path / "client-trace.json").read_text(encoding="utf-8"))
    ingresses = index_events(edge, "INGRESS", "rawSha256")
    egresses = index_events(edge, "RESPONSE_EGRESS", "requestRawSha256")
    sends = index_events(client, "SEND_ACTUAL", "rawSha256")
    if not ingresses.keys() <= sends.keys() or not egresses.keys() <= ingresses.keys():
        raise ValueError("uncorrelated C2 endpoint event")

    attempt_by_hash = {}
    by_task = collections.defaultdict(list)
    for request_hash, request in sends.items():
        arrived, response = ingresses.get(request_hash), egresses.get(request_hash)
        request_body = checked_body(request)
        if arrived is not None and checked_body(arrived) != request_body:
            raise ValueError("request bytes changed in transit")
        reply_body = checked_body(response) if response is not None else None
        if reply_body is not None and parse(reply_body)["requestRawSha256"] != request_hash:
            raise ValueError("response not bound to request")
        row = {
            "task_id": request["negotiationId"], "phase": request["phase"],
            "attempt": request["attempt"], "request_sha256": request_hash,
            "request_submission_body_bytes": len(request_body),
            "request_edge_ingress_body_bytes": len(request_body) if arrived is not None else 0,
            "reply_body_bytes": len(reply_body) if reply_body is not None else 0,
            "reply_sha256": response["rawSha256"] if response is not None else None,
            "won_phase": False,
        }
        by_task[row["task_id"]].append(row)
        attempt_by_hash[request_hash] = row

    winners = collections.defaultdict(dict)
    for event in client["events"]:
        if event["event"] != "PHASE_WINNER_LATCH":
            continue
        exchange = attempt_by_hash[event["requestRawSha256"]]
        if exchange["reply_sha256"] != event["rawSha256"]:
            raise ValueError("winner does not match observed egress")
        wins = winners[event["negotiationId"]]
        if event["phase"] in wins:
            raise ValueError("multiple C2 phase winners")
        wins[event["phase"]] = {
            "request_body_bytes": exchange["request_edge_ingress_body_bytes"],
            "reply_body_bytes": exchange["reply_body_bytes"], "attempt": exchange["attempt"],
        }
        exchange["won_phase"] = True

    confirmed = []
    for task in trials:
        attempts = by_task[task["task_id"]]
        matched = winners[task["task_id"]]
        task["request_sends"] = len(attempts)
        task["reply_egresses"] = sum(row["reply_body_bytes"] > 0 for row in attempts)
        task["all_attempt_body_bytes"] = sum(
            row["request_submission_body_bytes"] + row["reply_body_bytes"] for row in attempts
        )
        task["peer_observed_body_bytes"] = sum(
            row["request_edge_ingress_body_bytes"] + row["reply_body_bytes"] for row in attempts
        )
        task["winning_exchanges"] = matched
        task["winning_body_bytes"] = sum(
            row["request_body_bytes"] + row["reply_body_bytes"] for row in matched.values()
        )
        if task["confirmation_complete"] and task["status"] == "COMMITTED":
            if tuple(matched) != PHASES:
                raise ValueError("complete C2 transaction lacks four ordered matched exchanges")
            confirmed.append(task)

    result = {
        "scope": "REAL_SOFTWARE_LOOPBACK_FOUR_PHASE_CONTROL_ONLY",
        "request_byte_boundary": "SEND_ACTUAL HTTP body, cross-checked against actual edge ingress",
        "response_byte_boundary": "successful server RESPONSE_EGRESS HTTP body",
        "trial_count": len(trials), "confirmed_count": len(confirmed),
        "statuses": dict(collections.Counter(t["status"] for t in trials)),
        "elapsed_release_to_terminal_ms": percentiles([t["release_to_terminal_ns"] / 1e6 for t in trials]),
        "confirmed_elapsed_release_to_terminal_ms": percentiles(
            [t["release_to_terminal_ns"] / 1e6 for t in confirmed]
        ),
        "elapsed_protocol_only_ms": percentiles([t["protocol_elapsed_ns"] / 1e6 for t in trials]),
        "all_attempt_body_bytes": percentiles([t["all_attempt_body_bytes"] for t in trials]),
        "winning_body_bytes_confirmed": percentiles([t["winning_body_bytes"] for t in confirmed]),
        "actual_body_bytes_per_released_task": sum(t["all_attempt_body_bytes"] for t in trials) / len(trials),
        "requests_without_peer_ingress": len(sends) - len(ingresses),
        "complete_within_400ms_control_only": sum(t["release_to_terminal_ns"] < 400e6 for t in confirmed),
        "sign_verify_ms": {
            f"{role}_{op}": percentiles([r["duration_ns"] / 1e6 for r in trace[op]])
            for role, trace in (("terminal", client), ("edge", edge)) for op in ("sign", "verify")
        },
        "trials": trials, "attempts": list(attempt_by_hash.values()),
    }
    write_json(path / "c2_cost.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"trials", "attempts"}}))


def measure_task(path, address, task_id, contract, identity, trust):
    origin = time.perf_counter_ns()
    trace = Trace("initiator", relative_clock(task_id, origin))
    release = time.perf_counter_ns()
    initiator = Initiator(path / f"{task_id}.sqlite", contract, identity, trust, trace.clock, trace)
    start = time.perf_counter_ns()
    try:
        result = initiator.run(*address, task_id, f"{task_id}-intent", 1)
        returned = time.perf_counter_ns()
    finally:
        initiator.close()
    boundaries = {event["event"]: event["observedNs"] for event in trace.events}
    last, first = boundaries.get("TERMINAL_PUBLISHED"), boundaries.get("NEGOTIATION_START")
    if last is None or first is None:
        raise ValueError(f"{task_id} has incomplete publication timing")
    protocol_ns = last - first
    release_to_terminal_ns = origin + last - release
    return {
        "task_id": task_id, "status": result["status"], "confirmation_complete": result["confirmationComplete"],
        "release_to_terminal_ns": release_to_terminal_ns, "protocol_elapsed_ns": protocol_ns,
        "release_to_return_ns": returned - release, "release_ns": release,
        "declared_deadline_met": result.get("beforeDeadline", False), "initialization_ns": start - release,
    }, trace.events


def run(path, repetitions):
    if not 2 <= repetitions <= 2000:
        raise ValueError("2–2000 serial control trials required")
    path.mkdir(parents=True, exist_ok=False)
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe()
    identity = TimedIdentity("initiator", "initiator")
    server = ctx.Process(target=edge_process, args=(path, child, identity.pin(), repetitions))
    server.start()
    child.close()
    try:
        if not parent.poll(30):
            raise RuntimeError("standalone C2 edge not ready")
        ready = parent.recv()
        trust = TimedTrust([identity.pin(), ready["pin"]])
        contract = example_contract()
        task_ids = [f"cost-{i:04d}" for i in range(repetitions)]
        write_json(path / "inputs.json", {
            "plan": contract.plan, "policy": contract.policy, "timing": contract.timing,
            "public_pins": [identity.pin(), ready["pin"]],
            "released_tasks": task_ids, "units_per_task": 1, "independent_edge_pid": server.pid,
            "application_reference_deadline_ms": 400,
            "measurement_clock": "time.perf_counter_ns, monotonic, per process",
            "runner_sha256": sha(Path(__file__).read_bytes()),
            "protocol_source_manifest_sha256": sha((C2 / "SOURCE-FILES.json").read_bytes()),
            "python": sys.version,
            "note": "serial unloaded loopback C2; retains its own declared four-phase cutoffs",
        })
        trials, events = [], []
        address = ready["host"], ready["port"]
        for task_id in task_ids:
            row, trace = measure_task(path, address, task_id, contract, identity, trust)
            trials.append(row)
            events.extend(trace)
        write_json(path / "client-trace.json", {"events": events, "sign": identity.timings, "verify": trust.timings})
        parent.send("stop")
        server.join(30)
        if server.exitcode != 0:
            raise RuntimeError(f"standalone C2 edge exit {server.exitcode}")
        # A durable successful C2 transaction must have exactly one commit effect.
        with sqlite3.connect(path / "edge.sqlite") as db:
            counts = dict(db.execute("SELECT neg, count(*) FROM effects WHERE event='COMMIT' GROUP BY neg"))
        if any(count != 1 for count in counts.values()):
            raise ValueError("duplicate committed C2 effect")
        for task in trials:
            if task["status"] == "COMMITTED" and counts.get(task["task_id"], 0) != 1:
                raise ValueError("confirmed C2 transaction missing durable effect")
        aggregate(path, trials)
    finally:
        parent.close()
        if server.is_alive():
            server.terminate()
            server.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=24)
    args = parser.parse_args()
    run(args.out.resolve(), args.trials)

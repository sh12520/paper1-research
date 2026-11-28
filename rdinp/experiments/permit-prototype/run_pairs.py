"""Actual loopback pairings with shared, time-indexed rate limits on HTTP bodies."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import csv
from dataclasses import asdict, dataclass
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import threading
import time

from adoption import fallback, wait_until

HERE = Path(__file__).resolve().parent
RDINP = HERE.parents[1]
STEP1 = HERE.parent / "structured-fast-slow"
PERMIT = RDINP / "protocol" / "permit-v1"
sys.path.insert(0, str(STEP1))
from calibrate import IMAGES, SIDE, detect_edges, edge_values, similarity, transport_input

sys.path.insert(0, str(PERMIT))
from permit import AdoptionGuard, Client, TransportError, start_server, write_config

MS = 1_000_000
DEADLINE_MS = 400
FALLBACK_RESERVE_MS = 55
SLOT_COUNT = 2
PRINCIPALS = ("terminal-a", "terminal-b")
MODES = ("Structured-RDINP", "Reactive-ReNeg")
TRACE = {
    "plain": [(0, 24, 36)],
    "half": [(0, 12, 18)],
    "dynamic": [(0, 24, 36), (104, 12, 18), (658, 24, 36),
                (1010, 12, 18), (1540, 24, 36)],
}
REPETITIONS = 4
PERMIT_TTL_MS = 900
SNAPSHOT_MAX_AGE_NS = 55 * MS
RELEASE_GRID = (
    (0, 0, 0), (29, 1, 0), (88, 0, 0), (117, 1, 0),
    (185, 0, 0), (255, 1, 0), (402, 0, 0), (515, 1, 0),
    (915, 0, 1), (948, 1, 1), (995, 0, 1), (1070, 1, 1),
    (1142, 0, 1), (1205, 1, 1), (1365, 0, 1), (1440, 1, 1),
)
BASE_TRANSIT_NS = 4 * MS
CALIBRATION = json.loads((STEP1 / "calibration.json").read_text(encoding="utf-8"))
CPU = {
    tier: round(max(row[tier]["cpu_ms"] for row in CALIBRATION["workloads"].values()) * MS)
    for tier in ("main", "light")
}


def record_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    candidates = [
        Path(__file__), HERE / "adoption.py", RDINP / "requirements.txt",
        PERMIT / "permit.py", PERMIT / "permit_server.py",
        PERMIT / "permit_wire.py", PERMIT / "permit.schema.json",
        RDINP / "protocol/c2/contracts.py", RDINP / "protocol/c2/crypto.py",
        RDINP / "protocol/c2/trust.schema.json",
        HERE.parent / "service-worker/image_workload.py",
        STEP1 / "calibrate.py", STEP1 / "calibration.json",
    ]
    return {p.relative_to(RDINP).as_posix(): sha(p.read_bytes()) for p in candidates}


def quantile(values, p):
    values = sorted(values)
    index = (len(values) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


@dataclass(frozen=True)
class Task:
    task_id: str
    release_ms: int
    terminal: int
    epoch_window: int
    image: str


def shared_task_plan(seed):
    rng = random.Random(f"RDINP-PERMIT-V1-PROTOTYPE:{seed}")
    return [
        Task(f"t-{i:02}", t + rng.randrange(8), terminal, epoch, rng.choice(IMAGES))
        for i, (t, terminal, epoch) in enumerate(RELEASE_GRID)
    ]


class SharedLink:
    """A real-time, FIFO serializer for each direction. Signals are causal for policies."""
    def __init__(self, origin_ns, events):
        self.origin_ns = origin_ns
        self.events = events
        self.starts = [origin_ns + n * MS for n, _, _ in events]
        self.ready = {"up": origin_ns, "down": origin_ns}
        self.lock = threading.Lock()
        self.events_sent = []
        self.rpc_events = []

    def rate(self, direction, at_ns):
        index = max(0, bisect_right(self.starts, at_ns) - 1)
        return self.events[index][1 if direction == "up" else 2]

    def forecast(self, direction, nbytes, now):
        # Do not expose the future impairment schedule or reservations in the medium.
        sampled = max(self.origin_ns, now - 10 * MS)
        return BASE_TRANSIT_NS + (8_000 * nbytes) // self.rate(direction, sampled)

    def reserve(self, direction, start_ns, nbytes):
        remaining = nbytes * 8_000
        idx = max(0, bisect_right(self.starts, start_ns) - 1)
        while idx + 1 < len(self.starts):
            rate = self.events[idx][1 if direction == "up" else 2]
            boundary = self.starts[idx + 1]
            service = rate * (boundary - start_ns)
            if remaining <= service:
                return start_ns + (remaining + rate - 1) // rate
            remaining -= service
            idx += 1
            start_ns = boundary
        rate = self.events[idx][1 if direction == "up" else 2]
        return start_ns + (remaining + rate - 1) // rate

    def transit(self, direction, task_id, cutoff_ns, kind, control_bytes, data_bytes):
        observed = time.perf_counter_ns()
        nbytes = control_bytes + data_bytes
        with self.lock:
            begin = max(observed, self.ready[direction])
            finish = self.reserve(direction, begin, nbytes)
            end = finish + BASE_TRANSIT_NS
            timely = end < cutoff_ns
            self.ready[direction] = max(self.ready[direction], min(finish, cutoff_ns))
            sample = {
                "task_id": task_id, "kind": kind, "direction": direction,
                "control_bytes": control_bytes, "data_bytes": data_bytes,
                "queued_ns": max(0, begin - observed),
                "scheduled_service_ns": max(0, min(finish, cutoff_ns) - begin),
                "emulated_delivery_allowed": timely,
            }
            self.events_sent.append(sample)
        wait_until(min(end, cutoff_ns))
        return timely and time.perf_counter_ns() < cutoff_ns

    def call(self, client, task_id, cutoff_ns, kind, body, payload=b""):
        remaining = (cutoff_ns - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            return None
        start = time.perf_counter_ns()
        reply = None
        try:
            reply = client.call(
                kind, body, payload, timeout_s=remaining,
                before_send=lambda operation, ctrl, data: self.transit(
                    "up", task_id, cutoff_ns, operation, ctrl, data),
                after_receive=lambda operation, ctrl, data: self.transit(
                    "down", task_id, cutoff_ns, operation, ctrl, data),
            )
        except (TransportError, TimeoutError) as error:
            measurement = getattr(error, "reply", None)
        else:
            measurement = reply
        event = {
            "task_id": task_id, "kind": kind,
            "status": reply.body["status"] if reply is not None else "NO_DELIVERY",
            "request_sent": getattr(measurement, "request_sent", False),
            "actual_elapsed_ns": time.perf_counter_ns() - start,
            "sign_ns": getattr(measurement, "signature_ns", None),
            "verify_ns": getattr(measurement, "verify_ns", None),
            "request_control_bytes": getattr(measurement, "request_control_bytes", None),
            "response_control_bytes": getattr(measurement, "response_control_bytes", None),
            "request_data_bytes": getattr(measurement, "request_data_bytes", None),
            "response_data_bytes": getattr(measurement, "response_data_bytes", None),
        }
        with self.lock:
            self.rpc_events.append(event)
        return reply


def load_assets(asset_dir):
    assets = {name: (asset_dir / name).read_bytes() for name in IMAGES}
    for name, data in assets.items():
        if sha(data) != CALIBRATION["input_fixtures"][name]["sha256"]:
            raise ValueError(f"input fixture digest mismatch: {name}")
    return assets


class Session:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.guard = AdoptionGuard()
        self.lock = threading.Lock()
        self.windows = {}
        self.current = None

    def permit(self, window, link, task_id, edge_cutoff):
        with self.lock:
            if window not in self.windows:
                self.current = None
                receipt = link.call(
                    self.client, task_id, edge_cutoff, "ISSUE",
                    {"session": self.name, "ttl_ms": PERMIT_TTL_MS,
                     "max_tasks": 4, "max_slots": SLOT_COUNT,
                     "max_input_bytes": 300_000, "max_budget_ms": DEADLINE_MS},
                )
                self.windows[window] = (
                    receipt.body["permit"] if receipt is not None and receipt.body["status"] == "PERMIT" else None
                )
                self.current = self.windows[window]
            return self.windows[window]

    def adopt(self, reply, task_id, digest, cutoff):
        with self.lock:
            return self.current is not None and self.guard.adopt(
                reply, task_id=task_id, input_sha256=digest, permit=self.current,
                cutoff_ns=cutoff, allowed_tiers=("main", "light"),
            )


def choose_tier(task, snapshot, link, cutoff):
    profile = CALIBRATION["workloads"][task.image]
    now = time.perf_counter_ns()
    for tier in ("main", "light"):
        row = profile[tier]
        finish = (
            now + round(row["prepare_ms"] * MS) + snapshot["wait_ns"] +
            snapshot["service_estimate_ns"][tier] +
            link.forecast("up", row["upload_bytes"] + 2048, now) +
            link.forecast("down", row["download_bytes"] + 2048, now)
        )
        if finish < cutoff:
            return tier
    return None


def remote(job, session, link, source, release, edge_cutoff, deadline, style, forced):
    permit = session.permit(job.epoch_window, link, job.task_id, edge_cutoff)
    meta = {"permit_ready_ns": time.perf_counter_ns(), "selected_input_tier": None,
            "snapshot_ns": None, "initial_offer": False, "requested_switch": False}
    if permit is None:
        return None, meta
    snap = link.call(session.client, job.task_id, edge_cutoff, "SNAPSHOT", {})
    if snap is None or snap.body["status"] != "SNAPSHOT":
        return None, meta
    meta["snapshot_ns"] = snap.body["observed_ns"]
    if (snap.body["authority_epoch"] != permit["body"]["authority_epoch"]
            or not 0 <= time.perf_counter_ns() - meta["snapshot_ns"] <= SNAPSHOT_MAX_AGE_NS):
        return None, meta
    input_tier = forced if forced else choose_tier(job, snap.body, link, edge_cutoff)
    if input_tier is None:
        return None, meta
    meta["selected_input_tier"] = input_tier
    payload = transport_input(source, SIDE[input_tier])
    digest = sha(payload)
    now = time.perf_counter_ns()
    tails = {
        tier: link.forecast("down", d["download_bytes"] + 2048, now)
        for tier, d in CALIBRATION["workloads"][job.image].items() if tier != "local"
    }
    accepted_tier = "light" if forced else input_tier
    body = {
        "permit": permit, "task_id": job.task_id, "input_sha256": digest,
        "input_tier": input_tier, "accepted_tier": accepted_tier,
        "release_ns": release, "edge_cutoff_ns": edge_cutoff, "deadline_ns": deadline,
        "post_upload": style, "tail_budget_ns": tails,
    }
    reply = link.call(session.client, job.task_id, edge_cutoff, "TASK", body, payload)
    if reply is not None and reply.body["status"] == "OFFER":
        meta["initial_offer"] = True
        if reply.body["task_id"] == job.task_id and reply.body["input_sha256"] == digest:
            meta["requested_switch"] = True
            reply = link.call(session.client, job.task_id, edge_cutoff, "SELECT",
                              {"permit": permit, "task_id": job.task_id, "input_sha256": digest, "tier": "light"})
    meta["task_status"] = reply.status if reply is not None else "NO_DELIVERY"
    meta["reject_reason"] = reply.body.get("reason") if reply is not None else None
    if reply is None or reply.body["status"] != "RESULT":
        return None, meta
    if not session.adopt(reply, job.task_id, digest, edge_cutoff):
        return None, meta
    adopted = time.perf_counter_ns()
    if adopted >= edge_cutoff:
        return None, meta
    return (reply, adopted), meta


def execute_task(job, session, link, assets, reference_values, local_lock, remotes, style, forced):
    r = link.origin_ns + job.release_ms * MS
    edge_cutoff = r + (DEADLINE_MS - FALLBACK_RESERVE_MS) * MS
    d = r + DEADLINE_MS * MS
    source = assets[job.image]
    wait_until(r)
    actual_release_ns = time.perf_counter_ns()
    future = remotes.submit(remote, job, session, link, source, r, edge_cutoff, d, style, forced)
    try:
        result, meta = future.result(timeout=max(0, edge_cutoff - time.perf_counter_ns()) / 1e9)
    except FutureTimeout:
        result, meta = None, {}
    if result is None:
        wait_until(edge_cutoff)
        with local_lock:
            payload, adopted, timely = fallback(source, d, edge_cutoff)
        grade = "local" if timely else "missed"
        queue_ns, service_ns = None, None
    else:
        reply, adopted = result
        payload, grade = reply.payload, reply.body["tier"]
        queue_ns, service_ns = reply.body["queue_ns"], reply.body["service_ns"]
    score = similarity(reference_values[job.image], edge_values(payload)) if grade != "missed" else 0.0
    return {
        **asdict(job), **meta, "release_ns": r, "dispatch_lag_ns": actual_release_ns - r,
        "edge_cutoff_ns": edge_cutoff, "deadline_ns": d, "adopted_ns": adopted,
        "grade": grade, "utility": score, "end_to_end_ms": (adopted - r) / MS,
        "queue_ns": queue_ns, "service_ns": service_ns, "result_sha256": sha(payload),
    }, future


def start(directory, slots):
    cfg = write_config(directory, PRINCIPALS, slots=slots, service_estimate_ns=CPU)
    portfile = directory / "port.txt"
    proc = start_server(cfg, portfile)
    give_up = time.monotonic() + 25
    while not portfile.exists() or not portfile.stat().st_size:
        if proc.poll() is not None or time.monotonic() >= give_up:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
            raise RuntimeError(f"loopback server failed to start: {directory}")
        time.sleep(0.005)
    return cfg, int(portfile.read_text(encoding="utf-8").strip()), proc


def measured_bytes(event, field):
    sent = event["request_" + field] if event["request_sent"] else 0
    return (sent or 0) + (event["response_" + field] or 0)


def execute_arm(directory, method, jobs, trace, assets, reference_values, style, forced=None):
    directory.mkdir()
    cfg, port, proc = start(directory, SLOT_COUNT)
    try:
        sessions = [
            Session(f"session-{index}", Client(cfg, port, principal))
            for index, principal in enumerate(PRINCIPALS)
        ]
        link = SharedLink(time.perf_counter_ns() + 90 * MS, trace)
        local = [threading.Lock() for _ in PRINCIPALS]
        with ThreadPoolExecutor(max_workers=len(jobs)) as tasks, ThreadPoolExecutor(max_workers=len(jobs)) as remotes:
            handles = [
                tasks.submit(execute_task, job, sessions[job.terminal], link, assets, reference_values,
                             local[job.terminal], remotes, style, forced)
                for job in jobs
            ]
            rows = []
            outstanding = []
            for handle in handles:
                row, remote_handle = handle.result()
                rows.append(row)
                outstanding.append(remote_handle)
            for row, remote_handle in zip(rows, outstanding):
                # Preserve diagnostics from the path even after timely local fallback.
                _, diagnostics = remote_handle.result()
                row.update(diagnostics)
        audit_reply = sessions[0].client.call("AUDIT", {}, timeout_s=.7)
        if audit_reply.body["status"] != "AUDIT":
            raise RuntimeError("experiment did not obtain a signed execution audit")
        record_json(directory/"authority-audit.json", audit_reply.body)
        record_json(directory/"tasks.json", rows)
        with gzip.open(directory/"wire.jsonl.gz", "wt", encoding="utf-8") as handle:
            for event in link.events_sent:
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        with gzip.open(directory/"rpc.jsonl.gz", "wt", encoding="utf-8") as handle:
            for event in link.rpc_events:
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")
        return {
            "method": method, "tasks": rows, "audit": audit_reply.body,
            "permit_total_elapsed_ns": sum(
                x["actual_elapsed_ns"] for x in link.rpc_events if x["kind"] == "ISSUE"),
            "permit_total_control_bytes": sum(
                measured_bytes(x, "control_bytes") for x in link.rpc_events if x["kind"] == "ISSUE"),
            "permit_confirmed": sum(
                x["kind"] == "ISSUE" and x["status"] == "PERMIT" for x in link.rpc_events),
            "terminal_sign_total_ns": sum(x["sign_ns"] or 0 for x in link.rpc_events),
            "terminal_verify_total_ns": sum(x["verify_ns"] or 0 for x in link.rpc_events),
            "control_body_bytes": sum(measured_bytes(x, "control_bytes") for x in link.rpc_events),
            "control_body_attempted_bytes": sum(x["control_bytes"] for x in link.events_sent),
            "data_body_bytes": sum(measured_bytes(x, "data_bytes") for x in link.rpc_events),
            "issue_requests": sum(x["kind"] == "ISSUE" and x["direction"] == "up" for x in link.events_sent),
            "extra_select_requests": sum(x["kind"] == "SELECT" and x["direction"] == "up" for x in link.events_sent),
        }
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def write_table(path, rows):
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--probe", action="store_true", help="non-scored engineering fixture")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    assets = load_assets(args.assets)
    reference_values = {name: edge_values(detect_edges(transport_input(src, 512), 512)) for name, src in assets.items()}
    fixed = [
        (condition, seed, shared_task_plan(seed)) for condition in TRACE
        for seed in range(REPETITIONS)
    ]
    if args.probe:
        fixed = fixed[-1:]
    plan = {
        "deadline_ms": DEADLINE_MS, "fallback_reserve_ms": FALLBACK_RESERVE_MS,
        "slots": SLOT_COUNT, "permit_ttl_ms": PERMIT_TTL_MS, "trace": TRACE,
        "counts_per_permit_generation": 4, "methods": MODES,
        "snapshot_max_age_ns": SNAPSHOT_MAX_AGE_NS,
        "scope": "engineering-probe" if args.probe else "real software, controlled link paired evaluation",
        "python": platform.python_version(), "host": platform.platform(),
        "source_sha256": sources(),
        "dependencies": {
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
        "asset_sha256": {name: sha(src) for name, src in assets.items()},
        "cases": [{"condition": condition, "seed": seed, "tasks": [asdict(job) for job in jobs]}
                  for condition, seed, jobs in fixed],
        "clock": "same-host perf_counter_ns (QPC on Windows)",
        "headroom_rule": "345 ms minus p95 measured release-to-adoption; absent or fallback sample counts as exhausted",
    }
    record_json(args.out/"plan.json", plan)
    # Cost and effects of both switch locations. No data from these paths enters the scored pairs.
    feasibility = []
    for input_tier in ("light", "main"):
        jobs = [Task(f"headroom-{i}", i * 410, 0, i // 2, name) for i, name in enumerate(IMAGES * 3)]
        out = execute_arm(args.out/f"headroom-{input_tier}", "headroom", jobs, TRACE["half"],
                          assets, reference_values, "auto", forced=input_tier)
        durations = [row["end_to_end_ms"] if row["grade"] == "light" else DEADLINE_MS
                     for row in out["tasks"]]
        margin = DEADLINE_MS - FALLBACK_RESERVE_MS - quantile(durations, .95)
        feasibility.append({"upload": input_tier, "margin_p95_ms": margin, "rows": out["tasks"]})
    record_json(args.out/"headroom.json", feasibility)
    permit_style = "auto" if feasibility[1]["margin_p95_ms"] > 0 else "none"
    arms = []
    tasks = []
    for index, (condition, seed, jobs) in enumerate(fixed):
        case = args.out/f"pair-{condition}-{seed}"
        case.mkdir()
        for method in MODES[index % 2:] + MODES[:index % 2]:
            style = permit_style if method == MODES[0] else "offer"
            out = execute_arm(case/method, method, jobs, TRACE[condition], assets, reference_values, style)
            arms.append({"condition": condition, "seed": seed, "style": style,
                         **{k: v for k, v in out.items() if k not in ("tasks", "audit")},
                         "audit_effects": out["audit"]["effects"], "audit_starts": out["audit"]["starts"]})
            tasks.extend({"condition": condition, "seed": seed, "method": method, **row} for row in out["tasks"])
        print(f"Paired arm completed: {condition}/{seed}", flush=True)
    if sources() != plan["source_sha256"]:
        raise RuntimeError("source changed during live paired experiment")
    write_table(args.out/"per_task.csv", tasks)
    write_table(args.out/"per_arm.csv", arms)
    record_json(args.out/"COMPLETE.json", {
        "pair_count": len(fixed), "method_runs": len(arms),
        "task_rows": len(tasks), "structured_style": permit_style,
        "sha256": {name: sha((args.out/name).read_bytes()) for name
                   in ("plan.json", "headroom.json", "per_task.csv", "per_arm.csv")},
    })


if __name__ == "__main__":
    main()

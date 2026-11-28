"""Explicit G1-A ideal-release sensitivity, never measured wall-clock evidence.

Compare two runs of one deterministic event model with calibrated or supplied
stop-to-reuse delay and zero delay. Only pure scratch-file CPU work is modeled
as cancellable. No modeled result enters the measured paired experiment gate.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path
from statistics import median

from concurrent_audit import decode, sha256_hex, stable_id


SCHEMA = "rdinp-ideal-release-sensitivity-v1"
NS_PER_MS = 1_000_000
TERMINAL = {"RESULT", "EXPIRED", "CANCELLED", "CANCELLING"}


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def median_ns(samples):
    return round(median(samples)) if samples else None


C2_MODE = "frozen_bilateral_c2"
STOP_EVENTS = {"APP_START", "APP_CANCEL_ACCEPTED", "APP_WORKER_EXIT_CONFIRMED", "APP_RELEASE"}
GRID_CANCEL_REASONS = {"oracle_observed_fallback", "terminal_fallback", "terminal_cancel", "public_execution_cutoff"}
CALIBRATION_REASON = "diagnostic_stop_calibration"


def clock_domain(event):
    return tuple(event[key] for key in ("host", "boot", "clock"))


def c2_lane_traces(path, directory, tasks, clock_ref, refs):
    commits, leases = {}, {}
    for terminal in sorted({task["terminal"] for task in tasks.values()}):
        lane = path.parent / "c2" / f"terminal-{terminal}" / "authority_events.jsonl"
        require(lane.is_file(), f"{lane}: authority trace unavailable")
        raw = lane.read_bytes()
        require(raw, f"{lane}: empty authority trace")
        refs[lane.relative_to(directory).as_posix()] = hashlib.sha256(raw).hexdigest()
        for index, line in enumerate(raw.splitlines()):
            event = decode(line)
            require(
                event["role"] == "responder" and event["boot"] == clock_ref["c2_boot"]
                and event["clockId"] == f"c2-authority-{terminal}" and event["unit"] == "NANOSECONDS"
                and event["ordinal"] == index,
                f"{lane}: unexpected authority lane identity or event order",
            )
            task_id = event.get("negotiationId")
            if task_id is not None:
                require(task_id in tasks and tasks[task_id]["terminal"] == terminal,
                        f"{lane}: unexpected authority task or owner")
            if event["event"] == "LEASE_ANCHOR":
                require(task_id is not None and task_id not in leases
                        and type(event["leaseUntilNs"]) is int and event["leaseUntilNs"] > 0,
                        f"{lane}: invalid or duplicate lease anchor")
                leases[task_id] = event
            if event["event"] == "DURABLE_COMMIT_RETURN" and event.get("effectTx") is not None:
                require(task_id is not None and task_id not in commits
                        and event["phase"] == "COMMIT_INITIAL"
                        and type(event["observedNs"]) is int and event["observedNs"] >= 0,
                        f"{lane}: invalid or duplicate committed effect")
                commits[task_id] = event
    return commits, leases


def c2_approval_inputs(path, directory, plan, pair, case_events, refs):
    events = defaultdict(list)
    for event in case_events:
        events[event["event"]].append(event)
    if not events["C2_FINAL_AUTHORIZATION"]:
        # Older C2 engineering runs did not preserve the final roster.
        return None
    for name in ("CASE_START", "CASE_END", "C2_CLOCK_BIND"):
        require(len(events[name]) == 1, f"{path}: missing or duplicated {name}")
    start, end, clock_ref = (events[name][0] for name in ("CASE_START", "CASE_END", "C2_CLOCK_BIND"))
    origin = start["origin_ns"]
    clock_origin = clock_ref["origin_ns"]
    require(
        start.get("authorization") == C2_MODE and end["rows"] == len(pair["tasks"])
        and type(origin) is int and type(clock_origin) is int
        and 0 <= clock_origin <= clock_ref["monotonic_ns"] <= start["monotonic_ns"] <= origin
        and all(clock_domain(e) == clock_domain(start) for e in case_events)
        and all(e["run_id"] == plan["run_id"] for e in case_events)
        and all(a["index"] < b["index"] and a["monotonic_ns"] <= b["monotonic_ns"]
                for a, b in zip(case_events, case_events[1:])),
        f"{path}: inconsistent C2 case or clock binding",
    )
    tasks = {task["task_id"]: task for task in pair["tasks"]}
    witness_by_event = {}
    for name in ("C2_TASK_BIND", "RELEASE", "C2_CLIENT_TERMINAL", "C2_FINAL_AUTHORIZATION", "C2_DURABLE_AUTHORIZED"):
        found = {}
        for e in events[name]:
            task_id = e.get("task_id")
            require(task_id in tasks and task_id not in found and e["negotiationId"] == task_id,
                    f"{path}: duplicate or unplanned {name} task")
            found[task_id] = e
        if name != "C2_DURABLE_AUTHORIZED":
            require(set(found) == set(tasks), f"{path}: incomplete {name} task roster")
        witness_by_event[name] = found

    commits, leases = c2_lane_traces(path, directory, tasks, clock_ref, refs)
    require(set(commits) == set(witness_by_event["C2_DURABLE_AUTHORIZED"]),
            f"{path}: authoritative durable commit roster mismatch")
    inputs = {}
    for task_id, task in tasks.items():
        binding, release, terminal, final = (
            witness_by_event[name][task_id]
            for name in ("C2_TASK_BIND", "RELEASE", "C2_CLIENT_TERMINAL", "C2_FINAL_AUTHORIZATION")
        )
        release_ns = origin + task["release_offset_ns"]
        expected_binding = {key: task[key] for key in (
            "task_id", "terminal", "input_sha256", "release_offset_ns", "fallback_ns", "deadline_ns",
        )}
        if "expected_output_sha256" in task:
            expected_binding["expected_output_sha256"] = task["expected_output_sha256"]
        expected_binding.update(pair_id=pair["pair_id"], timing_contract_digest=clock_ref["c2_contract_digest"],
                                authority="authority", initiator=f"terminal-{task['terminal']}")
        require(binding["binding"] == expected_binding and binding["terminal"] == task["terminal"]
                and binding["input_sha256"] == task["input_sha256"]
                and sha256_hex(binding["intentId"]) and terminal["intentId"] == binding["intentId"]
                and terminal["terminal"] == task["terminal"] and release["terminal"] == task["terminal"]
                and release["release_ns"] == release_ns and release["monotonic_ns"] >= release_ns
                and release["fallback_ns"] == release_ns + task["fallback_ns"]
                and release["deadline_ns"] == release_ns + task["deadline_ns"]
                and binding["index"] < start["index"] < release["index"] < terminal["index"] < final["index"] < end["index"],
                f"{path}: invalid C2 task or schedule binding for {task_id}")
        approval = final["approval"]
        state, commit_offset, ready = "no_durable_commit", None, None
        if task_id not in commits:
            require(approval is None, f"{path}: final proof without authoritative commit for {task_id}")
        else:
            commit, lease = commits[task_id], leases.get(task_id)
            observed = clock_origin + commit["observedNs"]
            prior = witness_by_event["C2_DURABLE_AUTHORIZED"][task_id]
            require(type(approval) is dict
                    and approval == {key: val for key, val in prior.items() if key.startswith("c2_")}
                    and release["monotonic_ns"] <= observed <= prior["monotonic_ns"] <= final["monotonic_ns"]
                    and prior["index"] < final["index"]
                    and lease is not None and lease["ordinal"] < commit["ordinal"]
                    and lease["intentId"] == commit["intentId"] == binding["intentId"] == approval["c2_intent_id"]
                    and observed == approval["c2_commit_return_ns"]
                    and commit["effectTx"] == approval["c2_commit_effect_tx"]
                    and commit["transactionId"] == approval["c2_commit_transaction_id"]
                    and commit["rawSha256"] == approval["c2_request_raw_sha256"]
                    and approval["c2_terminal"] == task["terminal"]
                    and approval["c2_authority_state"] == "CONFIRMED"
                    and approval["c2_commit_before_lease"] is (commit["observedNs"] < lease["leaseUntilNs"])
                    and sha256_hex(approval["c2_request_raw_sha256"])
                    and sha256_hex(approval["c2_receipt_digest"])
                    and sha256_hex(approval["c2_decision_digest"]),
                    f"{path}: final and authoritative C2 proof disagree for {task_id}")
            commit_offset = observed - origin
            state = "committed_before_lease" if approval["c2_commit_before_lease"] else "committed_after_lease"
            ready = commit_offset if approval["c2_commit_before_lease"] else None
        inputs[task_id] = {"task_id": task_id, "state": state, "c2_commit_offset_ns": commit_offset,
                           "grant_ready_ns": ready}
    return inputs


def matched_stop_delays(events, reasons, *, strict=False):
    grouped = defaultdict(lambda: defaultdict(list))
    for event in events:
        if event["event"] in STOP_EVENTS and event.get("epoch") is not None:
            grouped[(event["task_id"], event["epoch"])][event["event"]].append(event)
    delays = []
    for trace in grouped.values():
        if not any(e["reason"] in reasons for e in trace["APP_CANCEL_ACCEPTED"] + trace["APP_RELEASE"]):
            continue
        if not all(len(trace[name]) == 1 for name in STOP_EVENTS):
            require(not strict, "incomplete or duplicated independent stop-calibration chain")
            continue
        start, cancel, confirmed, released = (
            trace[name][0] for name in ("APP_START", "APP_CANCEL_ACCEPTED", "APP_WORKER_EXIT_CONFIRMED", "APP_RELEASE")
        )
        finished = released["release_ns"]
        cancelled = cancel["commit_return_ns"]
        matched = (
            len({clock_domain(event) for event in (start, cancel, confirmed, released)}) == 1
            and cancel["reason"] in reasons and released["reason"] == cancel["reason"]
            and start["slot"] == cancel["slot"] == confirmed["slot"] == released["slot"]
            and type(start.get("worker_pid")) is int and start["worker_pid"] == confirmed.get("worker_pid")
            and start.get("activation_ns", start["monotonic_ns"]) <= cancelled <= confirmed["confirmed_ns"]
            <= finished == released["commit_return_ns"] and finished > cancelled
        )
        require(matched or not strict, "invalid independent stop-calibration chain")
        if matched:
            delays.append(finished - cancelled)
    return delays


def independent_stop_delays(directory, plan, observed_cases, refs):
    root = directory / "stop-calibration"
    if not root.exists() or not observed_cases:
        return [], []
    paths = [root / f"trial-{trial:02d}" / "events.jsonl" for trial in range(6)]
    require(set(root.glob("*/events.jsonl")) == set(paths), "incomplete independent stop-calibration trial roster")
    slots = {pair["slots"] for pair in plan["pairs"]}
    workload = plan.get("source_sha256", {}).get("image_workload.py")
    inputs = {task.get("input_sha256") for pair in plan["pairs"] for task in pair["tasks"]}
    domains = {clock_domain(case) for case in observed_cases}
    require(len(slots) == len(inputs) == len(domains) == 1 and sha256_hex(workload),
            "stop-calibration workload, topology or host binding unavailable")
    slot_count, = slots
    input_digest, = inputs
    domain, = domains
    require(sha256_hex(input_digest), "stop-calibration input binding unavailable")
    first_paired_case = min(case["monotonic_ns"] for case in observed_cases)
    delays, files = [], []
    for path in paths:
        raw = path.read_bytes()
        events = [decode(line) for line in raw.splitlines()]
        trial_id = path.parent.name
        require(
            events and all(e["pair_id"] == trial_id and e["method"] == "stop-calibration"
                           and e["run_id"] == plan["run_id"] and clock_domain(e) == domain
                           and e["index"] == index
                           for index, e in enumerate(events))
            and all(a["monotonic_ns"] <= b["monotonic_ns"] for a, b in zip(events, events[1:])),
            f"{path}: mismatched stop-calibration identity or host timeline",
        )
        begin, end = events[0], events[-1]
        require(
            begin["event"] == "CASE_START" and end["event"] == "CASE_END"
            and begin["scope"] == "stop_calibration" and begin["slots"] == end["attempted"] == slot_count
            and begin.get("input_sha256") == input_digest and begin.get("workload_sha256") == workload
            and 0 <= begin["origin_ns"] <= begin["monotonic_ns"] <= end["monotonic_ns"] <= first_paired_case,
            f"{path}: invalid stop-calibration case binding",
        )
        tasks = {f"{trial_id}-{slot}" for slot in range(slot_count)}
        require(all(e["task_id"] in tasks and e["negotiationId"] == e["task_id"]
                    for e in events if e["task_id"] is not None),
                f"{path}: foreign stop-calibration task")
        for name in ("APP_GRANT", "APP_START", "APP_WORKER_EXIT_CONFIRMED", "APP_RELEASE"):
            phases = [e["task_id"] for e in events if e["event"] == name]
            require(len(phases) == slot_count and set(phases) == tasks,
                    f"{path}: incomplete or duplicated {name} stop trial coverage")
        for event in events:
            if event["event"] == "APP_RELEASE":
                require(event["reason"] in {CALIBRATION_REASON, "completed"},
                        f"{path}: unexpected stop-calibration outcome")
        sample = matched_stop_delays(events, {CALIBRATION_REASON}, strict=True)
        eligible = sum(e["event"] == "APP_RELEASE" and e["reason"] == CALIBRATION_REASON for e in events)
        require(len(sample) == eligible, f"{path}: stop-calibration canceled work was not fully witnessed")
        delays.extend(sample)
        key = path.relative_to(directory).as_posix()
        files.append(key)
        refs[key] = hashlib.sha256(raw).hexdigest()
    return delays, files


def evidence_from_events(directory, plan):
    stop_delays = []
    local_delays = []
    refs = {}
    approvals = {}
    observed_cases = []
    for pair in plan["pairs"]:
        for method in ("B0", "B2-info"):
            path = directory / "runs" / pair["pair_id"] / method / "events.jsonl"
            if not path.is_file():
                continue
            raw = path.read_bytes()
            refs[path.relative_to(directory).as_posix()] = hashlib.sha256(raw).hexdigest()
            local_started = {}
            case_events = [decode(line) for line in raw.splitlines()]
            if method == "B2-info":
                observed_cases.extend(e for e in case_events if e["event"] == "CASE_START")
                stop_delays.extend(matched_stop_delays(case_events, GRID_CANCEL_REASONS))
                if plan.get("authorization") == C2_MODE:
                    evidence = c2_approval_inputs(path, directory, plan, pair, case_events, refs)
                    if evidence is not None:
                        approvals[pair["pair_id"]] = evidence
                else:
                    require(not any(event["event"] == "CASE_START" and event.get("authorization") == C2_MODE
                                    for event in case_events), f"{path}: C2 case disagrees with replay plan mode")
            for event in case_events:
                require(
                    event["pair_id"] == pair["pair_id"] and event["method"] == method,
                    f"{path}: event belongs to a different pair or arm",
                )
                task_id = event.get("task_id")
                kind = event["event"]
                domain = tuple(event[key] for key in ("host", "boot", "clock"))
                if method == "B0":
                    if kind == "LOCAL_START":
                        require(task_id not in local_started, f"{path}: repeated local start")
                        local_started[task_id] = (domain, event["monotonic_ns"])
                    if kind == "LOCAL_COMPLETE" and task_id in local_started:
                        origin_domain, origin = local_started.pop(task_id)
                        span = event["monotonic_ns"] - origin
                        if domain == origin_domain and span > 0:
                            local_delays.append(span)
                    continue
    return stop_delays, local_delays, refs, approvals, observed_cases


class ReleaseModel:
    """Shared transition function for both modeled stop-delay settings."""

    def __init__(self, pair, plan, service_ns, local_ns, stop_ns, approvals=None):
        self.pair = pair
        self.plan = plan
        self.service_ns = service_ns
        self.local_ns = local_ns
        self.stop_ns = stop_ns
        self.approvals = approvals
        self.events = []
        self.serial = itertools.count()
        self.slots = [None] * pair["slots"]
        self.terminal_ready = defaultdict(int)
        self.tasks = {}
        for task in pair["tasks"]:
            start = task["release_offset_ns"]
            fallback = start + task["fallback_ns"]
            deadline = start + task["deadline_ns"]
            state = {
                "spec": task, "fallback": fallback, "deadline": deadline,
                "cutoff": fallback if plan["public_fallback"] else deadline,
                "requested_local": False, "adopted": None, "origin": None, "poll_status": False,
                "remote": "ARMED", "slot": None, "generation": 0, "retained_after_fallback_ns": 0,
                "busy_replies": 0, "cancel": None,
            }
            self.tasks[task["task_id"]] = state
            self.at(start, 3, "attempt", task["task_id"])
            self.at(fallback, 0, "fallback", task["task_id"])
            self.at(state["cutoff"], 0, "cutoff", task["task_id"])

    def at(self, when, priority, kind, task_id, generation=None):
        heapq.heappush(self.events, (when, priority, next(self.serial), kind, task_id, generation))

    def lost(self, direction, route, time_ns):
        return any(
            window["direction"] == direction
            and route in window["routes"]
            and window["start_ns"] <= time_ns < window["end_ns"]
            for window in self.pair["windows"]
        )

    def release(self, task, state, now):
        slot = task["slot"]
        if slot is not None:
            self.slots[slot] = None
            task["slot"] = None
            if task["requested_local"]:
                task["retained_after_fallback_ns"] += max(0, now - task["fallback"])
        task["remote"] = state

    def cancel(self, task_id, task, now):
        if task["remote"] == "EXECUTING":
            task["remote"] = "CANCELLING"
            task["cancel"] = now
            # Zero modeled delay applies only at actual cancellation decision.
            self.at(now + self.stop_ns, 1, "cancel_release", task_id, task["generation"])
        elif task["remote"] in ("ARMED", "GRANTED"):
            self.release(task, "EXPIRED", now)

    def rpc(self, task_id, task, route, now):
        if self.lost("uplink", route, now):
            return None
        if route == "/grant" and self.approvals is not None:
            response_lost = self.lost("downlink", route, now)
            approval = self.approvals[task_id]
            commit = approval["c2_commit_offset_ns"]
            if commit is None or commit > now:
                return None if response_lost else "PENDING_AUTHORIZATION"
            if approval["grant_ready_ns"] is None:
                return None if response_lost else "EXPIRED"
        if route == "/grant" and task["remote"] == "ARMED":
            if None not in self.slots:
                outcome = "BUSY"
            else:
                slot = self.slots.index(None)
                self.slots[slot] = task_id
                task["slot"] = slot
                task["generation"] += 1
                task["remote"] = "GRANTED"
                expiry = min(now + self.plan["lease_ns"], task["cutoff"])
                self.at(expiry, 2, "lease_expiry", task_id, task["generation"])
                outcome = task["remote"]
        else:
            if route == "/execute" and task["remote"] == "GRANTED":
                task["remote"] = "EXECUTING"
                self.at(now + self.service_ns, 2, "compute_done", task_id, task["generation"])
            outcome = task["remote"]
        return None if self.lost("downlink", route, now) else outcome

    def handle_attempt(self, task_id, task, now):
        if task["adopted"] is not None or now >= task["fallback"]:
            return
        route = "/status" if task["poll_status"] else "/grant"
        reply = self.rpc(task_id, task, route, now)
        task["poll_status"] = reply is None or reply == "EXECUTING"
        if reply == "GRANTED":
            reply = self.rpc(task_id, task, "/execute", now)
            task["poll_status"] = True
        if reply == "BUSY":
            task["busy_replies"] += 1
        if reply == "RESULT":
            task["adopted"] = now
            task["origin"] = "edge"
        elif reply not in TERMINAL:
            self.at(now + self.plan["rto_ns"], 3, "attempt", task_id)

    def run(self):
        while self.events:
            now, _, _, kind, task_id, generation = heapq.heappop(self.events)
            task = self.tasks[task_id]
            if generation is not None and generation != task["generation"]:
                continue
            if kind == "attempt":
                self.handle_attempt(task_id, task, now)
            elif kind == "fallback":
                if task["adopted"] is None:
                    task["requested_local"] = True
                    self.cancel(task_id, task, now)
                    terminal = task["spec"]["terminal"]
                    finish = max(now, self.terminal_ready[terminal]) + self.local_ns
                    self.terminal_ready[terminal] = finish
                    self.at(finish, 4, "local_done", task_id)
            elif kind == "cutoff":
                self.cancel(task_id, task, now)
            elif kind == "lease_expiry" and task["remote"] == "GRANTED":
                self.release(task, "ARMED" if now < task["cutoff"] else "EXPIRED", now)
            elif kind == "compute_done" and task["remote"] == "EXECUTING":
                self.release(task, "RESULT", now)
            elif kind == "cancel_release" and task["remote"] == "CANCELLING":
                self.release(task, "CANCELLED", now)
            elif kind == "local_done":
                task["adopted"] = now
                task["origin"] = "local"

        rows = []
        for task_id, task in self.tasks.items():
            require(task["adopted"] is not None and task["slot"] is None, "model left a task unsettled")
            timely = task["adopted"] < task["deadline"]
            qualified = timely and (task["origin"] == "edge" or self.plan["minimum_quality"] == "local")
            rows.append({
                "task_id": task_id, "modeled_origin": task["origin"], "modeled_adoption_offset_ns": task["adopted"],
                "modeled_timely": timely, "modeled_qualified": qualified, "modeled_busy_replies": task["busy_replies"],
                "modeled_post_fallback_slot_hold_ns": task["retained_after_fallback_ns"],
            })
        return rows


def validate_plan(plan):
    require(plan.get("schema") == "rdinp-concurrent-v1", "unsupported paired plan")
    require(plan.get("minimum_quality") in ("edge", "local"), "unknown quality tier")
    require(type(plan.get("public_fallback")) is bool, "missing public fallback policy")
    for name in ("lease_ns", "rto_ns"):
        require(type(plan[name]) is int and plan[name] > 0, f"invalid {name}")
    mode = plan.get("authorization", "prebound_application")
    require(mode in (C2_MODE, "prebound_application"), "unsupported authorization mode")
    if mode == C2_MODE:
        require(stable_id(plan.get("run_id")), "missing or invalid C2 run identity")
    routes = {"/grant", "/status", "/execute", "/cancel"}
    if mode == C2_MODE:
        routes.update(("/rdinp/intent", "/rdinp/commit"))
    require(plan["pairs"], "no planned pairs")
    pair_ids = set()
    for pair in plan["pairs"]:
        require(stable_id(pair["pair_id"]) and pair["pair_id"] not in pair_ids, "invalid or duplicate pair")
        pair_ids.add(pair["pair_id"])
        require(pair["slots"] in (1, 2), "slot count outside model design")
        tasks = pair["tasks"]
        require(tasks and len({item["task_id"] for item in tasks}) == len(tasks), "missing or duplicate tasks")
        for item in tasks:
            if mode == C2_MODE:
                require(type(item["terminal"]) is int and item["terminal"] >= 0
                        and sha256_hex(item.get("input_sha256")), "invalid C2 task owner or input digest")
            require(
                all(type(item[key]) is int for key in ("release_offset_ns", "fallback_ns", "deadline_ns"))
                and 0 <= item["release_offset_ns"] and 0 < item["fallback_ns"] < item["deadline_ns"],
                "invalid task schedule",
            )
        for window in pair["windows"]:
            require(
                window["direction"] in ("uplink", "downlink")
                and 0 <= window["start_ns"] < window["end_ns"]
                and set(window["routes"]) <= routes,
                "invalid directional window",
            )


def positive_ms(value):
    require(value is not None and type(value) in (float, int) and math.isfinite(value) and value > 0, "positive finite calibration required")
    ns = round(value * NS_PER_MS)
    require(ns > 0, "calibration must be representable in nanoseconds")
    return ns


def arm_summary(rows):
    n = len(rows)
    return {
        "released": n,
        "qualified": sum(row["modeled_qualified"] for row in rows),
        "timely_edge": sum(row["modeled_timely"] and row["modeled_origin"] == "edge" for row in rows),
        "local_fallback": sum(row["modeled_origin"] == "local" for row in rows),
        "modeled_post_fallback_slot_hold_ns_per_released": sum(row["modeled_post_fallback_slot_hold_ns"] for row in rows) / n,
        "tasks": rows,
    }


def analyze(directory, *, stop_ms=None, local_ms=None):
    plan_path = directory / "plan.json"
    plan_raw = plan_path.read_bytes()
    plan = decode(plan_raw)
    validate_plan(plan)
    measured_stop, measured_local, sources, approvals, observed_cases = evidence_from_events(directory, plan)
    calibration_files = []
    if stop_ms is None and not measured_stop:
        measured_stop, calibration_files = independent_stop_delays(directory, plan, observed_cases, sources)
    if stop_ms is not None:
        stop_source = "supplied"
    elif calibration_files:
        stop_source = "median independent same-shape actual worker diagnostic cancel to postcommit reuse"
    else:
        stop_source = "median B2-info actual committed-cancel to postcommit reuse"
    c2_mode = plan.get("authorization") == C2_MODE
    missing_approvals = [p["pair_id"] for p in plan["pairs"] if c2_mode and p["pair_id"] not in approvals]
    service_ns = positive_ms(plan["service_ms"])
    local_ns = positive_ms(local_ms) if local_ms is not None else median_ns(measured_local)
    stop_ns = positive_ms(stop_ms) if stop_ms is not None else median_ns(measured_stop)
    result = {
        "schema": SCHEMA,
        "evidence_scope": "MODEL_SENSITIVITY_ONLY",
        "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "source_event_sha256": sources,
        "calibration": {
            "nominal_execution_ns": service_ns, "execution_source": "declared service_ms in paired plan",
            "local_ns": local_ns, "local_source": "supplied" if local_ms is not None else "median B0 local wall duration",
            "positive_stop_ns": stop_ns,
            "stop_source": stop_source,
            "stop_calibration_files": calibration_files,
            "stop_observations": len(measured_stop), "local_observations": len(measured_local),
            "stop_delay_samples_ns": measured_stop,
        },
        "limits": [
            "Simulated release events hold no physical CPU process. A canceled pure task is assumed to have no external side effects.",
            "Both modeled arms receive the actual model-local fallback decision at zero information delay.",
            "Grant-to-release service calibration is used as one deterministic execution duration. Service variation, startup, SQL timing and clock error are not modeled separately.",
            "RPCs take zero simulated transport time outside the directional application fault windows. Retry spacing is represented by the planned RTO.",
            "Modeled expiry, post-fallback publication and worker stop are idealizations. Compare modeled arm deltas only with their matched modeled control.",
        ],
        "pairs": [],
    }
    result["authorization"] = {
        "mode": "observed_b2_info_c2_fixed_exogenous" if c2_mode else "prebound_application",
        "covered_pairs": len(approvals) if c2_mode else len(plan["pairs"]),
        "missing_pairs": missing_approvals,
    }
    if c2_mode:
        result["limits"].extend([
            "Per-task authority commit availability and lease validity come from the matching B2-info trace and stay fixed across both model arms. C2 exchange dynamics and feedback from changed application occupancy are outside the model.",
            "An explicit final no-commit observation denies all modeled grants for that task. A durable commit permits grant only after its observed return and only if committed before the C2 lease limit. Application windows still affect requests and replies.",
            "C2 proof timings are cross-checked against the retained authority trace within the observed host clock domain. Source digests bind the supplied files and require an independently retained manifest to attest their origin.",
        ])
    missing = [name for name, value in (("safe_stop_to_reuse", stop_ns), ("local_workload", local_ns)) if value is None]
    if missing_approvals:
        missing.append("c2_authority_coverage")
    if missing:
        result.update(status="NOT_CALIBRATED", missing_calibration=missing)
        return result
    result["status"] = "MODELLED"
    for pair in plan["pairs"]:
        authorities = approvals.get(pair["pair_id"])
        control = arm_summary(ReleaseModel(pair, plan, service_ns, local_ns, stop_ns, authorities).run())
        ideal = arm_summary(ReleaseModel(pair, plan, service_ns, local_ns, 0, authorities).run())
        result["pairs"].append({
            "pair_id": pair["pair_id"], "load": pair["load"], "condition": pair["condition"],
            "model_control": control, "model_ideal": ideal,
            **({"authorization_inputs": list(authorities.values())} if authorities is not None else {}),
            "ideal_minus_control_qualified_pp": 100 * (ideal["qualified"] - control["qualified"]) / control["released"],
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--stop-delay-ms", type=float, help="Positive supplied diagnostic assumption, not observed")
    parser.add_argument("--local-service-ms", type=float, help="Positive supplied diagnostic assumption, not observed")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = analyze(args.run.resolve(), stop_ms=args.stop_delay_ms, local_ms=args.local_service_ms)
    report = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()

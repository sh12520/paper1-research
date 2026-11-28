"""Audit the G1-A paired experiment independently of its runner.

All released tasks enter the denominator. A certificate of admissible results
requires complete pair coverage and matching durable-worker event witnesses.
The verdict is evidence for manual review, not authorization for the next stage.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re


METHODS = ("B0", "B1", "B2-info", "B2-ideal")
LOADS = (0.4, 0.7, 0.9)
FIELDS = {
    "pair_id", "method", "task_id", "terminal", "input_sha256", "release_ns",
    "deadline_ns", "adopted_ns", "source", "quality", "quality_ok", "verified",
    "fallback_ns", "fallback_started_ns", "output_sha256",
}
QUALITY = {"none": -1, "local": 0, "edge": 1}
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20261127
ENGINEERING_SIGNAL = 0.05


def require(condition, message):
    if not condition:
        raise ValueError(message)


def int_ns(value, label, *, optional=False):
    if optional and value == "":
        return None
    try:
        if type(value) is int:
            number = value
        elif type(value) is str and re.fullmatch(r"[0-9]+", value):
            number = int(value)
        else:
            raise ValueError
    except ValueError:
        raise ValueError(f"{label}: invalid nanosecond value {value!r}") from None
    require(number >= 0, f"{label}: negative time")
    return number


def sha256_hex(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def stable_id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value) is not None


def embedded_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def no_json_constant(token):
    raise ValueError(f"invalid JSON constant {token}")


def decode(data):
    return json.loads(data, object_pairs_hook=embedded_json, parse_constant=no_json_constant)


def plan_index(plan):
    require(plan.get("schema") == "rdinp-concurrent-v1", "unsupported plan schema")
    require(plan.get("scope") in ("engineering", "g1a"), "unsupported plan scope")
    methods = tuple(plan["methods"])
    require(methods in (METHODS, METHODS[:-1]), f"invalid method roster {methods!r}")
    require(plan.get("minimum_quality") in ("local", "edge"), "missing or invalid quality floor")
    require(type(plan["pairs"]) is list and plan["pairs"], "no planned pairs")
    pairs = {}
    tasks = {}
    for pair in plan["pairs"]:
        pair_id = pair["pair_id"]
        require(stable_id(pair_id) and pair_id not in pairs, f"invalid or duplicate pair {pair_id!r}")
        require(
            type(pair["load"]) in (int, float) and pair["load"] in LOADS,
            f"{pair_id}: invalid planned load",
        )
        require(stable_id(pair["condition"]), f"{pair_id}: invalid condition")
        if "slots" in pair:
            require(type(pair["slots"]) is int and pair["slots"] in (1, 2), f"{pair_id}: invalid slot count")
        expected = {}
        for task in pair["tasks"]:
            task_id = task["task_id"]
            require(stable_id(task_id) and task_id not in expected, f"{pair_id}: invalid or duplicate task")
            require(
                type(task["terminal"]) in (int, str) and bool(str(task["terminal"])),
                f"{pair_id}/{task_id}: invalid terminal",
            )
            require(sha256_hex(task["input_sha256"]), f"{pair_id}/{task_id}: invalid input digest")
            for field in ("release_offset_ns", "fallback_ns", "deadline_ns"):
                require(type(task[field]) is int, f"{pair_id}/{task_id}: {field} must be an integer")
                int_ns(task[field], field)
            require(0 < task["fallback_ns"] < task["deadline_ns"], f"{pair_id}/{task_id}: invalid budgets")
            refs = task.get("expected_output_sha256")
            if refs is not None:
                require(
                    type(refs) is dict and set(refs) == {"edge", "local"} and all(map(sha256_hex, refs.values())),
                    f"{pair_id}/{task_id}: bad output references",
                )
            expected[task_id] = task
        require(bool(expected), f"{pair_id}: no scheduled tasks")
        pairs[pair_id] = pair
        tasks[pair_id] = expected
    return pairs, tasks, methods


def read_rows(path, plan, tasks, methods):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        require(len(fields) == len(set(fields)) and FIELDS <= set(fields), "malformed per_task.csv header")
        by_run = defaultdict(dict)
        for line, raw in enumerate(reader, 2):
            key = (raw["pair_id"], raw["method"])
            task_id = raw["task_id"]
            label = f"per_task.csv:{line} {key}/{task_id}"
            require(None not in raw and all(value is not None for value in raw.values()), f"{label}: malformed row")
            require(key[0] in tasks and key[1] in methods, f"{label}: unplanned run")
            require(task_id in tasks[key[0]] and task_id not in by_run[key], f"{label}: duplicate or unplanned task")
            task = tasks[key[0]][task_id]
            require(
                raw["terminal"] == str(task["terminal"]) and raw["input_sha256"] == task["input_sha256"],
                f"{label}: input/terminal does not match plan",
            )
            row = dict(raw)
            for field in ("release_ns", "deadline_ns", "fallback_ns", "adopted_ns", "fallback_started_ns"):
                row[field] = int_ns(raw[field], f"{label} {field}", optional=field in ("adopted_ns", "fallback_started_ns"))
            release = row["release_ns"]
            require(row["deadline_ns"] - release == task["deadline_ns"], f"{label}: deadline budget mismatch")
            require(row["fallback_ns"] - release == task["fallback_ns"], f"{label}: fallback budget mismatch")
            for field in ("quality_ok", "verified"):
                require(raw[field] in ("0", "1"), f"{label}: {field} must be 0 or 1")
                row[field] = raw[field] == "1"
            source = row["source"]
            quality = row["quality"]
            require(source in QUALITY and quality in QUALITY, f"{label}: unknown execution source/quality")
            require(quality == source, f"{label}: inconsistent fixed tier")
            require(
                row["quality_ok"] == (QUALITY[quality] >= QUALITY[plan["minimum_quality"]]),
                f"{label}: quality qualification mismatch",
            )
            for field in ("adopted_ns", "fallback_started_ns"):
                require(row[field] is None or row[field] >= release, f"{label}: {field} before release")
            if source == "none":
                require(
                    row["adopted_ns"] is None and not row["verified"] and row["output_sha256"] == "",
                    f"{label}: absent result has adoption/verification/output",
                )
            else:
                require(
                    row["adopted_ns"] is not None and row["verified"] and sha256_hex(row["output_sha256"]),
                    f"{label}: adopted output lacks digest, timestamp or verification",
                )
                refs = task.get("expected_output_sha256")
                require(
                    refs is None or row["output_sha256"] == refs[source],
                    f"{label}: adopted output differs from the planned reference",
                )
                if source == "local" and key[1] != "B0":
                    require(
                        row["fallback_started_ns"] is not None and row["fallback_started_ns"] <= row["adopted_ns"],
                        f"{label}: local result without prior local start",
                    )
                elif source == "edge":
                    require(row["fallback_started_ns"] is None and key[1] != "B0", f"{label}: forbidden edge adoption")
                    require(row["adopted_ns"] < row["fallback_ns"], f"{label}: edge adoption after fixed fallback")
            if row["fallback_started_ns"] is not None:
                require(
                    key[1] != "B0" and row["fallback_started_ns"] >= row["fallback_ns"],
                    f"{label}: fallback outside fixed causal policy",
                )
            row["timely"] = row["adopted_ns"] is not None and row["adopted_ns"] < row["deadline_ns"]
            row["qualified"] = row["verified"] and row["quality_ok"] and row["timely"]
            by_run[key][task_id] = row
    for pair_id, expected in tasks.items():
        for method in methods:
            rows = by_run.get((pair_id, method), {})
            require(rows.keys() == expected.keys(), f"{pair_id}/{method}: missing tasks {expected.keys() - rows.keys()}")
            anchors = {row["release_ns"] - expected[task]["release_offset_ns"] for task, row in rows.items()}
            require(len(anchors) == 1, f"{pair_id}/{method}: release schedule differs from plan")
    return by_run


def clock_domain(event):
    return tuple(event[key] for key in ("host", "boot", "clock"))


def read_events(path, pair_id, method, tasks):
    log = []
    with path.open(encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, 1):
            event = decode(line)
            label = f"{path}:{line_num}"
            require(type(event) is dict, f"{label}: malformed event")
            require(
                event["pair_id"] == pair_id and event["method"] == method,
                f"{label}: event from a different run",
            )
            for key in ("event", "run_id", "host", "boot", "clock"):
                require(type(event.get(key)) is str and bool(event[key]), f"{label}: missing {key}")
            require(type(event["monotonic_ns"]) is int, f"{label}: timestamp must be an integer")
            int_ns(event["monotonic_ns"], f"{label} monotonic_ns")
            task_id = event.get("task_id")
            if task_id is not None:
                require(task_id in tasks, f"{label}: unplanned task")
                expected_id = tasks[task_id].get("negotiationId", task_id)
                require(event.get("negotiationId") == expected_id, f"{label}: negotiation/task binding mismatch")
            log.append(event)
    require(len({event["run_id"] for event in log}) == 1, f"{path}: empty or mixed run")
    require(not any(event["event"] == "APP_MONITOR_FAILURE" for event in log), f"{path}: worker monitor failed")
    last_epoch = {}
    for event in log:
        if event["event"] == "APP_GRANT":
            domain = clock_domain(event)
            epoch = event["epoch"]
            require(type(epoch) is int and epoch > last_epoch.get(domain, 0), f"{path}: nonmonotonic grant epoch")
            last_epoch[domain] = epoch
    return log


def event_ns(event, field):
    require(type(event.get(field)) is int, f"{event['event']}: missing integer {field}")
    return int_ns(event[field], field)


def audit_events(events, rows, method, slot_count=None):
    by_task = defaultdict(lambda: defaultdict(list))
    for event in events:
        if event.get("task_id") is not None:
            by_task[event["task_id"]][event["event"]].append(event)

    intervals = defaultdict(list)
    issued_epochs = set()
    worker_tails = []
    for task, row in rows.items():
        task_events = by_task[task]
        label = f"{row['pair_id']}/{method}/{task}"
        require(len(task_events["RELEASE"]) == 1, f"{label}: release witness count")
        release = task_events["RELEASE"][0]
        require(
            release.get("release_ns", row["release_ns"]) == row["release_ns"]
            and event_ns(release, "monotonic_ns") >= row["release_ns"],
            f"{label}: release timing mismatch",
        )
        for event, field, event_fields in (
            ("ADOPT", "adopted_ns", ("source", "quality", "output_sha256")),
            ("FALLBACK", "fallback_started_ns", ()),
        ):
            stamp = row[field]
            witnessed = task_events[event]
            require(len(witnessed) == (stamp is not None), f"{label}: {event} witness count")
            if witnessed:
                witness = witnessed[0]
                require(
                    event_ns(witness, field) == stamp and witness["monotonic_ns"] >= stamp
                    and clock_domain(witness) == clock_domain(release)
                    and all(witness.get(key) == row[key] for key in event_fields),
                    f"{label}: {event} differs from adopted record",
                )
        grants = task_events["APP_GRANT"]
        starts = task_events["APP_START"]
        releases = task_events["APP_RELEASE"]
        if method == "B0":
            require(not (grants or starts or releases), f"{label}: local-only fixture touched edge")
        if row["source"] == "edge":
            require(bool(starts), f"{label}: adopted edge result without execution witness")
        require(len(task_events["WORKER_COMPUTE_START"]) <= 1, f"{label}: repeated edge computation")
        if row["source"] == "local":
            completion = task_events["LOCAL_COMPLETE"]
            require(len(completion) == 1, f"{label}: missing local verification witness")
            require(
                clock_domain(completion[0]) == clock_domain(release)
                and completion[0]["monotonic_ns"] <= row["adopted_ns"]
                and completion[0]["result_sha256"] == row["output_sha256"],
                f"{label}: inconsistent local verification witness",
            )
        if row["source"] == "edge":
            observed = task_events["EDGE_READBACK_VERIFIED"]
            successes = [event for event in task_events["APP_COMPLETE"] if event.get("success") is True]
            require(len(observed) == len(successes) == 1, f"{label}: missing durable result and readback witness")
            worker_result, readback = successes[0], observed[0]
            readback_ns = event_ns(readback, "observed_ns")
            require(
                readback.get("epoch") == worker_result["epoch"]
                and worker_result["result_sha256"] == readback["result_sha256"] == row["output_sha256"]
                and clock_domain(readback) == clock_domain(release)
                and readback_ns <= row["adopted_ns"],
                f"{label}: adopted result conflicts with durable result and readback",
            )
            if clock_domain(worker_result) == clock_domain(readback):
                require(
                    event_ns(worker_result, "commit_return_ns") <= readback_ns,
                    f"{label}: readback before durable result commit",
                )

        transitions = {}
        for field in (
            "APP_GRANT", "APP_START", "APP_RELEASE", "APP_WORKER_EXIT_CONFIRMED",
            "WORKER_COMPUTE_START", "WORKER_COMPUTE_END",
        ):
            by_epoch = {}
            for event in task_events[field]:
                epoch = event["epoch"]
                require(type(epoch) is int and epoch > 0 and epoch not in by_epoch, f"{label}: invalid {field} epoch")
                by_epoch[epoch] = event
            transitions[field] = by_epoch
        epochs = transitions["APP_GRANT"].keys()
        require(epochs == transitions["APP_RELEASE"].keys(), f"{label}: missing allocation/release transition")
        require(all(group.keys() <= epochs for group in transitions.values()), f"{label}: unknown allocation epoch")
        for generation, grant in transitions["APP_GRANT"].items():
            ended = transitions["APP_RELEASE"][generation]
            slot = grant["slot"]
            require(
                type(slot) is int and slot >= 0 and (slot_count is None or slot < slot_count),
                f"{label}: invalid slot",
            )
            domain = clock_domain(grant)
            require((domain, generation) not in issued_epochs, f"{label}: reused grant epoch")
            issued_epochs.add((domain, generation))
            require(
                all(group[generation]["slot"] == slot and clock_domain(group[generation]) == domain
                    for group in transitions.values() if generation in group),
                f"{label}: allocation lifecycle uses different slot or clock",
            )
            start = transitions["APP_START"].get(generation)
            exit_event = transitions["APP_WORKER_EXIT_CONFIRMED"].get(generation)
            compute_start = transitions["WORKER_COMPUTE_START"].get(generation)
            compute_end = transitions["WORKER_COMPUTE_END"].get(generation)
            require((start is None) == (exit_event is None), f"{label}: missing verified worker exit")
            require(compute_start is None or start is not None, f"{label}: compute without start")
            require(compute_end is None or compute_start is not None, f"{label}: compute end without start")

            allocation_ns = event_ns(grant, "commit_return_ns")
            free_ns = event_ns(ended, "release_ns")
            require(
                allocation_ns <= grant["monotonic_ns"]
                and allocation_ns <= free_ns <= ended["monotonic_ns"]
                and free_ns == event_ns(ended, "commit_return_ns"),
                f"{label}: release lacks post-commit timestamp",
            )
            if start:
                start_ns = start["activation_ns"] if "activation_ns" in start else start["monotonic_ns"]
                exit_ns = event_ns(exit_event, "confirmed_ns")
                require(
                    allocation_ns <= start_ns <= exit_ns <= free_ns and start_ns <= start["monotonic_ns"],
                    f"{label}: worker exit not confirmed before reuse",
                )
            else:
                start_ns = exit_ns = None
            cpu_start_ns = event_ns(compute_start, "worker_event_ns") if compute_start else None
            cpu_end_ns = event_ns(compute_end, "worker_event_ns") if compute_end else None
            if cpu_start_ns is not None:
                require(
                    allocation_ns <= cpu_start_ns <= (cpu_end_ns or exit_ns) <= exit_ns,
                    f"{label}: CPU trace outside supervised execution interval",
                )
            process_cpu_ns = exit_event.get("worker_cpu_ns") if exit_event else 0
            require(process_cpu_ns is None or type(process_cpu_ns) is int and process_cpu_ns >= 0,
                    f"{label}: invalid supervised process CPU duration")
            adopted_epoch = worker_result["epoch"] if row["source"] == "edge" else None
            intervals[(domain, slot)].append((allocation_ns, free_ns, task))
            known_local = domain == clock_domain(release)
            fallback = row["fallback_started_ns"]
            comparable = known_local and fallback is not None
            worker_tails.append({
                "task_id": task, "slot": slot, "epoch": generation,
                "allocated_ns": allocation_ns, "activated_ns": start_ns, "reusable_ns": free_ns,
                "release_reason": ended["reason"], "clock_domain": list(domain),
                "worker_cpu_ns": process_cpu_ns,
                "discarded_worker_cpu_ns": 0 if generation == adopted_epoch else process_cpu_ns,
                "fallback_clock_comparable": known_local,
                "fallback_to_reuse_ns": (
                    max(0, free_ns - max(allocation_ns, fallback)) if comparable else None
                ),
                "cpu_after_fallback_observed_ns": (
                    max(0, cpu_end_ns - max(cpu_start_ns, fallback))
                    if comparable and cpu_end_ns is not None else None
                ),
                "cpu_after_fallback_upper_ns": (
                    max(0, (cpu_end_ns or exit_ns) - max(cpu_start_ns or allocation_ns, fallback))
                    if comparable and exit_ns is not None else 0 if comparable else None
                ),
            })

    for slot, uses in intervals.items():
        uses.sort()
        for previous, current in zip(uses, uses[1:]):
            require(previous[1] <= current[0], f"{method}: overlap on slot {slot!r}: {previous[2]} and {current[2]}")
    return worker_tails


def quantile(sorted_values, probability):
    index = (len(sorted_values) - 1) * probability
    lower = math.floor(index)
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[math.ceil(index)] * fraction


def paired_interval(strata, *, replicates=BOOTSTRAP_REPLICATES):
    """Resample intact independent paired runs within each fixed load/condition stratum."""
    groups = [tuple(values) for _, values in sorted(strata.items())]
    if not groups:
        return {"pair_count": 0, "difference_pp": None, "ci95_pp": None}
    count = sum(map(len, groups))
    observed = sum(map(sum, groups)) / count
    bounds = None
    if all(len(group) >= 2 for group in groups):
        rng = random.Random(BOOTSTRAP_SEED)
        samples = sorted(
            sum(sum(rng.choice(group) for _ in group) for group in groups) / count
            for _ in range(replicates)
        )
        bounds = [quantile(samples, 0.025) * 100, quantile(samples, 0.975) * 100]
    return {"pair_count": count, "difference_pp": observed * 100, "ci95_pp": bounds}


def method_counts(rows, tails):
    released = len(rows)
    counts = Counter(
        "qualified" if row["qualified"] else (
            "missing" if row["source"] == "none" else "late" if not row["timely"] else "low_quality"
        )
        for row in rows.values()
    )
    fallbacks = [row for row in rows.values() if row["fallback_started_ns"] is not None]
    fallback_tails = [tail for tail in tails if rows[tail["task_id"]]["fallback_started_ns"] is not None]
    # A fallback without an allocation on the completed trace has zero occupied-slot tail.
    measurable = all(tail["fallback_clock_comparable"] for tail in fallback_tails)
    occupancy = sum(tail["fallback_to_reuse_ns"] for tail in fallback_tails) if measurable else None
    cpu_upper = sum(tail["cpu_after_fallback_upper_ns"] for tail in fallback_tails) if measurable else None
    all_cpu = [tail["discarded_worker_cpu_ns"] for tail in tails]
    discarded_cpu = sum(all_cpu) if all(value is not None for value in all_cpu) else None
    return {
        "released": released,
        "qualified": counts["qualified"],
        "missing": counts["missing"],
        "late": counts["late"],
        "timely_low_quality": counts["low_quality"],
        "timely_edge": sum(row["timely"] and row["source"] == "edge" for row in rows.values()),
        "timely_local": sum(row["timely"] and row["source"] == "local" for row in rows.values()),
        "low_tier_fallback": len(fallbacks),
        "qualified_fraction": counts["qualified"] / released,
        "fallback_occupied_slot_ns_per_released": occupancy / released if occupancy is not None else None,
        "fallback_cpu_ns_upper_per_released": cpu_upper / released if cpu_upper is not None else None,
        "discarded_worker_cpu_ns_per_released": discarded_cpu / released if discarded_cpu is not None else None,
    }


def downstream_witnesses(pair_id, baseline, info, b1_log, b1_allocations, info_allocations, plan_tasks):
    """Report observed, task-linked shared-slot conflicts, separately from the Go criterion."""
    oracle = defaultdict(list)
    for entry in info_allocations:
        oracle[entry["task_id"]].append(entry)
    busy_by_task = defaultdict(list)
    for event in b1_log:
        if event.get("task_id") and event["event"] == "APP_BUSY":
            busy_by_task[event["task_id"]].append(event)
    for task, row in baseline.items():
        other = info[task]
        if row["qualified"] or not other["qualified"] or other["source"] != "edge":
            continue
        successor = next((entry for entry in oracle[task] if entry["activated_ns"] is not None), None)
        if not successor or not successor["fallback_clock_comparable"]:
            continue
        found = False
        for busy in busy_by_task[task]:
            busy_ns = busy["commit_return_ns"]
            for allocation in b1_allocations:
                blocker = allocation["task_id"]
                fallback = baseline[blocker]["fallback_started_ns"]
                if blocker == task or fallback is None or fallback > busy_ns:
                    continue
                if not (
                    allocation["fallback_clock_comparable"] and list(clock_domain(busy)) == allocation["clock_domain"]
                    and allocation["allocated_ns"] <= busy_ns < allocation["reusable_ns"]
                ):
                    continue
                baseline_free = allocation["reusable_ns"] - baseline[blocker]["release_ns"]
                # Rebase by the fixed release plan, never by raw cross-run clocks.
                successor_offset = plan_tasks[task]["release_offset_ns"] - plan_tasks[blocker]["release_offset_ns"]
                successor_acquire = successor["allocated_ns"] - info[task]["release_ns"] + successor_offset
                earlier_releases = [
                    entry for entry in oracle[blocker]
                    if entry["fallback_clock_comparable"] and entry["slot"] == successor["slot"]
                    and entry["clock_domain"] == successor["clock_domain"]
                    and entry["reusable_ns"] <= successor["allocated_ns"]
                ]
                if earlier_releases and successor_acquire < baseline_free:
                    oracle_free = max(entry["reusable_ns"] for entry in earlier_releases) - info[blocker]["release_ns"]
                    yield {
                        "pair_id": pair_id, "task_id": task, "blocking_task_id": blocker,
                        "b1_busy_ns_after_task_release": busy_ns - row["release_ns"],
                        "b1_blocker_reuse_ns_after_its_release": baseline_free,
                        "info_blocker_reuse_ns_after_its_release": oracle_free,
                    }
                    found = True
                    break
            if found:
                break


def audit_authorization(log, planned_tasks, method, mode):
    if mode != "frozen_bilateral_c2":
        return None
    authorization_names = {
        "C2_TASK_BIND", "C2_CLIENT_TERMINAL", "C2_DURABLE_AUTHORIZED",
        "C2_PROOF_CHECKED_FOR_GRANT", "C2_AUTHORIZATION_LATE",
    }
    if method == "B0":
        require(not any(e["event"] in authorization_names for e in log),
                "local-only path unexpectedly used C2")
        return {"authorized_tasks": 0, "actuation_grants": 0}
    bindings = {}
    completed = set()
    proofs = {}
    usable = {}
    grants = 0
    for e in log:
        task = e["task_id"]
        kind = e["event"]
        if kind == "C2_TASK_BIND":
            spec = planned_tasks[task]
            require(task not in bindings and e["terminal"] == spec["terminal"]
                    and e["input_sha256"] == spec["input_sha256"], "C2 binding mismatch")
            bindings[task] = e["intentId"]
        elif kind == "C2_CLIENT_TERMINAL":
            require(task in bindings and e["intentId"] == bindings[task] and task not in completed,
                    "C2 initiator completion mismatch")
            completed.add(task)
        elif kind == "C2_DURABLE_AUTHORIZED":
            require(task in bindings and task not in proofs
                    and e["c2_intent_id"] == bindings[task]
                    and e["c2_terminal"] == planned_tasks[task]["terminal"]
                    and e["c2_authority_state"] == "CONFIRMED"
                    and e["c2_commit_return_ns"] <= e["monotonic_ns"], "invalid C2 authorization receipt")
            proofs[task] = {key: val for key, val in e.items() if key.startswith("c2_")}
        elif kind == "C2_PROOF_CHECKED_FOR_GRANT":
            require(task in proofs and e["approval"] == proofs[task]
                    and proofs[task]["c2_commit_before_lease"] is True, "invalid C2 grant proof")
            # Authorization is immutable. A concurrent recheck can be logged
            # after SQLite returns but before its APP_GRANT row reaches the log.
            usable.setdefault(task, e["monotonic_ns"])
        elif kind == "APP_GRANT":
            require(task in usable and usable[task] <= e["commit_return_ns"],
                    "application grant lacks a prior C2 authorization")
            grants += 1
    require(set(bindings) == completed == set(planned_tasks), "incomplete C2 handshake roster")
    return {"authorized_tasks": len(proofs), "actuation_grants": grants}


def audit(directory):
    plan_path = directory / "plan.json"
    task_path = directory / "per_task.csv"
    plan_data = plan_path.read_bytes()
    plan = decode(plan_data)
    pairs, tasks, methods = plan_index(plan)
    rows = read_rows(task_path, plan, tasks, methods)
    run_root = directory / "runs"
    expected_logs = {
        run_root / pair_id / method / "events.jsonl" for pair_id in pairs for method in methods
    }
    require(set(run_root.glob("*/*/events.jsonl")) == expected_logs, "event log roster differs from paired plan")

    run_results = []
    witnesses = []
    comparisons = {
        f"{method} minus {base}": (method, base)
        for method, base in (("B1", "B0"), ("B2-info", "B1"), ("B2-ideal", "B2-info"))
        if method in methods
    }
    differences = {key: defaultdict(list) for key in comparisons}
    for pair_id, pair in pairs.items():
        counts = {}
        logs = {}
        allocations = {}
        for method in methods:
            path = run_root / pair_id / method / "events.jsonl"
            log = read_events(path, pair_id, method, tasks[pair_id])
            run_id = log[0]["run_id"]
            if "run_id" in plan:
                require(run_id == plan["run_id"], f"{pair_id}/{method}: run id does not match plan")
            logs[method] = log
            run_rows = rows[(pair_id, method)]
            tails = audit_events(log, run_rows, method, pair.get("slots"))
            c2 = audit_authorization(log, tasks[pair_id], method, plan.get("authorization"))
            allocations[method] = tails
            counts[method] = method_counts(run_rows, tails)
            run_results.append({
                "pair_id": pair_id, "method": method, "run_id": run_id,
                "load": pair["load"], "condition": pair["condition"],
                "event_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **counts[method], "allocation_witnesses": tails,
                **({"c2": c2} if c2 is not None else {}),
            })
        key = (pair["load"], pair["condition"])
        for name, (method, base) in comparisons.items():
            n = counts[method]["released"]
            difference = (counts[method]["qualified"] - counts[base]["qualified"]) / n
            differences[name][key].append(difference)
        witnesses.extend(downstream_witnesses(
            pair_id, rows[(pair_id, "B1")], rows[(pair_id, "B2-info")], logs["B1"],
            allocations["B1"], allocations["B2-info"], tasks[pair_id],
        ))

    info = differences["B2-info minus B1"]
    medium_high = {key: values for key, values in info.items() if key[0] in (0.7, 0.9)}
    primary = paired_interval(medium_high)
    blockers = []
    if plan["scope"] != "g1a":
        blockers.append("engineering scope")
    if "B2-ideal" not in methods:
        blockers.append("B2-ideal not observed")
    if {pair["load"] for pair in pairs.values()} != set(LOADS):
        blockers.append("incomplete load coverage")
    if not all(task.get("expected_output_sha256") for group in tasks.values() for task in group.values()):
        blockers.append("missing independently frozen output references")
    if primary["ci95_pp"] is None:
        blockers.append("insufficient independent paired runs per primary stratum")

    aggregate_counts = defaultdict(Counter)
    for run in run_results:
        key = (run["load"], run["condition"], run["method"])
        for name in ("released", "qualified", "timely_edge", "timely_local", "low_tier_fallback",
                     "late", "missing", "timely_low_quality"):
            aggregate_counts[key][name] += run[name]
    arm_counts = []
    for (load, condition, method), tally in sorted(aggregate_counts.items()):
        n = tally["released"]
        arm_counts.append({
            "load": load, "condition": condition, "method": method, **tally,
            **{f"{name}_fraction": count / n for name, count in tally.items() if name != "released"},
        })

    if blockers:
        verdict = "INCOMPLETE_FOR_GATE"
    elif primary["difference_pp"] >= ENGINEERING_SIGNAL * 100 and primary["ci95_pp"][0] > 0:
        verdict = "GO_CANDIDATE_REQUIRES_MANUAL_REVIEW"
    else:
        verdict = "NO_PRIMARY_GO_SIGNAL_REQUIRES_MANUAL_REVIEW"
    return {
        "schema": "rdinp-g1a-audit-v1",
        "scope": plan["scope"],
        "on_time_rule": "verified result strictly before deadline; minimum quality for main endpoint",
        "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
        "table_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
        "methods_observed": list(methods),
        "methods_not_observed": [method for method in METHODS if method not in methods],
        "pairs": len(pairs),
        "runs": len(run_results),
        "released_method_observations": sum(run["released"] for run in run_results),
        "estimand": "Mean within-pair difference, retaining schedule, load and fault condition",
        "interval": {
            "unit": "paired run or independent fault cluster",
            "assumption": "Each planned pair_id represents one independent unit",
            "bootstrap_within": "load/condition stratum",
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "limits": "Stratum intervals are descriptive and unavailable when a stratum has fewer than two pairs",
        },
        "contrasts": {
            name: [
                {"load": key[0], "condition": key[1], **paired_interval({key: values})}
                for key, values in sorted(group.items())
            ]
            for name, group in differences.items()
        },
        "primary_medium_high_info_minus_b1": primary,
        "arm_counts_by_load_and_condition": arm_counts,
        "downstream_witnesses": witnesses,
        "verdict": verdict,
        "gate_blockers": blockers,
        "run_results": run_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, help="Create a new JSON audit report at this path")
    args = parser.parse_args()
    summary = audit(args.run.resolve())
    serialized = json.dumps(summary, allow_nan=False, indent=2) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()

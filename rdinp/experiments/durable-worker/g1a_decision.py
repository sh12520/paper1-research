"""Verify and report the paired G1-A experiment under its fixed study design."""

from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
from itertools import permutations
import json
import math
from pathlib import Path
import random

from concurrent_audit import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, audit, clock_domain, decode,
    plan_index, quantile, read_rows, require, sha256_hex,
)
from ideal_release_replay import analyze as replay, c2_approval_inputs


PROTOCOL = "rdinp-g1a-20261127-v1"
TOPOLOGIES = {(4, 1), (8, 2)}
PHYSICAL_METHODS = ("B0", "B1", "B2-info")
CONDITIONS = {"clean": set(), "uplink": {"uplink"}, "downlink": {"downlink"},
              "both": {"uplink", "downlink"}}
LOADS = (0.4, 0.7, 0.9)
ORDERS = tuple(permutations(PHYSICAL_METHODS))
TASKS = 12
MS = 1_000_000
GO_MARGIN_PP = 5
ROUTES = {"/grant", "/status", "/execute", "/cancel", "/rdinp/intent", "/rdinp/commit"}


def check_plan(plan):
    require(plan.get("decision_protocol") == PROTOCOL and plan.get("scope") == "g1a",
            "not a fixed G1-A decision plan")
    require(plan.get("authorization") == "frozen_bilateral_c2", "frozen C2 authorization required")
    require(plan.get("transport") == "directional_application_fault_windows_on_loopback",
            "unexpected fault mechanism")
    require(plan.get("service_source") == "calibrated" and math.isfinite(plan["service_ms"])
            and plan["service_ms"] > 0, "measured service calibration required")
    require(plan.get("public_fallback") is True and plan.get("minimum_quality") == "edge",
            "incorrect public fallback or fixture quality policy")
    require(plan.get("lease_ns") == 150 * MS and plan.get("rto_ns") == 25 * MS,
            "incorrect lease or RTO")
    for key in ("source_sha256", "frozen_c2_sha256"):
        values = plan.get(key)
        require(isinstance(values, dict) and values and all(map(sha256_hex, values.values())),
                f"missing frozen {key}")

    pairs, tasks, methods = plan_index(plan)
    require(methods == PHYSICAL_METHODS, "physical methods must be B0, B1, B2-info")
    topologies = {(pair["terminals"], pair["slots"]) for pair in pairs.values()}
    require(len(topologies) == 1 and topologies <= TOPOLOGIES, "wrong topology")
    topology = topologies.pop()
    seen = set()
    fixtures = set()
    for pair_id, pair in pairs.items():
        replicate = pair["replicate"]
        stratum = pair["load"], pair["condition"], replicate
        require(type(replicate) is int and 0 <= replicate < len(ORDERS)
                and pair["condition"] in CONDITIONS and stratum not in seen,
                f"{pair_id}: unplanned or duplicate replicate")
        seen.add(stratum)
        require(tuple(pair["method_order"]) == ORDERS[replicate], f"{pair_id}: method order changed")
        planned = list(tasks[pair_id].values())
        require(len(planned) == TASKS and [task["release_offset_ns"] for task in planned]
                == sorted({task["release_offset_ns"] for task in planned}),
                f"{pair_id}: invalid release roster")
        interval = pair["interrelease_ns"]
        require(interval == max(1, round(round(plan["service_ms"] * MS) / (pair["load"] * topology[1]))),
                f"{pair_id}: release rate inconsistent with measured calibration")
        for index, task in enumerate(planned):
            require(task["fallback_ns"] == 550 * MS and task["deadline_ns"] == 800 * MS
                    and task["terminal"] == index % topology[0], f"{pair_id}: fixed deadline or lane changed")
            expected_release = index * interval
            if index % 2 and index < TASKS - 1:
                key = f"{topology[0]}/{topology[1]}/{pair['load']:.1f}/{replicate}/{index}".encode("ascii")
                sign = 1 if sha256(key).digest()[0] & 1 else -1
                expected_release += sign * (55 * interval // 100)
            require(task["release_offset_ns"] == expected_release, f"{pair_id}: release schedule mismatch")
            output = task.get("expected_output_sha256")
            require(output is not None, f"{pair_id}: missing independent fixture digests")
            fixtures.add((task["input_sha256"], output["edge"], output["local"]))
        anchor = planned[replicate % 3]
        center = anchor["release_offset_ns"] + anchor["fallback_ns"] + (-1 if replicate < 3 else 1) * plan["rto_ns"]
        windows = pair["windows"]
        require(len(windows) == len(CONDITIONS[pair["condition"]])
                and {window["direction"] for window in windows} == CONDITIONS[pair["condition"]],
                f"{pair_id}: wrong fault directions")
        for window in windows:
            require(set(window["routes"]) == ROUTES and window["start_ns"] == center - 120 * MS
                    and window["end_ns"] == center + 120 * MS, f"{pair_id}: wrong fault window")
    planned_grid = {(load, condition, repeat) for load in LOADS for condition in CONDITIONS
                    for repeat in range(len(ORDERS))}
    require(seen == planned_grid and len(fixtures) == 1, "incomplete grid or mixed fixtures")
    return pairs, topology, fixtures.pop()


def check_measurement(directory, plan):
    calibration = directory / "calibration"
    log = calibration / "runs" / "calibration" / "B1" / "events.jsonl"
    measured = decode((calibration / "measurement.json").read_bytes())
    grants, releases = {}, {}
    with log.open(encoding="utf-8") as handle:
        for line in handle:
            event = decode(line)
            if event["event"] in ("APP_GRANT", "APP_RELEASE"):
                require(event["run_id"] == plan["run_id"], "calibration trace belongs to a different run")
                task = event["task_id"]
                destination = grants if event["event"] == "APP_GRANT" else releases
                require(task not in destination, "duplicate calibration allocation")
                field = "monotonic_ns" if destination is grants else "release_ns"
                destination[task] = event[field]
    require(set(grants) == set(releases) and len(grants) == 4, "incomplete slot calibration")
    values = [releases[task] - start for task, start in grants.items()]
    require(all(value > 0 for value in values) and values == measured["slot_occupancy_ns"],
            "calibration durations differ from event trace")
    require(plan["service_ms"] == measured["mean_ms"] == sum(values) / len(values) / MS,
            "plan uses a different calibration mean")
    return sha256(log.read_bytes()).hexdigest()


def load_timeline(directory, planned):
    """Check serial arm execution and retain slim evidence for attribution."""
    spans = {}
    evidence = {}
    for pair_id, pair in planned.items():
        for method in PHYSICAL_METHODS:
            log = directory / "runs" / pair_id / method / "events.jsonl"
            selected = defaultdict(list)
            with log.open(encoding="utf-8") as handle:
                for line in handle:
                    event = decode(line)
                    if event["event"] in ("CASE_START", "CASE_END", "RELEASE", "FALLBACK", "APP_BUSY",
                                          "ORACLE_INFO_DELIVERY", "APP_CANCEL_ACCEPTED", "APP_START",
                                          "APP_STOP_REQUESTED", "APP_WORKER_EXIT_CONFIRMED", "APP_RELEASE",
                                          "C2_FINAL_AUTHORIZATION", "C2_RELAY_DROP", "RPC_DROP"):
                        selected[event["event"]].append(event)
            require(len(selected["CASE_START"]) == len(selected["CASE_END"]) == 1,
                    f"{pair_id}/{method}: missing case boundaries")
            start, end = selected["CASE_START"][0], selected["CASE_END"][0]
            require(clock_domain(start) == clock_domain(end) and start["monotonic_ns"] < end["monotonic_ns"],
                    f"{pair_id}/{method}: incoherent case boundaries")
            require(len(selected["RELEASE"]) == end["rows"] == TASKS
                    and all(start["monotonic_ns"] <= e["monotonic_ns"] <= end["monotonic_ns"]
                            for e in selected["RELEASE"]), f"{pair_id}/{method}: release coverage")
            for drop in selected["C2_RELAY_DROP"] + selected["RPC_DROP"]:
                gate_ns = drop["fault_gate_ns"]
                require(type(gate_ns) is int and start["origin_ns"] <= gate_ns <= drop["monotonic_ns"]
                        and clock_domain(start) == clock_domain(drop)
                        and any(w["direction"] == drop["direction"] and drop["route"] in w["routes"]
                                and w["start_ns"] <= gate_ns - start["origin_ns"] < w["end_ns"]
                                for w in pair["windows"]),
                        f"{pair_id}/{method}: fault stamp outside configured window")
            spans[(pair_id, method)] = start["monotonic_ns"], end["monotonic_ns"], clock_domain(start)
            evidence[(pair_id, method)] = selected
        order = sorted(PHYSICAL_METHODS, key=lambda method: spans[(pair_id, method)][0])
        require(tuple(order) == tuple(pair["method_order"]), f"{pair_id}: actual execution order differs from plan")

    require(len({domain for _, _, domain in spans.values()}) == 1,
            "run clock changed within a decision study")
    by_start = sorted(spans.values())
    require(all(prev[1] <= current[0] for prev, current in zip(by_start, by_start[1:])),
            "physical arm executions overlap")
    return evidence


def stratified_interval(strata):
    """Equal-stratum paired bootstrap using complete run pairs as sample units."""
    groups = [values for _, values in sorted(strata.items())]
    pair_count = sum(map(len, groups))
    if not groups or any(len(values) < 2 or None in values for values in groups):
        return {"paired_runs": pair_count, "estimate": None, "ci95": None}
    estimate = sum(sum(values) / len(values) for values in groups) / len(groups)
    rng = random.Random(BOOTSTRAP_SEED)
    estimates = sorted(
        sum(sum(rng.choice(values) for _ in values) / len(values) for values in groups) / len(groups)
        for _ in range(BOOTSTRAP_REPLICATES)
    )
    return {"paired_runs": pair_count, "estimate": estimate,
            "ci95": [quantile(estimates, 0.025), quantile(estimates, 0.975)]}


def evaluate_signal(primary, downstream, chains, ideal_complete, pivot_exposure_complete):
    low, high = primary["ci95"]
    main_signal = primary["estimate"] >= GO_MARGIN_PP and low > 0
    downstream_signal = downstream["ci95"][0] > 0
    attribution = len({(w["topology"], w["pair_id"]) for w in chains
                       if w["new_information_precedes_public_cutoff"]}) >= 2
    if not ideal_complete:
        status = "INCOMPLETE_FOR_GATE"
    elif main_signal or downstream_signal:
        status = ("GO_CANDIDATE_REQUIRES_MANUAL_REVIEW" if attribution
                  else "QUANTITATIVE_SIGNAL_REQUIRES_ATTRIBUTION")
    elif high < GO_MARGIN_PP and not downstream_signal and not attribution and pivot_exposure_complete:
        status = "PIVOT_CANDIDATE_REQUIRES_MANUAL_REVIEW"
    else:
        status = "INCONCLUSIVE_REQUIRES_MANUAL_REVIEW"
    return {"status": status, "main_signal": main_signal, "downstream_signal": downstream_signal,
            "repeated_information_attribution": attribution, "pivot_exposure_complete": pivot_exposure_complete,
            "manual_decision_required": True,
            "next_stage_authorized": False}


def busy_sample_ns(event):
    # SQLite commits and emits APP_BUSY under its admission lock, so other
    # grants and releases cannot interleave into this transaction's sample.
    return event.get("decision_ns", event["commit_return_ns"])


def audit_busy(rows, logs, run):
    """Count unqualified tasks exposed to a BUSY interval with a fallen-back owner."""
    outcomes = {task for task, row in rows.items() if not row["qualified"]}
    fallbacks = {event["task_id"]: event["fallback_started_ns"] for event in logs["FALLBACK"]}
    return {
        e["task_id"] for e in logs["APP_BUSY"] if e["task_id"] in outcomes
        and any(a["task_id"] != e["task_id"] and a["task_id"] in fallbacks
                and a["fallback_clock_comparable"] and a["clock_domain"] == list(clock_domain(e))
                and max(a["allocated_ns"], fallbacks[a["task_id"]]) <= busy_sample_ns(e) < a["reusable_ns"]
                for a in run["allocation_witnesses"])
    }


def pivot_exposures(pair, logs, run):
    """Check realized opportunities without conditioning the primary estimate."""
    if not pair["windows"]:
        return {}
    origin = logs["CASE_START"][0]["origin_ns"]
    anchor = pair["tasks"][pair["replicate"] % 3]
    fallback_offset = anchor["release_offset_ns"] + anchor["fallback_ns"]
    counts = {}
    held = sum((a["fallback_to_reuse_ns"] or 0) > 0 for a in run["allocation_witnesses"])
    for window in pair["windows"]:
        require(window["start_ns"] < fallback_offset < window["end_ns"], "outage misses declared fallback")
        direction = window["direction"]
        drop_events = [event for event in logs["C2_RELAY_DROP"] + logs["RPC_DROP"]
                       if event["direction"] == direction and event["route"] in window["routes"]
                       and window["start_ns"] <= event["fault_gate_ns"] - origin < window["end_ns"]]
        shared = bool(logs["FALLBACK"] and logs["APP_BUSY"])
        counts[direction] = {
            "realized_drops_in_fallback_window": len(drop_events),
            "pairs_with_realized_drop": int(bool(drop_events)),
            "pairs_with_realized_drop_fallback_and_busy": int(bool(drop_events) and shared),
            "pairs_with_realized_drop_fallback_busy_and_held_epoch": int(bool(drop_events) and shared and held > 0),
            "fallback_records_in_exposed_pairs": len(logs["FALLBACK"]) if drop_events else 0,
            "admission_busy_records_in_exposed_pairs": len(logs["APP_BUSY"]) if drop_events else 0,
            "held_epochs_in_exposed_pairs": held if drop_events else 0,
        }
    return counts


def trace_chains(witnesses, topology, timeline, plans):
    chains = []
    for witness in witnesses:
        pair_id = witness["pair_id"]
        blocker = witness["blocking_task_id"]
        successor = witness["task_id"]
        info = timeline[(pair_id, "B2-info")]
        baseline = timeline[(pair_id, "B1")]
        for arm in (info, baseline):
            found = next(e for e in arm["C2_FINAL_AUTHORIZATION"] if e["task_id"] == successor)
            boundary = next(e["fallback_ns"] for e in arm["RELEASE"] if e["task_id"] == successor)
            proof = found["approval"]
            if proof is None or not proof["c2_commit_before_lease"] or proof["c2_commit_return_ns"] >= boundary:
                break
        else:
            release = next(e for e in info["RELEASE"] if e["task_id"] == blocker)
            fallback = release["fallback_ns"]
            span = witness["info_blocker_reuse_ns_after_its_release"] + release["release_ns"]
            released = [e for e in info["APP_RELEASE"] if e["task_id"] == blocker
                        and e["release_ns"] == span and e["reason"] == "oracle_observed_fallback"]
            if len(released) != 1:
                continue
            epoch = released[0]["epoch"]
            candidates = [
                (delivery["observed_ns"], cancel["commit_return_ns"])
                for delivery in info["ORACLE_INFO_DELIVERY"] for cancel in info["APP_CANCEL_ACCEPTED"]
                if delivery["task_id"] == blocker == cancel["task_id"]
                and cancel["reason"] == "oracle_observed_fallback" and cancel["epoch"] == epoch
                and clock_domain(delivery) == clock_domain(cancel) == clock_domain(release)
                and delivery["observed_ns"] <= cancel["commit_return_ns"] <= span
            ]
            if not candidates:
                continue
            info_ns, cancel_ns = min(candidates)
            activation = [e for e in info["APP_START"] if e["task_id"] == blocker and e["epoch"] == epoch]
            if activation and not any(
                    signal["task_id"] == exit_event["task_id"] == blocker
                    and signal["epoch"] == exit_event["epoch"] == epoch
                    and cancel_ns <= signal["stop_requested_ns"] <= exit_event["confirmed_ns"] <= span
                    for signal in info["APP_STOP_REQUESTED"] for exit_event in info["APP_WORKER_EXIT_CONFIRMED"]):
                continue
            chains.append({
                **witness, "topology": tuple(topology), "load": plans[pair_id]["load"],
                "oracle_delivery_after_blocker_release_ns": info_ns - release["release_ns"],
                "oracle_cancel_commit_after_blocker_release_ns": cancel_ns - release["release_ns"],
                "public_cutoff_after_blocker_release_ns": fallback - release["release_ns"],
                # Knowledge of a fixed public cutoff can already trigger a safe
                # stop. Earlier task scheduling after that cutoff is ambiguous.
                "new_information_precedes_public_cutoff": info_ns < fallback,
            })
    return chains

def contrast(strata, newer, baseline, metric, *, units):
    values = {}
    for stratum, repeats in strata.items():
        values[stratum] = []
        for arms in repeats:
            left = arms[newer][metric]
            right = arms[baseline][metric]
            values[stratum].append(left - right if left is not None and right is not None else None)
    return {"units": units, **stratified_interval(values)}


def verify_b1_authorities(directory, plan, pairs):
    """Cross-check B1 final application proofs with the retained native lane bytes."""
    refs = {}
    stats = defaultdict(int)
    for pair_id, pair in pairs.items():
        path = directory / "runs" / pair_id / "B1" / "events.jsonl"
        raw = path.read_bytes()
        refs[path.relative_to(directory).as_posix()] = sha256(raw).hexdigest()
        inputs = c2_approval_inputs(path, directory, plan, pair,
                                    [decode(line) for line in raw.splitlines()], refs)
        require(inputs is not None, f"{pair_id} B1: native final authorization unavailable")
        for task in pair["tasks"]:
            proof = inputs[task["task_id"]]
            ready = proof["grant_ready_ns"]
            fallback_offset = task["release_offset_ns"] + task["fallback_ns"]
            stats["tasks"] += 1
            stats["commits"] += proof["c2_commit_offset_ns"] is not None
            stats["eligible_before_fallback"] += ready is not None and ready < fallback_offset
    return {"counts": stats, "source_event_sha256": refs}


def matched_busy_exposure(logs, run, slots):
    """Describe real admission while an already-fallen-back owner still held capacity."""
    fallback = {e["task_id"]: e["fallback_started_ns"] for e in logs["FALLBACK"]}
    drops = defaultdict(list)
    for event in logs["C2_RELAY_DROP"] + logs["RPC_DROP"]:
        if event["route"] in ("/rdinp/commit", "/execute", "/status", "/cancel"):
            drops[event["task_id"]].append(event["fault_gate_ns"])
    matched = set()
    matched_drop = set()
    for event in logs["APP_BUSY"]:
        stamp = busy_sample_ns(event)
        owners = [a for a in run["allocation_witnesses"] if
                  a["clock_domain"] == list(clock_domain(event)) and
                  a["allocated_ns"] <= stamp < a["reusable_ns"]]
        if len({a["slot"] for a in owners}) < slots:
            continue
        for owner in owners:
            task = owner["task_id"]
            if task == event["task_id"] or task not in fallback or not (
                    owner["allocated_ns"] <= fallback[task] <= stamp):
                continue
            key = (event["task_id"], task, owner["epoch"])
            matched.add(key)
            if any(owner["allocated_ns"] <= drop <= stamp for drop in drops[task]):
                matched_drop.add(key)
    return {
        "busy_with_fallen_back_owner": len(matched),
        "busy_with_fallen_back_owner_and_linked_drop": len(matched_drop),
    }


def summarize(directories, ideal_filename):
    require(len(directories) == len(set(directories)) == len(TOPOLOGIES),
            "each topology must come from its own run")
    strata = defaultdict(list)
    totals = {method: defaultdict(int) for method in PHYSICAL_METHODS}
    identities = set()
    seen_topologies = set()
    cohorts = []
    chains = []
    traffic = []
    pivot_counts = {direction: defaultdict(int) for direction in ("uplink", "downlink")}
    modeled = []
    hashes = []
    for directory in directories:
        plan_path = directory / "plan.json"
        plan = decode(plan_path.read_bytes())
        pairs, topology, fixture = check_plan(plan)
        calibration_sha256 = check_measurement(directory, plan)
        require(topology not in seen_topologies and plan["run_id"] not in identities,
                "same run or topology submitted twice")
        identities.add(plan["run_id"])
        seen_topologies.add(topology)
        hashes.append((plan["source_sha256"], plan["frozen_c2_sha256"], fixture))
        measured = audit(directory)
        timeline = load_timeline(directory, pairs)
        _, tasks, methods = plan_index(plan)
        rows = read_rows(directory / "per_task.csv", plan, tasks, methods)
        data = {(run["pair_id"], run["method"]): run for run in measured["run_results"]}
        exposures = defaultdict(int)
        for pair_id, pair in pairs.items():
            arms = {}
            for method in methods:
                run = data[(pair_id, method)]
                n = run["released"]
                require(n == TASKS, f"{pair_id}/{method}: each release must be counted")
                logs = timeline[(pair_id, method)]
                if method == "B1" and pair["load"] in (0.7, 0.9):
                    for direction, exposure in pivot_exposures(pair, logs, run).items():
                        for key, value in exposure.items():
                            pivot_counts[direction][key] += value
                run_rows = rows[(pair_id, method)]
                busy_losses = len(audit_busy(run_rows, logs, run))
                discarded_cpu_ns = run.get("discarded_worker_cpu_ns_per_released")
                require(type(discarded_cpu_ns) in (int, float) and math.isfinite(discarded_cpu_ns)
                        and discarded_cpu_ns >= 0, "missing or invalid Linux discarded-worker CPU sample")
                arms[method] = {
                    "qualified": 100 * run["qualified"] / n,
                    "timely_edge": 100 * run["timely_edge"] / n,
                    "low_tier_fallback": 100 * run["low_tier_fallback"] / n,
                    "post_fallback_busy_unqualified": 100 * busy_losses / n,
                    "discarded_worker_cpu_ms": discarded_cpu_ns / MS,
                    "slot_tail_ms": (run["fallback_occupied_slot_ns_per_released"] / MS
                                     if run["fallback_occupied_slot_ns_per_released"] is not None else None),
                    "cpu_tail_upper_ms": (run["fallback_cpu_ns_upper_per_released"] / MS
                                          if run["fallback_cpu_ns_upper_per_released"] is not None else None),
                }
                for key in ("released", "qualified", "timely_edge", "timely_local", "low_tier_fallback",
                            "late", "missing", "timely_low_quality"):
                    totals[method][key] += run[key]
                totals[method]["post_fallback_busy_unqualified"] += busy_losses
                key = pair["load"], pair["condition"], method
                drops = logs["C2_RELAY_DROP"] + logs["RPC_DROP"]
                exposures[(*key, "commit_drops")] += sum(
                    event["route"] == "/rdinp/commit" for event in drops
                )
                exposures[(*key, "result_query_drops")] += sum(
                    event["route"] in ("/status", "/execute") for event in drops
                )
                exposures[(*key, "affected_pair_count")] += bool(drops)
                exposures[(*key, "busy_pair_count")] += bool(logs["APP_BUSY"])
                for name, count in matched_busy_exposure(logs, run, pair["slots"]).items():
                    exposures[(*key, name)] += count
            strata[(*topology, pair["load"], pair["condition"])].append(arms)
        traffic.extend({"topology": topology, "load": load, "condition": condition, "method": method,
                        "kind": kind, "count": count}
                       for (load, condition, method, kind), count in sorted(exposures.items()))
        chains.extend(trace_chains(measured["downstream_witnesses"], topology, timeline, pairs))

        shadow = replay(directory)
        require(shadow["plan_sha256"] == measured["plan_sha256"], "raw and modeled plan digests differ")
        if ideal_filename:
            expected = decode((directory / ideal_filename).read_bytes())
            require(shadow == expected, "stored B2-ideal artifact differs from independent replay")
        if shadow["status"] == "MODELLED":
            require(len(shadow["pairs"]) == len(pairs)
                    and {r["pair_id"] for r in shadow["pairs"]} == set(pairs),
                    "model pair coverage mismatch")
            for result in shadow["pairs"]:
                require(result["model_control"]["released"] == result["model_ideal"]["released"] == TASKS,
                        "model release denominators differ from the plan")
        modeled.append({"topology": topology, "evidence": shadow})
        cohorts.append({
            "directory": str(directory), "topology": topology, "run_id": plan["run_id"],
            "plan_sha256": measured["plan_sha256"], "table_sha256": measured["table_sha256"],
            "calibration_event_sha256": calibration_sha256,
            "native_b1_authorizations": verify_b1_authorities(directory, plan, pairs),
            "source_sha256": plan["source_sha256"], "frozen_c2_sha256": plan["frozen_c2_sha256"],
            "event_sha256": {f"{r['pair_id']}/{r['method']}": r["event_sha256"] for r in data.values()},
            "paired_runs": measured["pairs"], "released_method_observations": measured["released_method_observations"],
        })
    require(seen_topologies == TOPOLOGIES and hashes[0] == hashes[1],
            "topology coverage or cross-run source/input hashes differ")
    require(all(len(values) == len(ORDERS) for values in strata.values()), "incomplete analyzed strata")
    high = {key: values for key, values in strata.items() if key[2] in (0.7, 0.9)}
    primary = contrast(high, "B2-info", "B1", "qualified", units="percentage points")
    # A positive ancillary contrast means fewer unqualified releases exposed
    # to a BUSY interval in B2-info. This proxy does not prove slot causality.
    downstream = contrast(high, "B1", "B2-info", "post_fallback_busy_unqualified", units="percentage points")
    units = {
        "qualified": "percentage points", "timely_edge": "percentage points",
        "low_tier_fallback": "percentage points", "post_fallback_busy_unqualified": "percentage points",
        "slot_tail_ms": "ms per released task", "cpu_tail_upper_ms": "ms per released task",
        "discarded_worker_cpu_ms": "CPU ms per released task",
    }
    supported = all(r["evidence"]["status"] == "MODELLED" for r in modeled)
    exposed = all(counts["pairs_with_realized_drop_fallback_and_busy"] > 0
                  for counts in pivot_counts.values())
    decision = evaluate_signal(primary, downstream, [c for c in chains if c["load"] in (0.7, 0.9)],
                               supported, exposed)
    return {
        "schema": "rdinp-g1a-decision-v1",
        "decision_protocol": PROTOCOL,
        "scope": "controlled application fault injection with real CPU work; fixture quality floor",
        "scope_limits": [
            "No field latency, reliability SLA, or physical RF link is validated.",
            "Inference assumes separately executed paired runs are independent conditional on the fixed strata.",
            "An exposure to BUSY after another task falls back is descriptive unless the linked events support attribution.",
            "Actual oracle delivery at or after an already public cutoff may change scheduler timing without adding information.",
            "Discarded CPU includes the sampled user plus system CPU across the lifetimes of worker processes with unadopted output generations.",
            "Modeled zero stop-to-reuse results are sensitivity evidence and do not enter the physical effect or gate threshold.",
        ],
        "cohorts": cohorts,
        "primary": {
            "endpoint": "qualified on-time adoptions",
            "loads": [0.7, 0.9],
            "effect": "B2-info minus B1",
            "minimum_effect_pp": GO_MARGIN_PP,
            **primary,
        },
        "middle_high_ancillary": downstream,
        "sampling": {"primary_strata": len(high), "bootstrap_unit": "complete run pair",
                     "strata": "topology, load, condition", "stratum_weight": "equal",
                     "draws": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED},
        "physical_counts": totals,
        "physical_all_load_arm_estimates": {
            method: {
                key: {"units": "percent" if unit == "percentage points" else unit,
                      **stratified_interval({stratum: [row[method][key] for row in repeats]
                                             for stratum, repeats in strata.items()})}
                for key, unit in units.items()
            }
            for method in PHYSICAL_METHODS
        },
        "physical_all_load_contrasts": {
            f"{arm} minus {base}": {key: contrast(strata, arm, base, key, units=unit)
                                  for key, unit in units.items()}
            for arm, base in (("B1", "B0"), ("B2-info", "B1"))
        },
        "per_stratum_physical_effect": [
            {"terminals": key[0], "slots": key[1], "load": key[2], "condition": key[3],
             **contrast({key: values}, "B2-info", "B1", "qualified", units="percentage points")}
            for key, values in sorted(strata.items())
        ],
        "fault_and_busy_exposures": traffic,
        "pivot_primary_exposures": {
            "criterion": "For each direction, at least one primary B1 pair has an observed drop within its "
                         "planned fallback-straddling window, a fallback event, and an admission BUSY event.",
            "held_epochs": "Positive retained-slot epochs after actual fallback, shown as exposure diagnostics.",
            "counts_by_direction": pivot_counts,
            "coverage_complete": exposed,
        },
        "linked_post_fallback_chains": chains,
        "B2-ideal_model_sensitivity_only": modeled,
        "decision": decision,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs=2, type=Path, help="One completed run directory per topology")
    parser.add_argument("--ideal-filename", help="Optionally compare a saved replay within each run directory")
    parser.add_argument("--out", required=True, type=Path, help="A new JSON decision report")
    args = parser.parse_args()
    if args.ideal_filename:
        require(Path(args.ideal_filename).name == args.ideal_filename and args.ideal_filename not in (".", ".."),
                "ideal filename must name a file within each run")
    report = summarize([path.resolve() for path in args.directories], args.ideal_filename)
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, allow_nan=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()

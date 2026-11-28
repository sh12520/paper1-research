"""Audit fixed 400 ms permit-prototype evidence and evaluate the author's gate."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sys


RDINP = Path(__file__).resolve().parents[2]
MS = 1_000_000
PROTOCOL_FILES = {
    "protocol/permit-v1/permit.py", "protocol/permit-v1/permit_server.py",
    "protocol/permit-v1/permit_wire.py", "protocol/permit-v1/permit.schema.json",
    "protocol/c2/contracts.py", "protocol/c2/crypto.py", "protocol/c2/trust.schema.json",
    "experiments/service-worker/image_workload.py", "experiments/permit-prototype/adoption.py",
}
METHODS = ("Structured-RDINP", "Reactive-ReNeg")
GRADES = ("main", "light", "local", "missed")
PHASES = {"INTENT_INITIAL", "INTENT_REPLAY", "COMMIT_INITIAL", "COMMIT_REPLAY"}
SAFETY_CASES = {
    "clean_control", "receipt_lost", "receipt_delayed", "late_result",
    "old_generation_result", "duplicate_commit_across_renewal",
}


def need(predicate, message):
    if not predicate:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def log_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from (json.loads(line) for line in handle)


def quantile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def window(row, edge_ns, deadline_ns):
    release = int(row["release_ns"])
    adopted = int(row["adopted_ns"])
    grade = row["grade"]
    utility = float(row["utility"])
    need(grade in GRADES and math.isfinite(utility) and 0 <= utility <= 1,
         f"invalid grade/utility {row['task_id']}")
    need(adopted >= release and int(row["edge_cutoff_ns"]) == release + edge_ns and
         int(row["deadline_ns"]) == release + deadline_ns, f"invalid clock window {row['task_id']}")
    need(math.isclose(float(row["end_to_end_ms"]), (adopted - release) / MS, abs_tol=1e-8),
         f"elapsed time differs from stamps {row['task_id']}")
    if grade in ("main", "light"):
        need(adopted < release + edge_ns and int(row["queue_ns"]) >= 0 and int(row["service_ns"]) >= 0,
             f"late or ill-timed edge adoption {row['task_id']}")
    elif grade == "local":
        need(release + edge_ns <= adopted < release + deadline_ns,
             f"local result violated fallback/deadline {row['task_id']}")
    else:
        need(utility == 0 and adopted >= release + deadline_ns,
             f"missed task not scored zero or not late {row['task_id']}")
    return utility


def verify_sources(mapping, required):
    need(required <= set(mapping), "source provenance omitted a required executable file")
    for name, expected in mapping.items():
        path = (RDINP / name).resolve()
        need(path.is_relative_to(RDINP) and sha(path) == expected, f"source checksum mismatch for {name}")


def audit_safety(path, edge_ms, deadline_ms):
    data = load(path)
    need(data["source_unchanged"] is True, "safety test source changed during its run")
    verify_sources(data["source_sha256"], PROTOCOL_FILES | {"experiments/permit-prototype/check_protocol.py"})
    cases = {row["case"]: row for row in data["cases"]}
    need(data["status"] == "PASS" and data["expected_cases"] == len(SAFETY_CASES) and
         len(data["cases"]) == len(cases) and set(cases) == SAFETY_CASES and
         all(row["status"] == "PASS" for row in cases.values()), "safety fixture matrix is incomplete or failed")
    need(data["deadline_ms"] == deadline_ms and data["local_reserve_ms"] == deadline_ms - edge_ms,
         "safety fixture deadline inconsistent with the scored plan")
    need(data["old_generation_pollution"] == data["duplicate_effects"] == 0,
         "safety fixture reported old-generation pollution or repeated effects")
    clean = cases["clean_control"]
    need(clean["accepted"] is True and clean["worker_starts"] == clean["effects"] == 1,
         "clean control did not actually adopt a single effect")
    for label in ("receipt_lost", "receipt_delayed"):
        row = cases[label]
        need(row["faulted_receipt_bytes"] > 0 and row["edge_worker_starts"] == row["edge_effects"] == 0 and
             edge_ms <= row["fallback_adopted_ms"] < deadline_ms, f"receipt fixture missed safe fallback: {label}")
    need(cases["receipt_lost"]["late_valid_tokens_observed"] == 0 and
         cases["receipt_delayed"]["late_valid_tokens_observed"] == 1,
         "receipt fixtures did not demonstrate loss and delayed valid delivery separately")
    late, stale = cases["late_result"], cases["old_generation_result"]
    need(late["signed_result_delivered_ms"] >= edge_ms and
         edge_ms <= late["fallback_adopted_ms"] < deadline_ms and
         late["effect_count"] == late["guard"]["late"] == late["late_rejections"] == 1,
         "signed late result fixture did not prove a late rejection")
    need(0 <= stale["signed_result_presentation_ms"] < edge_ms and
         stale["current_generation"] > stale["prior_generation"] and
         stale["effect_count"] == stale["guard"]["old_generation"] == stale["stale_generation_rejections"] == 1,
         "stale-generation fixture did not distinguish generation rejection from a deadline miss")
    duplicate = cases["duplicate_commit_across_renewal"]
    need(sorted(duplicate["same_generation_statuses"]) == ["REJECT", "RESULT"] and
         duplicate["renewed_duplicate_status"] == "REJECT" and
         duplicate["fresh_task_under_renewed_permit"] == "RESULT" and
         duplicate["worker_starts_for_reused_id"] == duplicate["effects_for_reused_id"] ==
         duplicate["duplicate_adoption_rejections"] == duplicate["guard"]["duplicate"] == 1,
         "duplicate fixture did not prove rejection and exactly one effect")
    return data


def audit_c2(path):
    data = load(path)
    need(data["scope"] == "REAL_SOFTWARE_LOOPBACK_FOUR_PHASE_CONTROL_ONLY", "incorrect C2 benchmark scope")
    trials = data["trials"]
    need(data["trial_count"] == len(trials) and
         len({row["task_id"] for row in trials}) == len(trials) > 0, "incomplete C2 control denominator")
    confirmed = [row for row in trials if row["confirmation_complete"] and row["status"] == "COMMITTED"]
    need(data["confirmed_count"] == len(confirmed) > 0 and data["requests_without_peer_ingress"] == 0,
         "no verified complete C2 four-phase path or wire mismatch")
    for row in confirmed:
        exchanges = row["winning_exchanges"]
        need(set(exchanges) == PHASES, "C2 control confirmation missing a phase")
        winning = sum(leg["request_body_bytes"] + leg["reply_body_bytes"] for leg in exchanges.values())
        need(0 < winning == row["winning_body_bytes"] <= row["all_attempt_body_bytes"] ==
             row["peer_observed_body_bytes"], "C2 request/response cost not reconciled")
    check_mean = sum(row["all_attempt_body_bytes"] for row in trials) / len(trials)
    need(math.isclose(data["actual_body_bytes_per_released_task"], check_mean, abs_tol=1e-9),
         "C2 all-attempt average uses incorrect denominator")
    return {key: data[key] for key in (
        "scope", "trial_count", "confirmed_count", "request_byte_boundary", "response_byte_boundary",
        "elapsed_release_to_terminal_ms", "confirmed_elapsed_release_to_terminal_ms",
        "elapsed_protocol_only_ms", "winning_body_bytes_confirmed",
        "actual_body_bytes_per_released_task", "complete_within_400ms_control_only", "sign_verify_ms",
    )}


def verify_completion(directory):
    doc = load(directory / "COMPLETE.json")
    hashes = doc["sha256"]
    need({"plan.json", "headroom.json", "per_task.csv", "per_arm.csv"} <= set(hashes),
         "completion receipt omitted a required scoring artifact")
    for name, expected in hashes.items():
        need(Path(name).name == name and sha(directory / name) == expected,
             f"completion checksum mismatch for {name}")
    return doc


def verify_headroom(directory, complete, edge_ms, deadline_ms):
    headroom = load(directory / "headroom.json")
    need(len(headroom) == 2 and [part["upload"] for part in headroom] == ["light", "main"],
         "pre/post-upload headroom evidence missing")
    result = []
    for part in headroom:
        case_rows = part["rows"]
        need(case_rows and len({row["task_id"] for row in case_rows}) == len(case_rows),
             "forced switch paths contain absent or duplicate tasks")
        samples = []
        for row in case_rows:
            window(row, edge_ms * MS, deadline_ms * MS)
            if row["grade"] == "light":
                need(row["selected_input_tier"] == part["upload"], "forced switch arm used wrong upload tier")
                samples.append(row["end_to_end_ms"])
            else:
                samples.append(deadline_ms)
        p95_margin = edge_ms - quantile(samples, .95)
        need(math.isclose(p95_margin, part["margin_p95_ms"], abs_tol=1e-8),
             "headroom margin disagrees with raw timings")
        result.append({"upload": part["upload"], "released": len(case_rows),
                       "timely_light_adoptions": sum(row["grade"] == "light" for row in case_rows),
                       "margin_p95_ms": p95_margin})
    expected_style = "auto" if result[1]["margin_p95_ms"] > 0 else "none"
    need(complete["structured_style"] == expected_style, "structured branch violated the automatic scope rule")
    return result


def unique(values, key, label):
    table = {}
    for value in values:
        name = key(value)
        need(name not in table, f"duplicate {label}: {name}")
        table[name] = value
    return table


def arm_key(row):
    return row["condition"], int(row["seed"]), row["method"]


def verify_arm(directory, key, arm, task_rows, hashes):
    condition, seed, method = key
    folder = directory / f"pair-{condition}-{seed}" / method
    logs = ("authority-audit.json", "tasks.json", "wire.jsonl.gz", "rpc.jsonl.gz")
    for name in logs:
        path = folder / name
        hashes[path.relative_to(directory).as_posix()] = sha(path)

    sealed = unique(load(folder / "tasks.json"), lambda row: row["task_id"], "arm task")
    need(set(sealed) == set(task_rows), f"scored arm JSON/CSV mismatch {key}")
    for task_id, row in task_rows.items():
        for name, value in sealed[task_id].items():
            need(row[name] == ("" if value is None else str(value)),
                 f"scored CSV row differs from arm JSON: {key}/{task_id}/{name}")

    audit = load(folder / "authority-audit.json")
    observed = unique(audit["tasks"], lambda t: t["task_id"], "authority task id")
    need(audit["status"] == "AUDIT" and audit["next_offset"] is None and
         len(observed) == audit["task_count"] and set(observed) <= set(task_rows), f"incomplete audit {key}")
    for tid, task in observed.items():
        need(task["principal"] == f"terminal-{'ab'[int(task_rows[tid]['terminal'])]}" and
             0 <= task["effects"] <= task["starts"] <= 1, f"unplanned requester or repeated effect/start {key}/{tid}")
    for tid, row in task_rows.items():
        if row["grade"] in ("main", "light"):
            need(tid in observed and observed[tid]["effects"] == observed[tid]["starts"] == 1 and
                 observed[tid]["result_sha256"] == row["result_sha256"],
                 f"adoption has no single matching durable result {key}/{tid}")
    for name in ("starts", "effects"):
        need(audit[name] == sum(task[name] for task in observed.values()) == int(arm[f"audit_{name}"]),
             f"audit {name} total mismatch {key}")

    wire = list(log_rows(folder / "wire.jsonl.gz"))
    rpc = list(log_rows(folder / "rpc.jsonl.gz"))
    need(all(e["task_id"] in task_rows for e in [*wire, *rpc]), f"wire or RPC outside paired task set {key}")
    need(all(e["direction"] in ("up", "down") and e["kind"] in ("ISSUE", "SNAPSHOT", "TASK", "SELECT") and
             e["control_bytes"] >= 0 and e["data_bytes"] >= 0 for e in wire), f"invalid wire evidence {key}")
    need(all(e["kind"] in ("ISSUE", "SNAPSHOT", "TASK", "SELECT") and e["actual_elapsed_ns"] >= 0 and
             (e["sign_ns"] is None or e["sign_ns"] >= 0) and
             (e["verify_ns"] is None or e["verify_ns"] >= 0) for e in rpc), f"invalid RPC evidence {key}")
    byte_fields = ("request_control_bytes", "response_control_bytes", "request_data_bytes", "response_data_bytes")
    need(all(type(e["request_sent"]) is bool and
             all(e[name] is None or (type(e[name]) is int and e[name] >= 0) for name in byte_fields)
             for e in rpc), f"invalid measured body-accounting data {key}")

    def measured_bytes(event, field):
        sent = event["request_" + field] if event["request_sent"] else 0
        return (sent or 0) + (event["response_" + field] or 0)

    uplink_rounds = Counter(e["kind"] for e in wire if e["direction"] == "up")
    issued = [e for e in rpc if e["kind"] == "ISSUE"]
    reconstructed = {
        "permit_total_elapsed_ns": sum(e["actual_elapsed_ns"] for e in issued),
        "permit_total_control_bytes": sum(measured_bytes(e, "control_bytes") for e in issued),
        "permit_confirmed": sum(e["status"] == "PERMIT" for e in issued),
        "terminal_sign_total_ns": sum(e["sign_ns"] or 0 for e in rpc),
        "terminal_verify_total_ns": sum(e["verify_ns"] or 0 for e in rpc),
        "control_body_bytes": sum(measured_bytes(e, "control_bytes") for e in rpc),
        "control_body_attempted_bytes": sum(e["control_bytes"] for e in wire),
        "data_body_bytes": sum(measured_bytes(e, "data_bytes") for e in rpc),
        "issue_requests": uplink_rounds["ISSUE"],
        "extra_select_requests": uplink_rounds["SELECT"],
    }
    for name, value in reconstructed.items():
        need(int(arm[name]) == value, f"raw wire/RPC differs from aggregate {key}/{name}")
    return {**reconstructed, "request_rounds_observed": sum(uplink_rounds.values()),
            "snapshot_requests": uplink_rounds["SNAPSHOT"], "task_requests": uplink_rounds["TASK"],
            "actual_loopback_requests": sum(e["request_sent"] for e in rpc),
            "audit_starts": audit["starts"], "audit_effects": audit["effects"]}


def aggregate(task_rows, arms):
    count = len(task_rows)
    observed = Counter(row["grade"] for row in task_rows)
    result = {grade: observed[grade] for grade in GRADES}
    result["released"] = count
    result["edge_adopted"] = observed["main"] + observed["light"]
    result["timely_adopted"] = count - observed["missed"]
    result["edge_adoption_rate"] = result["edge_adopted"] / count
    result["timely_adoption_rate"] = result["timely_adopted"] / count
    result["mean_utility"] = math.fsum(float(row["utility"]) for row in task_rows) / count
    times = [float(row["end_to_end_ms"]) for row in task_rows]
    result["end_to_end_ms"] = {"n": count, "p50": quantile(times, .5), "p95": quantile(times, .95)}
    edge_rows = [row for row in task_rows if row["grade"] in ("main", "light")]
    result["edge_observed_ms"] = {
        name: ({"n": len(edge_rows), "p50": quantile(vals, .5), "p95": quantile(vals, .95)} if edge_rows else None)
        for name in ("queue_ns", "service_ns")
        for vals in [[int(row[name]) / MS for row in edge_rows]]
    }
    totals = Counter()
    for arm in arms:
        totals.update(arm)
    result["cost"] = dict(totals)
    for name in ("control_body_bytes", "control_body_attempted_bytes", "data_body_bytes",
                 "permit_total_control_bytes", "request_rounds_observed", "actual_loopback_requests", "extra_select_requests"):
        result["cost"][f"{name}_per_released"] = totals[name] / count
    for source, metric in (("permit_total_elapsed_ns", "amortized_permit_ms_per_released"),
                           ("terminal_sign_total_ns", "terminal_sign_ms_per_released"),
                           ("terminal_verify_total_ns", "terminal_verify_ms_per_released")):
        result["cost"][metric] = totals[source] / MS / count
    return result


def summarize_pairs(directory):
    complete = verify_completion(directory)
    plan = load(directory / "plan.json")
    need(plan["scope"] == "real software, controlled link paired evaluation" and plan["deadline_ms"] == 400 and
         plan["fallback_reserve_ms"] == 55 and tuple(plan["methods"]) == METHODS,
         "scope is not the fixed 400 ms experiment")
    verify_sources(plan["source_sha256"], PROTOCOL_FILES | {"experiments/permit-prototype/run_pairs.py"})
    edge_ms = plan["deadline_ms"] - plan["fallback_reserve_ms"]
    headroom = verify_headroom(directory, complete, edge_ms, plan["deadline_ms"])
    expected = unique(plan["cases"], lambda c: (c["condition"], c["seed"]), "planned condition/seed")
    need(expected and {key[0] for key in expected} == set(plan["trace"]) and
         len(expected) == complete["pair_count"], "completion receipt or condition coverage disagrees with plan")
    arms_by_key = unique(rows(directory / "per_arm.csv"), arm_key, "scored arm")
    required = {(condition, seed, method) for condition, seed in expected for method in METHODS}
    need(required == set(arms_by_key) and len(required) == complete["method_runs"], "missing or unplanned arm")
    groups = defaultdict(dict)
    for row in rows(directory / "per_task.csv"):
        key = arm_key(row)
        task_id = row["task_id"]
        need(key in required and task_id not in groups[key], f"repeat or unplanned scored result {key}/{task_id}")
        window(row, edge_ms * MS, plan["deadline_ms"] * MS)
        groups[key][task_id] = row
    need(set(groups) == required and complete["task_rows"] == sum(map(len, groups.values())),
         "task output coverage disagrees with completion receipt")
    comparisons = defaultdict(list)
    arm_stats = {}
    by_condition = defaultdict(lambda: defaultdict(list))
    evidence = dict(complete["sha256"])
    for (condition, seed), case in sorted(expected.items()):
        planned = unique(case["tasks"], lambda t: t["task_id"], "planned task")
        need(planned, f"empty plan for {condition}/{seed}")
        left, right = (groups[condition, seed, m] for m in METHODS)
        for method, group in zip(METHODS, (left, right)):
            key = condition, seed, method
            style = complete["structured_style"] if method == METHODS[0] else "offer"
            need(arms_by_key[key]["style"] == style and set(group) == set(planned), f"wrong task coverage/style {key}")
            anchors = set()
            for tid, task in planned.items():
                row = group[tid]
                need(all(str(task[name]) == row[name] for name in ("release_ms", "terminal", "epoch_window", "image")),
                     f"planned task parameters not honored {key}/{tid}")
                anchors.add(int(row["release_ns"]) - int(row["release_ms"]) * MS)
            need(len(anchors) == 1, f"arm tasks did not share a release clock {key}")
            arm_stats[key] = verify_arm(directory, key, arms_by_key[key], group, evidence)
            by_condition[condition][method].extend(group.values())
        comparisons[seed].extend(float(left[tid]["utility"]) - float(right[tid]["utility"]) for tid in planned)

    diffs = [d for samples in comparisons.values() for d in samples]
    delta = math.fsum(diffs) / len(diffs)
    # Resample seeds across all linked trace conditions, preserving within-seed dependence.
    clusters = [(math.fsum(v), len(v)) for _, v in sorted(comparisons.items())]
    rng = random.Random("RDINP-permit-prototype-paired-seed-v1")
    distributions = []
    for _ in range(4000):
        draw = rng.choices(clusters, k=len(clusters))
        distributions.append(math.fsum(total for total, _ in draw) / sum(n for _, n in draw))
    methods = {
        method: aggregate(
            [row for key, group in groups.items() if key[2] == method for row in group.values()],
            [arm for key, arm in arm_stats.items() if key[2] == method],
        ) for method in METHODS
    }
    conditions = {
        condition: {
            method: aggregate(task_rows, [arm for key, arm in arm_stats.items() if key[0] == condition and key[2] == method])
            for method, task_rows in cohort.items()
        } for condition, cohort in sorted(by_condition.items())
    }
    return {
        "net_utility_delta": delta,
        "paired_seed_cluster_ci95": [quantile(distributions, .025), quantile(distributions, .975)],
        "counts": {"pairs": len(expected), "seed_clusters": len(clusters),
                   "method_runs": len(required), "task_rows": 2 * len(diffs), "per_method": len(diffs)},
        "headroom": headroom,
        "structured_style": complete["structured_style"],
        "methods": methods,
        "by_condition": conditions,
        "evidence_sha256": evidence,
    }


def evaluate(pairs, matrix, c2):
    data = summarize_pairs(pairs)
    safety = audit_safety(matrix, 345, 400)
    cost = audit_c2(c2)
    return {
        "decision": "PROCEED_STEP3" if data["net_utility_delta"] > 0 else "SCIENTIFIC_STOP",
        "scientific_gate_evaluated": True,
        "utility_definition": (
            "mean paired structured-minus-reactive adopted quality over all released tasks; "
            "lateness or failure is zero; measured protocol waiting already affects timeliness"
        ),
        "interval_scope": "exploratory 4000-draw percentile interval over paired seed clusters; not a gate",
        "old_generation_pollution": safety["old_generation_pollution"],
        "duplicate_effects": safety["duplicate_effects"],
        "safety": safety,
        "c2_control_only": cost,
        **data,
        "matrix_sha256": sha(matrix),
        "c2_sha256": sha(c2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pairs", "matrix", "c2", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(args.pairs, args.matrix, args.c2)
        code = 0
    except (OSError, ValueError, KeyError, TypeError, IndexError, ZeroDivisionError) as error:
        report = {"decision": "ENGINEERING_INVALID", "scientific_gate_evaluated": False,
                  "error_type": type(error).__name__, "error": str(error)}
        code = 2
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(report["decision"], report.get("net_utility_delta", report.get("error", "")))
    return code


if __name__ == "__main__":
    sys.exit(main())

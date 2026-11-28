"""Validate and score the preplanned RDINP 16-seed loopback expansion."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

import gate
import run_expansion as design


CONDITIONS = ("plain", "half", "dynamic")
METRICS = ("utility", "edge_adoption_rate", "timely_adoption_rate")
REFERENCES = {
    "structured_minus_reactive": "Reactive-ReNeg",
    "structured_minus_no_switch": "Same-Permit-No-Switch",
}
BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_SEED = "RDINP-expansion-paired-clusters-v1"


def audit_plan(directory):
    plan = gate.load(directory / "plan.json")
    original = design.original
    expected_trace = json.loads(json.dumps(original.TRACE))
    gate.need(
        plan["phase"] == "independent 16-seed engineering expansion"
        and tuple(plan["seeds"]) == design.SEEDS and set(plan["trace"]) == set(CONDITIONS)
        and tuple(plan["methods"]) == design.METHODS and plan["styles"] == design.STYLES
        and plan["deadline_ms"] == 400 and plan["fallback_reserve_ms"] == 55
        and plan["trace"] == expected_trace and plan["slots"] == original.SLOT_COUNT
        and plan["permit_ttl_ms"] == original.PERMIT_TTL_MS
        and plan["snapshot_max_age_ns"] == original.SNAPSHOT_MAX_AGE_NS
        and plan["post_upload_light_extra_tail_ns"] == design.EXTRA_TAIL_NS == 12 * gate.MS,
        "run differs from the fixed expansion settings",
    )
    gate.need(plan["source_sha256"] == design.sources(), "source differs from the recorded expansion")
    planned_digests = {
        name: original.CALIBRATION["input_fixtures"][name]["sha256"] for name in original.IMAGES
    }
    gate.need(plan["asset_sha256"] == planned_digests, "input fixtures differ from calibration")
    gate.need(plan["cases"] == design.scheduled_cases(), "case inputs or method order differ from schedule")
    return plan


def audit_completion(directory, cases):
    complete = gate.load(directory / "COMPLETE.json")
    required_logs = {
        f"pair-{case['condition']}-{case['seed']}/{method}/{name}"
        for case in cases for method in design.METHODS for name in design.LOGS
    }
    required_logs.update(f"headroom-{tier}/{name}" for tier in ("main", "light") for name in design.LOGS)
    files = required_logs | {"plan.json", "safety/safety.json", "headroom.json", "per_task.csv", "per_arm.csv"}
    gate.need(
        set(complete["sha256"]) == files and complete["pair_count"] == 48
        and complete["method_runs"] == 144 and complete["task_rows"] == 2304,
        "incorrect study denominator or incomplete evidence set",
    )
    for name, digest in complete["sha256"].items():
        gate.need(gate.sha(directory / name) == digest, f"completion checksum mismatch for {name}")
    return complete


def audit_headroom(directory):
    records = gate.load(directory / "headroom.json")
    gate.need([row["input_tier"] for row in records] == ["light", "main"], "missing headroom arm")
    for record in records:
        tier = record["input_tier"]
        samples = gate.load(directory / f"headroom-{tier}" / "tasks.json")
        gate.need(len(samples) == record["n"] == len({row["task_id"] for row in samples}) == 9,
                  f"wrong headroom denominator for {tier}")
        margins = []
        for sample in samples:
            gate.window(sample, 345 * gate.MS, 400 * gate.MS)
            if sample["grade"] == "light":
                gate.need(sample["selected_input_tier"] == tier, f"unexpected upload tier for {tier}")
            margins.append(sample["end_to_end_ms"] if sample["grade"] == "light" else 400)
        count = sum(row["grade"] == "light" for row in samples)
        margin = 345 - gate.quantile(margins, .95)
        gate.need(count == record["light_adopted"] and
                  math.isclose(margin, record["measured_headroom_p95_ms"], abs_tol=1e-8),
                  f"invalid feasibility summary for {tier}")
    return records


def audit_scored_arms(directory, cases, complete):
    arms_by_key = gate.unique(gate.rows(directory / "per_arm.csv"), gate.arm_key, "method run")
    expected_order = [
        (case["condition"], case["seed"], method) for case in cases for method in case["method_order"]
    ]
    gate.need(list(arms_by_key) == expected_order, "missing method run or execution order changed")
    groups = defaultdict(dict)
    for row in gate.rows(directory / "per_task.csv"):
        key = gate.arm_key(row)
        task_id = row["task_id"]
        gate.need(key in arms_by_key and task_id not in groups[key], f"unplanned or duplicate task: {key}/{task_id}")
        gate.window(row, 345 * gate.MS, 400 * gate.MS)
        groups[key][task_id] = row
    gate.need(set(groups) == set(arms_by_key) and sum(map(len, groups.values())) == complete["task_rows"],
              "incorrect scored task coverage")

    arm_stats = {}
    for case in cases:
        planned = gate.unique(case["tasks"], lambda row: row["task_id"], "planned task")
        gate.need(len(planned) == 16, "case did not release the fixed set of sixteen tasks")
        for method in design.METHODS:
            key = case["condition"], case["seed"], method
            rows = groups[key]
            gate.need(planned.keys() == rows.keys() and arms_by_key[key]["style"] == design.STYLES[method],
                      f"incorrect task set or policy for {key}")
            anchors = set()
            for tid, task in planned.items():
                row = rows[tid]
                payload_fields = ("release_ms", "terminal", "epoch_window", "image")
                gate.need(all(str(task[name]) == row[name] for name in payload_fields),
                          f"task differs from the common input plan: {key}/{tid}")
                anchors.add(int(row["release_ns"]) - int(row["release_ms"]) * gate.MS)
                if row["grade"] in ("main", "light"):
                    gate.need(row["selected_input_tier"] in ("main", "light") and
                              (row["grade"], row["selected_input_tier"]) != ("main", "light"),
                              f"invalid adopted edge tier: {key}/{tid}")
                if method == "Same-Permit-No-Switch" and row["grade"] in ("main", "light"):
                    gate.need(row["grade"] == row["selected_input_tier"],
                              f"post-upload switch adopted in disabled arm: {key}/{tid}")
            gate.need(len(anchors) == 1, f"inconsistent release clock for {key}")
            reconciled = gate.verify_arm(directory, key, arms_by_key[key], rows, {})
            if method != "Reactive-ReNeg":
                gate.need(reconciled["extra_select_requests"] == 0, f"unexpected extra selection: {key}")
            arm_stats[key] = reconciled
    return groups, arm_stats


def aggregate(groups, arms, method, condition=None):
    keys = [key for key in groups if key[2] == method and (condition is None or key[0] == condition)]
    task_rows = [row for key in keys for row in groups[key].values()]
    result = gate.aggregate(task_rows, [arms[key] for key in keys])
    result["post_upload_light_adopted"] = sum(
        row["grade"] == "light" and row["selected_input_tier"] == "main" for row in task_rows
    )
    result["pre_upload_light_adopted"] = result["light"] - result["post_upload_light_adopted"]
    return result


def measure(row, metric):
    if metric == "utility":
        return float(row["utility"])
    if metric == "edge_adoption_rate":
        return row["grade"] in ("main", "light")
    return row["grade"] != "missed"


def paired_uncertainty(groups):
    rng = random.Random(BOOTSTRAP_SEED)
    positions = range(len(design.SEEDS))
    draws = [rng.choices(positions, k=len(positions)) for _ in range(BOOTSTRAP_DRAWS)]
    results = {}
    for name, reference in REFERENCES.items():
        cells = {}
        for metric in METRICS:
            per_condition = {}
            for condition in CONDITIONS:
                per_seed = []
                for seed in design.SEEDS:
                    left = groups[condition, seed, design.METHODS[0]]
                    right = groups[condition, seed, reference]
                    differences = (measure(row, metric) - measure(right[tid], metric) for tid, row in left.items())
                    per_seed.append(math.fsum(differences) / len(left))
                per_condition[condition] = per_seed
            per_condition["overall"] = [
                math.fsum(condition[pos] for condition in per_condition.values()) / len(CONDITIONS)
                for pos in positions
            ]
            for condition, values in per_condition.items():
                distribution = [math.fsum(values[pos] for pos in draw) / len(draw) for draw in draws]
                cells.setdefault(condition, {})[metric] = {
                    "delta": math.fsum(values) / len(values),
                    "ci95": [gate.quantile(distribution, .025), gate.quantile(distribution, .975)],
                }
        results[name] = cells
    return results


def missed_cases(groups):
    return [
        {"condition": condition, "seed": seed, "method": method, **row}
        for (condition, seed, method), rows in sorted(groups.items())
        for row in rows.values() if row["grade"] == "missed"
    ]


def evaluate(directory):
    plan = audit_plan(directory)
    complete = audit_completion(directory, plan["cases"])
    safety = gate.audit_safety(directory / "safety/safety.json", 345, 400)
    headroom = audit_headroom(directory)
    groups, arms = audit_scored_arms(directory, plan["cases"], complete)
    methods = {method: aggregate(groups, arms, method) for method in design.METHODS}
    by_condition = {
        condition: {method: aggregate(groups, arms, method, condition) for method in design.METHODS}
        for condition in CONDITIONS
    }
    contrasts = paired_uncertainty(groups)
    primary = contrasts["structured_minus_reactive"]
    checks = {
        "half_utility_ci_lower_positive": primary["half"]["utility"]["ci95"][0] > 0,
        "dynamic_utility_ci_lower_positive": primary["dynamic"]["utility"]["ci95"][0] > 0,
        "no_extra_deadline_misses_overall": methods[design.METHODS[0]]["missed"] <= methods[design.METHODS[1]]["missed"],
        "plain_utility_no_clear_negative_difference": primary["plain"]["utility"]["ci95"][1] >= 0,
    }
    return {
        "decision": "FOLLOWUP_CRITERIA_MET" if all(checks.values()) else "FOLLOWUP_CRITERIA_NOT_MET",
        "checks": checks,
        "counts": {"condition_seed_cases": 48, "seed_clusters": 16, "methods": 3,
                   "method_runs": 144, "task_rows": 2304, "per_method": 768, "per_method_condition": 256},
        "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED,
                      "unit": "paired release/fixture seed cluster shared across all three fixed traces",
                      "interval": "nominal two-sided 95% percentile",
                      "scope": "fixed traces and three source images; no claim of regular-link non-inferiority"},
        "post_upload_light_extra_tail_ns": plan["post_upload_light_extra_tail_ns"],
        "methods": methods,
        "by_condition": by_condition,
        "contrasts": contrasts,
        "deadline_misses": missed_cases(groups),
        "headroom": headroom,
        "safety": safety,
        "evidence_sha256": {"COMPLETE.json": gate.sha(directory / "COMPLETE.json"), **complete["sha256"]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(args.pairs)
    except (OSError, ValueError, KeyError, TypeError, IndexError, ZeroDivisionError) as error:
        report = {"decision": "ENGINEERING_INVALID", "error_type": type(error).__name__, "error": str(error)}
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(report["decision"], report.get("checks", report.get("error", "")))
    return 2 if report["decision"] == "ENGINEERING_INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())

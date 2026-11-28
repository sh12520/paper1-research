"""Verify complete run coverage and paired task accounting from exported artifacts."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

from sim import LIGHT, LOCAL, MAIN, METHODS, MISSED, Scenario

SUMS = ("control_bytes", "data_bytes", "requests", "grants", "grant_light", "switch_upload",
        "switch_edge", "stale_results", "busy", "air_attempts", "lost_frames")


def require(ok, detail):
    if not ok:
        raise ValueError(detail)


def audit(directory):
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    complete = json.loads((directory / "COMPLETE.json").read_text(encoding="utf-8"))
    for name, expected in complete["sha256"].items():
        require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected,
                f"digest mismatch: {name}")
    scenarios = {Scenario(**row).name: Scenario(**row) for row in plan["scenario_grid"]}
    expected = set(itertools.product(scenarios, plan["seeds"], METHODS))
    indexes = {}
    with (directory / "per_run.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = row["scenario"], int(row["seed"]), row["method"]
            require(key in expected and key not in indexes, f"unexpected run: {key}")
            indexes[key] = row
    require(indexes.keys() == expected, "missing run rows")
    require(len(indexes) == complete["run_rows"], "wrong completion run count")
    identities = {}
    task_rows = 0
    with gzip.open(directory / "per_task.csv.gz", "rt", newline="", encoding="utf-8") as handle:
        tasks = csv.DictReader(handle)
        for key, batch in itertools.groupby(tasks, lambda row: (row["scenario"], int(row["seed"]), row["method"])):
            summary = indexes.pop(key)
            pair_key = key[:2]
            seen = []
            counted = Counter()
            sums = Counter()
            n = 0
            for task in batch:
                grade = task["grade"]
                require(grade in (MAIN, LIGHT, LOCAL, MISSED), "unknown grade")
                require(int(task["task_id"]) == n, "unexpected task ID")
                require(task["input_hash"] == summary["input_hash"], "task fingerprint mismatch")
                seen.append(tuple(task[col] for col in ("terminal", "image", "release_ms", "deadline_ms",
                                                       "fallback_ms")))
                utility = float(task["utility"])
                require(0 <= utility <= 1 and (grade != MISSED or utility == 0), "invalid utility")
                if grade == MISSED:
                    require(not task["adopted_ms"], "missed task has output")
                else:
                    t = float(task["adopted_ms"])
                    require(float(task["release_ms"]) <= t < float(task["deadline_ms"]), "late adoption")
                    if grade in (MAIN, LIGHT):
                        require(task["edge_started_epoch"] == task["client_epoch"] == task["edge_epoch"],
                                "adopted wrong generation")
                        require(key[2] == "Fixed-Intent" or t < float(task["fallback_ms"]),
                                "adopted edge after fallback point")
                require(key[2] != "Fixed-Intent" or grade in (MAIN, MISSED), "fixed tier changed")
                require(key[2] != "Static-Fallback" or grade != LIGHT, "static tier changed")
                require(int(task["requests"]) <= (2 if key[2] == "Reactive-ReNeg" else 1),
                        "unexpected negotiation")
                counted[grade] += 1
                for field in SUMS:
                    sums[field] += int(task[field])
                for field in ("utility", "rounds", "negotiation_ms"):
                    sums[f"{field}_sum"] += float(task[field])
                n += 1
            require(identities.setdefault(pair_key, (summary["input_hash"], seen)) ==
                    (summary["input_hash"], seen), f"methods did not share inputs: {pair_key}")
            require(n == int(summary["released"]), "release denominator mismatch")
            for field, value in counted.items():
                require(int(summary[field]) == value, f"{field} total mismatch")
            require(sum(int(summary[key]) for key in (MAIN, LIGHT, LOCAL, MISSED)) == n,
                    "grade total mismatch")
            for field, value in sums.items():
                require(math.isclose(float(summary[field]), value, abs_tol=1e-8), f"{field} total mismatch")
            task_rows += n
    require(not indexes and task_rows == complete["task_method_rows"], "missing task rows")
    require(len(identities) == complete["paired_runs"], "pair count mismatch")
    return {
        "status": "PASS", "scenarios": len(scenarios), "seed_count": len(plan["seeds"]),
        "paired_runs": len(identities), "method_runs": len(expected), "task_method_rows": task_rows,
        "checks": ["artifact digests", "complete grid", "same task identities and input hash",
                   "all-release denominator", "summaries recomputed from task rows", "deadline and generation",
                   "allowed quality tiers and negotiation counts"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    report = json.dumps(audit(args.result_dir), indent=2) + "\n"
    (args.result_dir / "AUDIT.json").write_text(report, encoding="utf-8")
    print(report)

"""Generate the fixed, paired Step 1 development sweep and preserve task-level results."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import median

from sim import (
    AIR_RATES, BIN_MS, CONTROL_SERVICE_MS, FRAME_ATTEMPTS, FRAME_BYTES,
    FRAME_HEADER_BYTES, LIGHT, LOCAL, LOCAL_RESERVE_MS, MAIN, METHODS, MISSED,
    NOMINAL_EDGE_MS, RTT_RETRY_MS, TRACE_PERIOD_MS, Scenario, Simulation, Tier,
    paired_inputs, read_capacity,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TRACE = REPO / "archive/genspace/PAPER1-PROBLEM-BASELINE-RESET/native_replay/OptimizeRBs/capacity-events.csv"
LOADS = (0.4, 0.7, 0.9)
LOSSES = (0.0, 0.05, 0.15)
DIPS = (0.0, 0.5, 0.75)
DEADLINES = (400, 600, 800)
SEEDS = tuple(range(10))
DURATION_MS = 10_000
TERMINALS, SLOTS = 8, 2
REFERENCE = Scenario(.7, .05, .5, 600)
TASK_FIELDS = (
    "scenario", "seed", "input_hash", "method", "task_id", "terminal", "image", "release_ms",
    "deadline_ms", "fallback_ms", "grade", "adopted_ms", "reason", "utility", "requests",
    "grants", "rounds", "negotiation_ms", "control_bytes", "data_bytes", "air_attempts",
    "lost_frames", "busy", "grant_light", "switch_upload", "switch_edge", "stale_results",
    "local_started", "local_finished", "edge_started_epoch", "edge_epoch", "client_epoch",
)


def profiles_from_calibration(path, edge_ms):
    data = json.loads(path.read_text(encoding="utf-8"))
    workloads = data["workloads"]
    main_reference = median(row["main"]["cpu_ms"] for row in workloads.values())
    scale = edge_ms / main_reference
    profiles = {}
    for name, values in sorted(workloads.items()):
        tiers = {}
        for grade, key in ((MAIN, "main"), (LIGHT, "light"), (LOCAL, "local")):
            row = values[key]
            tiers[grade] = Tier(
                int(row["upload_bytes"]), int(row["download_bytes"]),
                row["cpu_ms"] * (1 if grade == LOCAL else scale),
                row.get("prepare_ms", 0), row["utility"],
            )
            tier = tiers[grade]
            if (
                min(tier.upload, tier.download, tier.prepare) < 0 or tier.service <= 0
                or not 0 <= tier.utility <= 1
                or not all(math.isfinite(v) for v in asdict(tier).values())
            ):
                raise ValueError(f"invalid tier for {name}: {tier}")
        if not (tiers[LIGHT].upload < tiers[MAIN].upload and tiers[LIGHT].service < tiers[MAIN].service):
            raise ValueError(f"light tier is not lighter for {name}")
        profiles[name] = tiers
    return profiles, scale


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_row(task, scenario, seed, input_hash, method):
    grade = task.grade
    row = {
        "scenario": scenario.name, "seed": seed, "input_hash": input_hash,
        "method": method, "task_id": task.release.task_id, "terminal": task.release.terminal,
        "image": task.release.image, "release_ms": task.release.at, "deadline_ms": task.deadline,
        "fallback_ms": task.fallback, "grade": grade, "adopted_ms": task.adopted,
        "utility": task.tiers[grade].utility if grade != MISSED else 0,
    }
    row.update({key: getattr(task, key) for key in TASK_FIELDS if key not in row})
    return row


def summarize(sim, rows, scenario, seed, input_hash):
    counts = Counter(row["grade"] for row in rows)
    summary = dict(scenario=scenario.name, seed=seed, input_hash=input_hash, method=sim.method,
                   load=scenario.load, loss=scenario.loss, dip=scenario.dip,
                   deadline_ms=scenario.deadline_ms, released=len(rows))
    summary.update({key: counts[key] for key in (MAIN, LIGHT, LOCAL, MISSED)})
    for key in ("utility", "rounds", "negotiation_ms"):
        summary[f"{key}_sum"] = sum(row[key] for row in rows)
    for key in ("control_bytes", "data_bytes", "air_attempts", "lost_frames", "busy",
                "grant_light", "switch_upload", "switch_edge", "stale_results", "grants",
                "requests", "local_started"):
        summary[key] = sum(row[key] for row in rows)
    summary.update(
        edge_busy_ms=sim.edge_busy_ms, edge_max_queue=sim.max_queue,
        fh_bytes=sim.network.fh_bytes, fh_busy_ms=sim.network.fh_busy_ms,
        fh_max_wait_ms=sim.network.fh_max_wait_ms,
        realized_bad_up=sum(bad for bad, _ in sim.inputs.channel["up"]) / len(sim.inputs.channel["up"]),
        realized_bad_down=sum(bad for bad, _ in sim.inputs.channel["down"]) / len(sim.inputs.channel["down"]),
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, default=HERE / "calibration.json")
    parser.add_argument("--trace", type=Path, default=TRACE)
    parser.add_argument("--probe", action="store_true", help="one seed, one scenario for an engineering check")
    args = parser.parse_args()
    profiles, scale = profiles_from_calibration(args.calibration, NOMINAL_EDGE_MS)
    capacity = read_capacity(args.trace)
    scenarios = (
        (REFERENCE,) if args.probe else tuple(
            Scenario(*values) for values in itertools.product(LOADS, LOSSES, DIPS, DEADLINES)
        )
    )
    seeds = SEEDS[:1] if args.probe else SEEDS
    args.out.mkdir(parents=True, exist_ok=False)
    provenance = {
        "status": "STARTED", "scope": "RDINP-FAST-SLOW-STEP1-DEVELOPMENT",
        "python": sys.version, "seeds": seeds, "duration_ms": DURATION_MS,
        "terminals": TERMINALS, "slots": SLOTS, "methods": METHODS,
        "scenario_grid": [asdict(scenario) for scenario in scenarios],
        "source_sha256": {p.name: sha(p) for p in (HERE / "sim.py", Path(__file__), HERE / "calibrate.py")},
        "trace_sha256": sha(args.trace), "calibration_sha256": sha(args.calibration),
        "trace_period_ms": TRACE_PERIOD_MS, "trace_ms_mbps": capacity,
        "radio_air_mbps": AIR_RATES, "channel_bin_ms": BIN_MS,
        "frame_app_payload_bytes": FRAME_BYTES, "frame_header_bytes": FRAME_HEADER_BYTES,
        "frame_attempts": FRAME_ATTEMPTS, "frame_retry_ms": RTT_RETRY_MS,
        "processing_per_control_response_ms": CONTROL_SERVICE_MS,
        "edge_scale_vs_calibrated_cpu": scale, "nominal_edge_ms": NOMINAL_EDGE_MS,
        "local_fallback_reserve_ms": LOCAL_RESERVE_MS,
        "scenario_reference": asdict(REFERENCE),
        "profiles": {image: {grade: asdict(tier) for grade, tier in tiers.items()}
                     for image, tiers in profiles.items()},
    }
    (args.out / "plan.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    num_rows = 0
    run_csv = args.out / "per_run.csv"
    task_csv = args.out / "per_task.csv.gz"
    with (
        run_csv.open("w", newline="", encoding="utf-8") as run_file,
        gzip.open(task_csv, "wt", compresslevel=3, newline="", encoding="utf-8") as task_file,
    ):
        task_writer = csv.DictWriter(task_file, fieldnames=TASK_FIELDS)
        task_writer.writeheader()
        run_writer = None
        for i, scenario in enumerate(scenarios, 1):
            for seed in seeds:
                inputs = paired_inputs(scenario, seed, capacity, tuple(profiles),
                                       DURATION_MS, TERMINALS, SLOTS)
                # Rotate policy order independently of outcomes.
                shift = seed % len(METHODS)
                for method in METHODS[shift:] + METHODS[:shift]:
                    sim = Simulation(inputs, method, profiles)
                    tasks = sim.run()
                    rows = [task_row(task, scenario, seed, inputs.input_hash, method) for task in tasks]
                    task_writer.writerows(rows)
                    summary = summarize(sim, rows, scenario, seed, inputs.input_hash)
                    if run_writer is None:
                        run_writer = csv.DictWriter(run_file, fieldnames=summary)
                        run_writer.writeheader()
                    run_writer.writerow(summary)
                    num_rows += len(rows)
            if i % 9 == 0 or i == len(scenarios):
                print(f"{i}/{len(scenarios)} configurations; {num_rows} task-method rows", flush=True)
    completion = {
        "status": "COMPLETE", "task_method_rows": num_rows,
        "paired_runs": len(scenarios) * len(seeds), "run_rows": len(scenarios) * len(seeds) * len(METHODS),
        "sha256": {p.name: sha(p) for p in (run_csv, task_csv, args.out / "plan.json")},
    }
    (args.out / "COMPLETE.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()


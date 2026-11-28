"""Isolate admission-time light selection and post-commit switching on the Step 1 workload."""
import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import quantiles

from run import HERE, TRACE, NOMINAL_EDGE_MS, profiles_from_calibration, summarize, task_row
from sim import Scenario, Simulation, paired_inputs, read_capacity

VARIANTS = {
    "Main-Grant-Only": (False, False),
    "Menu-Admission-Only": (True, False),
    "Post-Commit-Switch-Only": (False, True),
    "Structured-RDINP": (True, True),
}
METRICS = {
    "effective_utility": "utility_sum",
    "edge_adopted": "edge_adopted",
    "main_adopted": "high",
    "deadline_missed": "missed",
    "control_bytes": "control_bytes",
    "data_bytes": "data_bytes",
    "rounds": "rounds_sum",
    "negotiation_ms": "negotiation_ms_sum",
}
BOOTSTRAPS = 2000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_ablation(pairs):
    groups = {"all": pairs}
    for deadline_ms in sorted({key[2] for key in pairs}):
        groups[f"{deadline_ms:g}ms"] = {k: v for k, v in pairs.items() if k[2] == deadline_ms}
    comparisons = [
        ("fast_given_menu_admission", {"Structured-RDINP": 1, "Menu-Admission-Only": -1}),
        ("menu_admission_given_fast", {"Structured-RDINP": 1, "Post-Commit-Switch-Only": -1}),
        ("fast_given_main_admission", {"Post-Commit-Switch-Only": 1, "Main-Grant-Only": -1}),
        ("menu_admission_without_fast", {"Menu-Admission-Only": 1, "Main-Grant-Only": -1}),
        ("interaction", {"Structured-RDINP": 1, "Menu-Admission-Only": -1,
                         "Post-Commit-Switch-Only": -1, "Main-Grant-Only": 1}),
    ]
    results = []
    summaries = []
    for label, group in groups.items():
        seeds = sorted({key[1] for key in group})
        seed_pairs = defaultdict(list)
        for (_, seed, _), methods in group.items():
            seed_pairs[seed].append(methods)
        def n_released(pairs):
            return sum(p["Structured-RDINP"]["released"] for p in pairs)
        weights = [n_released(seed_pairs[seed]) for seed in seeds]
        rng = random.Random(20261128)
        samples = [rng.choices(range(len(seeds)), k=len(seeds)) for _ in range(BOOTSTRAPS)]
        for name in VARIANTS:
            totals = [p[name] for p in group.values()]
            n = sum(row["released"] for row in totals)
            summaries.append({
                "cohort": label, "variant": name, "seeds": len(seeds), "pairs": len(totals),
                "released": n,
                **{metric: sum(row[field] for row in totals) / n for metric, field in METRICS.items()},
                **{field: sum(row[field] for row in totals)
                   for field in ("high", "light", "local", "missed", "grant_light", "switch_upload", "switch_edge")},
            })
        for comparison, coefficients in comparisons:
            for metric, field in METRICS.items():
                numerators = [
                    sum(
                        weight * row[name][field]
                        for row in seed_pairs[seed] for name, weight in coefficients.items()
                    )
                    for seed in seeds
                ]
                estimates = [
                    sum(numerators[i] for i in sample) / sum(weights[i] for i in sample)
                    for sample in samples
                ]
                percentiles = quantiles(estimates, n=40, method="inclusive")
                results.append({
                    "cohort": label, "contrast": comparison, "metric": metric,
                    "seeds": len(seeds), "pairs": len(group), "released": sum(weights),
                    "difference": sum(numerators) / sum(weights),
                    "ci95_low": percentiles[0], "ci95_high": percentiles[-1],
                })
    return summaries, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="directory of the completed Step 1 four-method run")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plan_path = args.reference / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    receipt = json.loads((args.reference / "COMPLETE.json").read_text(encoding="utf-8"))
    for path in (plan_path, args.reference / "per_run.csv"):
        if sha(path) != receipt["sha256"][path.name]:
            raise ValueError(f"reference integrity mismatch: {path}")
    with (args.reference / "per_run.csv").open(newline="", encoding="utf-8") as handle:
        reference = {
            (row["scenario"], int(row["seed"])): row
            for row in csv.DictReader(handle) if row["method"] == "Structured-RDINP"
        }

    calibration = HERE / "calibration.json"
    if sha(calibration) != plan["calibration_sha256"]:
        raise ValueError("calibration changed")
    if sha(TRACE) != plan["trace_sha256"]:
        raise ValueError("trace changed")
    capacity = read_capacity(TRACE)
    profiles, _ = profiles_from_calibration(calibration, NOMINAL_EDGE_MS)

    args.out.mkdir(parents=True, exist_ok=False)
    configuration = {
        "scope": "step1 mechanism attribution on prior development inputs",
        "reference_plan_sha256": sha(plan_path),
        "reference_run_sha256": sha(args.reference / "per_run.csv"),
        "sim_sha256": sha(HERE / "sim.py"), "script_sha256": sha(Path(__file__)),
        "variants": {key: {"menu_admission": value[0], "fast_switch": value[1]}
                     for key, value in VARIANTS.items()},
        "same_message_formats_and_sizes": True,
        "causal_resource_view": plan.get("causal_resource_view", False),
        "exploratory_using_prior_scenarios": True,
        "grouping": ["all", "400ms", "600ms", "800ms"],
    }
    (args.out / "plan.json").write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
    pairs = {}
    for i, settings in enumerate(plan["scenario_grid"], start=1):
        scenario = Scenario(**settings)
        for seed in plan["seeds"]:
            inputs = paired_inputs(scenario, seed, capacity, tuple(profiles), plan["duration_ms"],
                                   plan["terminals"], plan["slots"])
            old = reference[scenario.name, seed]
            if old["input_hash"] != inputs.input_hash:
                raise AssertionError(f"input changed: {scenario.name}, {seed}")
            variants = {}
            for name, (menu, fast) in VARIANTS.items():
                sim = Simulation(inputs, "Structured-RDINP", profiles,
                                 menu_admission=menu, fast_switch=fast,
                                 causal_resource_view=configuration["causal_resource_view"])
                tasks = sim.run()
                rows = [task_row(task, scenario, seed, inputs.input_hash, sim.method) for task in tasks]
                row = summarize(sim, rows, scenario, seed, inputs.input_hash)
                if configuration["causal_resource_view"]:
                    row["cached_dispatches"] = sim.cached_dispatches
                if name == "Structured-RDINP" and {k: str(v) for k, v in row.items()} != old:
                    raise AssertionError(f"full Structured-RDINP did not reproduce: {scenario.name}, {seed}")
                if (not menu and row["grant_light"]) or (not fast and (row["switch_upload"] or row["switch_edge"])):
                    raise AssertionError("disabled path executed")
                if row["requests"] != row["released"]:
                    raise AssertionError("unexpected additional request")
                variants[name] = {**row, "method": name, "edge_adopted": row["high"] + row["light"]}
            pairs[scenario.name, seed, scenario.deadline_ms] = variants
        if i % 9 == 0 or i == len(plan["scenario_grid"]):
            print(f"{i}/{len(plan['scenario_grid'])} scenarios", flush=True)
    if len(pairs) != len(reference) or len(pairs) != receipt["paired_runs"]:
        raise AssertionError("incomplete pairing")
    rows = [row for block in pairs.values() for row in block.values()]
    summary, contrasts = summarize_ablation(pairs)
    write_csv(args.out / "per_run.csv", rows)
    write_csv(args.out / "summary.csv", summary)
    write_csv(args.out / "contrasts.csv", contrasts)
    complete = {
        "pairs": len(pairs), "method_runs": len(rows),
        "structured_exact_replay": len(pairs),
        "released_per_variant": sum(row["released"] for row in rows if row["method"] == "Structured-RDINP"),
        "sha256": {name: sha(args.out / name)
                   for name in ("per_run.csv", "summary.csv", "contrasts.csv", "plan.json")},
    }
    (args.out / "COMPLETE.json").write_text(json.dumps(complete, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

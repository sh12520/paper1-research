"""Run the fixed, three-arm 16-seed RDINP loopback expansion."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.metadata
import itertools
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import time
from unittest.mock import patch

import check_protocol
import run_pairs as original
from permit_guarded import EXTRA_TAIL_NS, protected_budget

HERE = Path(__file__).resolve().parent
PLAN_RULES = HERE / "EXPANSION_PLAN.md"
SEEDS = tuple(range(100, 116))
METHODS = ("Structured-RDINP", "Reactive-ReNeg", "Same-Permit-No-Switch")
STYLES = dict(zip(METHODS, ("auto", "offer", "none")))
LOGS = ("authority-audit.json", "tasks.json", "wire.jsonl.gz", "rpc.jsonl.gz")
EXECUTE_TASK = original.execute_task


class ObservedLock:
    """Record local fallback timing while using the original per-terminal lock."""
    def __init__(self, shared_lock):
        self.shared_lock = shared_lock
        self.request_ns = None
        self.acquire_ns = None

    def __enter__(self):
        self.request_ns = time.perf_counter_ns()
        self.shared_lock.acquire()
        self.acquire_ns = time.perf_counter_ns()

    def __exit__(self, *_):
        self.shared_lock.release()


def execute_observed(job, session, link, assets, references, lock, remotes, style, forced):
    observed = ObservedLock(lock)
    row, future = EXECUTE_TASK(job, session, link, assets, references, observed, remotes, style, forced)
    row["local_lock_request_ns"] = observed.request_ns
    row["local_compute_start_ns"] = observed.acquire_ns
    return row, future


def start_server(config, port):
    if port.exists():
        raise FileExistsError(port)
    interpreter = [sys.executable]
    env = os.environ.copy()
    if os.name == "nt" and sys.prefix != sys.base_prefix:
        interpreter = [sys._base_executable, "-S"]
        libraries = dict.fromkeys(sysconfig.get_path(kind) for kind in ("purelib", "platlib"))
        env["PYTHONPATH"] = os.pathsep.join(libraries)
    script = original.PERMIT / "permit_guarded.py"
    with port.with_suffix(".server.log").open("x", encoding="utf-8") as log:
        return subprocess.Popen(
            [*interpreter, "-B", str(script), str(config.resolve()), str(port.resolve())],
            stdout=log, stderr=subprocess.STDOUT, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def sources():
    files = (Path(__file__), PLAN_RULES, original.PERMIT / "permit_guarded.py",
             HERE / "check_protocol.py", HERE / "gate.py")
    return {
        **original.sources(),
        **{p.relative_to(original.RDINP).as_posix(): original.sha(p.read_bytes()) for p in files},
    }


def scheduled_cases():
    cases = []
    orderings = tuple(itertools.permutations(METHODS))
    trace_orders = tuple(itertools.permutations(original.TRACE))
    for index, seed in enumerate(SEEDS):
        for condition in trace_orders[index % len(trace_orders)]:
            cases.append({
                "condition": condition, "seed": seed,
                "method_order": list(orderings[(index + tuple(original.TRACE).index(condition)) % len(orderings)]),
                "tasks": [asdict(task) for task in original.shared_task_plan(seed)],
            })
    return cases


def check_guard():
    budgets = {"main": 40_000_000, "light": 25_000_000}
    for start, target, style, guarded in (
        ("main", "main", "auto", True), ("main", "main", "offer", True),
        ("main", "main", "none", False), ("main", "light", "auto", True),
        ("light", "light", "auto", False), ("light", "light", "offer", False),
    ):
        request = {"input_tier": start, "accepted_tier": target, "post_upload": style,
                   "tail_budget_ns": budgets}
        expected = budgets["light"] + (EXTRA_TAIL_NS if guarded else 0)
        observed = protected_budget(request)["tail_budget_ns"]
        if observed != {"main": budgets["main"], "light": expected} or budgets["light"] != 25_000_000:
            raise RuntimeError(f"invalid tail guard: {(start, target, style)}")


def calibration(output, assets, reference_values):
    tests = []
    for tier in ("light", "main"):
        jobs = [original.Task(f"headroom-{i}", i * 410, 0, i // 2, name)
                for i, name in enumerate(original.IMAGES * 3)]
        result = original.execute_arm(output / f"headroom-{tier}", "headroom", jobs,
                                      original.TRACE["half"], assets, reference_values, "auto", forced=tier)
        durations = [
            row["end_to_end_ms"] if row["grade"] == "light" else original.DEADLINE_MS
            for row in result["tasks"]
        ]
        tests.append({
            "input_tier": tier,
            "light_adopted": sum(row["grade"] == "light" for row in result["tasks"]),
            "measured_headroom_p95_ms": (original.DEADLINE_MS - original.FALLBACK_RESERVE_MS
                                         - original.quantile(durations, .95)),
            "n": len(jobs),
        })
    original.record_json(output / "headroom.json", tests)


def run(output, asset_dir):
    check_guard()
    assets = original.load_assets(asset_dir)
    references = {
        name: original.edge_values(original.detect_edges(original.transport_input(src, 512), 512))
        for name, src in assets.items()
    }
    cases = scheduled_cases()
    output.mkdir(parents=True, exist_ok=False)
    plan = {
        "phase": "independent 16-seed engineering expansion",
        "deadline_ms": original.DEADLINE_MS, "fallback_reserve_ms": original.FALLBACK_RESERVE_MS,
        "slots": original.SLOT_COUNT, "permit_ttl_ms": original.PERMIT_TTL_MS,
        "trace": original.TRACE, "seeds": SEEDS, "methods": METHODS, "styles": STYLES,
        "post_upload_light_extra_tail_ns": EXTRA_TAIL_NS,
        "snapshot_max_age_ns": original.SNAPSHOT_MAX_AGE_NS,
        "python": platform.python_version(), "host": platform.platform(),
        "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "asset_sha256": {name: original.sha(src) for name, src in assets.items()},
        "source_sha256": sources(), "cases": cases,
    }
    original.record_json(output / "plan.json", plan)
    with patch.object(check_protocol, "start_server", start_server):
        if not check_protocol.run(output / "safety"):
            raise RuntimeError("guarded authority failed the safety matrix before scoring")
    tasks, arms = [], []
    sealed = ["plan.json", "safety/safety.json", "headroom.json", "per_task.csv", "per_arm.csv"]
    with (patch.object(original, "start_server", start_server),
          patch.object(original, "execute_task", execute_observed)):
        calibration(output, assets, references)
        for tier in ("light", "main"):
            sealed.extend(f"headroom-{tier}/{name}" for name in LOGS)
        for index, case in enumerate(cases, 1):
            condition, seed = case["condition"], case["seed"]
            jobs = [original.Task(**record) for record in case["tasks"]]
            directory = output / f"pair-{condition}-{seed}"
            directory.mkdir()
            for method in case["method_order"]:
                style = STYLES[method]
                result = original.execute_arm(directory/method, method, jobs, original.TRACE[condition],
                                              assets, references, style)
                arms.append({
                    "condition": condition, "seed": seed, "style": style,
                    **{k: v for k, v in result.items() if k not in ("tasks", "audit")},
                    "audit_effects": result["audit"]["effects"], "audit_starts": result["audit"]["starts"],
                })
                tasks.extend({"condition": condition, "seed": seed, "method": method, **row}
                             for row in result["tasks"])
                sealed.extend(f"{directory.name}/{method}/{name}" for name in LOGS)
            print(f"Completed {index}/{len(cases)}: {condition}/{seed}", flush=True)
    if sources() != plan["source_sha256"]:
        raise RuntimeError("source changed during the expansion")
    original.write_table(output / "per_task.csv", tasks)
    original.write_table(output / "per_arm.csv", arms)
    original.record_json(output / "COMPLETE.json", {
        "pair_count": len(cases), "method_runs": len(arms), "task_rows": len(tasks),
        "sha256": {name: original.sha((output/name).read_bytes()) for name in sealed},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.assets)


if __name__ == "__main__":
    main()

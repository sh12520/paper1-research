"""Paired, development-only comparison of public contract streams."""

from collections import Counter
from hashlib import file_digest, sha256
from math import inf, nextafter
from pathlib import Path
from time import perf_counter, sleep
import argparse
import csv
import gc
import json
import os
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "results"
sys.path[:0] = [str(p) for p in (ROOT, ARCHIVE / "depth3", ARCHIVE / "grammar_gate",
                                ARCHIVE / "grammar_dedup", ARCHIVE / "method_dev_v1")]

import numpy as np
from audit_common import read_json, sealed_payloads
from certificate_report import validate_cut
from depth_search import DepthCursor
from grammar_search import Entry, Limits, SearchLimit
from run_depth3 import select_slots
from run_search import MemoryProbe, atomic_json
from runtime import verification_public
from src.instances import deserialize_instance
from tools.smoke_01 import memory_status, process_memory
import protocol_adapter

CURRENT = "CURRENT_ON_DEMAND_GRAMMAR_SEARCH"
GENERIC = "GENERIC_ABSTRACT_BEST_FIRST"
ABLATIONS = ("NO_EARLY_SEMANTIC_DEDUP", "GENERIC_BOUND_ONLY", "DEFER_CAPABILITY_PRUNING",
             "WEAK_STATE_TIME_RESOURCE_ENVELOPE", "NO_LAZY_STOP", "NO_SEARCH_TIME_DOMAIN_NORMALIZATION")
GRAPH_METHODS = ("FULL_FLAT", "GENERIC_INDEX", "CONTRACT_AWARE_INDEX")
METHODS = (CURRENT, GENERIC, *ABLATIONS, *GRAPH_METHODS)
KS = {1: (10, 50, 100, 500), 2: (10, 50, 100, 500), 3: (10, 100, 500)}
LIMITS = {1: Limits(12.0, 300_000, 180_000), 2: Limits(12.0, 300_000, 180_000),
          3: Limits(45.0, 2_000_000, 260_000)}
MIB = 1 << 20
RSS_LIMIT = 2048 * MIB
PRELAUNCH_MEMORY = 1280 * MIB
PROBE = MemoryProbe(RSS_LIMIT)
FULL = "EXACT_TOPK_FULL_LENGTH"
SHORT = "EXACT_DOMAIN_EXHAUSTED_SHORT"
CAPPED = "NOT_CERTIFIED_WITHIN_BUDGET"
UNSOUND = "UNSOUND"


def hash_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def fixture_path(instance_id):
    return ARCHIVE / "pilot" / "instances" / (instance_id + ".json")


def require_safe_scope():
    auth = read_json(ROOT / "PILOT_AUTHORIZATION_STATE.json")
    if auth["namespace_authorizations"]["CONFIRM"]["allowed"] is not False:
        raise ValueError("CONFIRM authorization must stay closed")
    if (ROOT / "FROZEN_CONFIG.yaml").exists():
        raise ValueError("Unexpected FROZEN_CONFIG")


def scope():
    d2 = [(slot["instance_id"], slot["configuration"]["composition_depth"])
          for slot in select_slots("regression")]
    d3 = [(slot["instance_id"], 3) for slot in select_slots("development")]
    # Alternate original-depth and derived-depth work. Rotate methods per query.
    cells = []
    for index in range(len(d2)):
        cells.append(d2[index])
        if index % 4 == 3:
            cells.append(d3[index // 4])
    return cells


def capture_prefix(cursor_factory, depth, no_lazy_stop=False):
    """Record the original proof point and any post-proof work separately."""
    gc.collect()
    baseline_rss = PROBE()
    started = perf_counter()
    deadline = started + LIMITS[depth].wall_seconds
    entries, cuts = [], {}
    hasher = sha256()
    cursor = None
    limit_reason, error = None, None

    def checkpoint(k, exhausted):
        metrics = cursor.metrics()
        boundary = entries[-1] if entries else None
        cut = {
            "status": "EXACT_TOPK_CERTIFIED", "returned": len(entries),
            "boundary_score": boundary.score if boundary else None,
            "boundary_key": boundary.key.hex() if boundary else None,
            "frontier_min_lb": metrics["frontier_min_lb"],
            "frontier_remaining": metrics["frontier_remaining"],
            "buffered_best_score": metrics["buffered_best_score"],
            "buffered_best_key": metrics["buffered_best_key"],
            "full_domain_exhausted": exhausted,
            "elapsed_s": perf_counter() - started, "prefix_sha256": hasher.hexdigest(),
            "metrics": metrics,
        }
        checked = cut
        tie_key = metrics.get("frontier_min_key")
        if (boundary is not None and cut["frontier_remaining"] and
                cut["frontier_min_lb"] == boundary.score and tie_key is not None and
                bytes.fromhex(tie_key) > boundary.key):
            # The archived checker only handles scalar bounds. A graph index
            # can additionally prove a strict lexicographic cutoff at a tie.
            successor = nextafter(boundary.score, inf)
            checked = dict(cut, frontier_min_lb=successor, metrics=dict(metrics, frontier_min_lb=successor))
            cut["frontier_min_key"] = tie_key
        valid, reason = validate_cut(checked, k, [(x.score, x.key) for x in entries])
        if valid != "EXACT_TOPK_CERTIFIED":
            raise AssertionError(reason)
        cut["status"] = SHORT if exhausted and len(entries) < k else FULL
        cuts[k] = cut

    try:
        cursor = cursor_factory(deadline)
        for k in KS[depth]:
            while len(entries) < k:
                entry = cursor.next_contract()
                if entry is None:
                    if not cursor.exhausted:
                        raise AssertionError("silently stopped with an open domain")
                    break
                if entries and (entry.score, entry.key) <= (entries[-1].score, entries[-1].key):
                    raise AssertionError("public order violation")
                hasher.update(struct.pack(">d", entry.score) + entry.key)
                entries.append(entry)
            checkpoint(k, cursor.exhausted)
        if no_lazy_stop:
            while cursor.next_contract() is not None:
                pass
            if not cursor.exhausted:
                raise AssertionError("exhaustive delivery stopped with a pending domain")
    except SearchLimit as exc:
        limit_reason = str(exc)
    except (AssertionError, ValueError) as exc:
        error = str(exc) or type(exc).__name__

    elapsed = perf_counter() - started
    metrics = cursor.metrics() if cursor else {}
    final_rss, lifetime_peak = process_memory(os.getpid())
    sample_peak = max(baseline_rss, final_rss, metrics.get("peak_working_set_bytes", 0))
    if limit_reason is None and error is None and elapsed > LIMITS[depth].wall_seconds:
        # Some NumPy kernels are noninterruptible. Do not credit a late proof.
        limit_reason = "wall_time_limit_after_noninterruptible_call"
    for k in KS[depth]:
        if error or k not in cuts or cuts[k]["elapsed_s"] > LIMITS[depth].wall_seconds:
            cuts[k] = {"status": UNSOUND if error else CAPPED, "returned": min(k, len(entries)),
                       "elapsed_s": elapsed, "metrics": metrics,
                       "reason": error or limit_reason, "prefix_sha256": None}
    max_k = max(KS[depth])
    completion = cuts[max_k]["status"]
    delivery = CAPPED if no_lazy_stop and limit_reason and not error else completion
    return [] if error else entries, {
        "cuts": cuts, "elapsed_s": elapsed, "baseline_rss_bytes": baseline_rss,
        "query_sampled_peak_rss_bytes": sample_peak, "process_lifetime_peak_rss_bytes": lifetime_peak,
        "min_sampled_available_mib_at_boundary": memory_status()[1] / MIB,
        "limit_reason": error or limit_reason, "delivery_status": delivery, "metrics": metrics,
        "exhausted_after_work": bool(cursor and cursor.exhausted),
    }


class PrefixUnavailable(RuntimeError):
    pass


class PrefixReplay:
    def __init__(self, entries, exhausted):
        self.entries = iter(entries)
        self.exhausted = exhausted

    def next_contract(self):
        entry = next(self.entries, None)
        if entry is None and not self.exhausted:
            raise PrefixUnavailable("The next structural candidate was not certified in this replay.")
        return entry


def replay(entries, exhausted, public, instance, depth):
    """Use the existing batched protocol without inventing domain exhaustion."""
    budgets = (100, 500, 1000, 5000)
    candidates = len(entries)
    attempted = [budgets]
    supported = tuple(b for b in budgets if b <= candidates + 27)
    if supported and supported != budgets:
        attempted.append(supported)
    start = perf_counter()
    for prefix in attempted:
        try:
            out, history, _ = protocol_adapter.run_protocol(
                PrefixReplay(entries, exhausted), public, instance.private, max_depth=depth, budgets=prefix)
        except PrefixUnavailable:
            continue
        protocol_adapter.reference_utilities(out, instance, depth)
        return {"status": "COMPLETE" if prefix == budgets else "PARTIAL_PREFIX",
                "budget_max": prefix[-1], "outcomes": out, "history": history,
                "elapsed_s": perf_counter() - start}
    return {"status": "INSUFFICIENT_PREFIX", "budget_max": 0, "outcomes": {},
            "history": [], "elapsed_s": perf_counter() - start}


def research_protocol(record):
    fields = {k: v for k, v in record.items() if k != "elapsed_s"}
    # The worker transport stringifies budget keys in JSON. Normalize that
    # transport detail without rounding utilities or removing history.
    fields["outcomes"] = {str(k): value for k, value in fields["outcomes"].items()}
    return json.dumps(fields, sort_keys=True, allow_nan=False)


def guard_factory():
    path = ARCHIVE / "grammar_gate" / "guard.py"
    source = path.read_text(encoding="utf-8")
    old = "scope = root/'results'/'grammar_gate'"
    if source.count(old) != 1:
        raise ValueError("Archived guard changed")
    from types import ModuleType
    guard = ModuleType("paper_online_guard")
    guard.__file__ = str(path)
    sys.modules[guard.__name__] = guard
    exec(compile(source.replace(old, "scope = root/'results'/'paper_method_dev'"),
                 str(path), "exec"), guard.__dict__)
    return guard.graph_guard


def new_cursor(method, public, depth, deadline, controls=None):
    args = public, depth, LIMITS[depth], PROBE
    if method == CURRENT or method == "NO_LAZY_STOP":
        return DepthCursor(*args, deadline=deadline)
    if method == GENERIC:
        from generic_search import GenericCursor
        return GenericCursor(*args, deadline=deadline)
    if method in GRAPH_METHODS:
        return controls.make_cursor(method, *args, deadline=deadline)
    from ablations import make_ablated
    return make_ablated(method, *args, deadline=deadline)


def run_worker(lane):
    require_safe_scope()
    allowed = frozenset(scope())
    manifest = read_json(ARCHIVE / "pilot" / "instances_manifest.json")
    if lane == "graph":
        from index_controls import IndexControls
        started = perf_counter()
        first = fixture_path(select_slots("regression")[0]["instance_id"])
        controls = IndexControls(verification_public(deserialize_instance(first.read_text(encoding="utf-8")).public))
        load = {"combined_load_s": perf_counter() - started, "rss_bytes": PROBE(),
                "lifetime_peak_rss_bytes": process_memory(os.getpid())[1], **controls.load_metrics}
        from contextlib import nullcontext
        guard = nullcontext(None)
    else:
        import ablations  # preload code before restricting workspace input
        import generic_search
        controls, load = None, {}
        worker_output = HERE / "synth_work"
        worker_output.mkdir(exist_ok=True)
        guard = guard_factory()(ROOT, allowed_inputs=[fixture_path(i) for i, _ in allowed],
                                output_dir=worker_output)

    with guard as access:
        print(json.dumps({"ready": lane, "load": load}), flush=True)
        for line in sys.stdin:
            command = json.loads(line)
            instance_id, depth, method = command["id"], command["depth"], command["method"]
            if (instance_id, depth) not in allowed or (lane == "graph") != (method in GRAPH_METHODS):
                raise ValueError("Out-of-scope development request")
            if method not in METHODS or (depth == 3 and lane == "graph"):
                raise ValueError("Unsupported method/depth pair")
            raw = fixture_path(instance_id).read_bytes()
            instance = deserialize_instance(raw.decode("utf-8"))
            if sha256(raw).hexdigest() != manifest[instance_id]["sha256"]:
                raise ValueError("Existing serialized instance no longer matches manifest")
            public = verification_public(instance.public)

            def factory(deadline):
                return new_cursor(method, public, depth, deadline, controls)

            entries, result = capture_prefix(factory, depth, method == "NO_LAZY_STOP")
            # A capped search must never simulate domain exhaustion in bilateral replay.
            exhausted = any(c["status"] == SHORT for c in result["cuts"].values())
            result["protocol"] = replay(entries, exhausted, public, instance, depth)
            result.update(method=method, instance_id=instance_id, effective_depth=depth,
                          instance_hash=instance.instance_hash, namespace=instance.namespace,
                          configuration=instance.public.configuration, family=instance.public.family,
                          public_hash=instance.public_hash, worker_pid=os.getpid(),
                          memory_available_mib=memory_status()[1] / MIB,
                          snapshot=access.snapshot() if access else None)
            if controls is not None and method == "FULL_FLAT":
                result["conditioned_candidate_count"] = controls.conditioned_count(public, depth)
            result["prefix"] = [(x.key.hex(), x.score, x.witness) for x in entries]
            print(json.dumps(result, allow_nan=False, separators=(",", ":")), flush=True)


class Worker:
    def __init__(self, lane):
        self.process = subprocess.Popen(
            [sys.executable, "-B", str(__file__), "--worker", lane],
            cwd=ROOT, text=True, encoding="utf-8", stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "OPENBLAS_NUM_THREADS": "1",
                 "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        self.ready = self.receive()
        if self.ready.get("ready") != lane:
            raise RuntimeError("Worker startup handshake failed")

    def receive(self):
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"Worker stopped unexpectedly: pid={self.process.pid}, exit={self.process.poll()}")
        return json.loads(line)

    def send(self, instance_id, depth, method):
        self.process.stdin.write(json.dumps({"id": instance_id, "depth": depth, "method": method}) + "\n")
        self.process.stdin.flush()
        return self.receive()

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=15)
        self.process.stdout.close()


def comparable_prefix(result, expected):
    actual = result.pop("prefix")
    want = expected["topk"][:len(actual)]
    if len(actual) != len(want):
        return False, "emitted beyond the sealed reference length"
    witness_hash = sha256()
    for rank, ((key, score, witness), prior) in enumerate(zip(actual, want), 1):
        if (key != prior["key"] or struct.pack(">d", score) != struct.pack(">d", prior["score"])
                or witness != prior["witness"]):
            return False, f"signature/score/witness mismatch at rank {rank}"
        witness_hash.update(witness.encode("utf-8") + b"\n")
    result["observed_prefix_count"] = len(actual)
    result["observed_witness_sha256"] = witness_hash.hexdigest()
    for k, cut in result["cuts"].items():
        if cut["status"] in (FULL, SHORT):
            prior = expected["k_certificates"][str(k)]
            if (cut["returned"], cut["prefix_sha256"]) != (prior["returned"], prior["prefix_sha256"]):
                return False, f"certificate coverage mismatch at K={k}"
    return True, ""


def declare_plan(references):
    row_scope = scope()
    sources = [HERE / name for name in ("run_comparison.py", "check_reduced.py", "generic_search.py",
                                      "ablations.py", "index_controls.py")]
    fixed = {i for i, d in row_scope if d < 3}
    count_file = ARCHIVE / "flat_audit" / "per_instance.csv"
    with count_file.open(encoding="utf-8-sig", newline="") as stream:
        public_counts = {row["instance_id"]: int(row["conditioned_structural_method_eligible"])
                         for row in csv.DictReader(stream) if row["instance_id"] in fixed}
    if set(public_counts) != fixed:
        raise ValueError("Archived public counts do not cover the fixed 96 queries")
    reduced = read_json(HERE / "reduced_correctness.json")
    if reduced["status"] != "PASS" or set(reduced["pass_by_method"]) != {CURRENT, GENERIC, *ABLATIONS}:
        raise ValueError("All online methods must pass the independent reduced-domain test")
    for name, expected in reduced["method_sources"].items():
        if hash_file(HERE / name) != expected:
            raise ValueError(f"Reduced evidence no longer binds {name}")
    return {
        "stage": "PAPER-BASELINE-ABLATION-01",
        "query_order": row_scope,
        "method_orders": {str(depth): [m for m in METHODS if depth < 3 or m not in GRAPH_METHODS]
                          for depth in KS},
        "rotation": "rotate allowed method order by planned query index modulo method count",
        "high_cost_rule": "at least 100000 public-conditioned structural candidates within fixed original-depth grid",
        "public_conditioned_counts": public_counts,
        "public_count_source_sha256": hash_file(count_file),
        "high_cost_ids": sorted(i for i, n in public_counts.items() if n >= 100_000),
        "limits": {str(d): {"wall_s": l.wall_seconds, "expansions": l.expanded, "frontier": l.frontier}
                   for d, l in LIMITS.items()},
        "worker_rss_mib": RSS_LIMIT // MIB, "prelaunch_mib": PRELAUNCH_MEMORY // MIB,
        "emergency_mib": 768,
        "sources": {p.name: hash_file(p) for p in sources},
        "reduced_evidence_sha256": hash_file(HERE / "reduced_correctness.json"),
        "oracle_seals": references, "python": sys.version, "numpy": np.__version__,
    }


def controller():
    require_safe_scope()
    if memory_status()[1] < PRELAUNCH_MEMORY:
        raise RuntimeError("PAUSED_MEMORY: prelaunch floor 1280 MiB")
    reference = {}
    seals = {}
    for phase in ("regression", "development"):
        _, reference[phase], seals[phase] = sealed_payloads(ARCHIVE / "depth3" / phase / "search_seal.json")
    plan = declare_plan(seals)
    plan_file = HERE / "development_plan.json"
    if plan_file.exists() and read_json(plan_file) != json.loads(json.dumps(plan)):
        raise ValueError("Existing plan is bound to different source or comparison settings")
    if not plan_file.exists():
        atomic_json(plan_file, plan)
    runs = HERE / "attempts"
    runs.mkdir(exist_ok=True)
    stop_methods = set()
    workers = {}
    planned = 96 * len(METHODS) + 24 * (len(METHODS) - len(GRAPH_METHODS))
    done = 0
    try:
        workers["synth"] = Worker("synth")
        workers["graph"] = Worker("graph")
        stamp = HERE / "worker_startup.json"
        if not stamp.exists():
            atomic_json(stamp, {lane: w.ready for lane, w in workers.items()})
        for query_index, (instance_id, depth) in enumerate(scope()):
            phase = "development" if depth == 3 else "regression"
            expected = reference[phase][instance_id]
            protocol_refs = {}
            methods = plan["method_orders"][str(depth)]
            offset = query_index % len(methods)
            for method in methods[offset:] + methods[:offset]:
                path = runs / f"{depth}__{instance_id}__{method}.json"
                if path.exists():
                    row = read_json(path)
                    if row.get("correctness") == UNSOUND:
                        stop_methods.add(method)
                    done += 1
                    continue
                if method in stop_methods:
                    atomic_json(path, {"method": method, "instance_id": instance_id, "effective_depth": depth,
                                       "correctness": "STOPPED_AFTER_UNSOUND"})
                    done += 1
                    continue
                while memory_status()[1] < PRELAUNCH_MEMORY:
                    print("PAUSED_MEMORY before next attempt; retaining prior results", flush=True)
                    sleep(15)
                row = workers["graph" if method in GRAPH_METHODS else "synth"].send(instance_id, depth, method)
                if row["instance_hash"] != expected["instance_hash"]:
                    raise ValueError("Unpaired serialized instance")
                equal, reason = comparable_prefix(row, expected)
                unsafe = not equal or any(c["status"] == UNSOUND for c in row["cuts"].values())
                if method == "FULL_FLAT" and row.get("conditioned_candidate_count") != plan["public_conditioned_counts"][instance_id]:
                    unsafe = True
                    reason = "FLAT public-conditioned count differs from the independent archived count"
                if not unsafe:
                    n = row["observed_prefix_count"]
                    exhausted = any(c["status"] == SHORT for c in row["cuts"].values())
                    protocol_id = (n, exhausted)
                    if protocol_id not in protocol_refs:
                        instance = deserialize_instance(fixture_path(instance_id).read_text(encoding="utf-8"))
                        entries = [Entry(bytes.fromhex(x["key"]), x["score"], x["witness"], x["witness"])
                                   for x in expected["topk"][:n]]
                        protocol_refs[protocol_id] = research_protocol(
                            replay(entries, exhausted, verification_public(instance.public), instance, depth))
                    unsafe = research_protocol(row["protocol"]) != protocol_refs[protocol_id]
                    if unsafe:
                        reason = "Same exact input prefix had unequal bilateral outcomes or history"
                    row["protocol_prefix_match"] = not unsafe
                row["correctness"] = UNSOUND if unsafe else "CONSISTENT_WITH_SEALED_REFERENCE"
                if unsafe:
                    row["unsound_reason"] = reason or row["limit_reason"]
                    stop_methods.add(method)
                atomic_json(path, row)
                done += 1
                status = row["cuts"]["500"]["status"] if not unsafe else UNSOUND
                if done % 12 == 0 or unsafe:
                    print(f"{done}/{planned} d{depth} {instance_id} {method} {status} {row['elapsed_s']:.3f}s",
                          flush=True)
    finally:
        for worker in workers.values():
            worker.close()
    if done != planned:
        raise RuntimeError(f"Coverage {done}/{planned}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("graph", "synth"))
    args = parser.parse_args()
    if args.worker:
        run_worker(args.worker)
    else:
        controller()

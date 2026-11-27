"""One fresh child per primary method on a fixed existing development query."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from time import perf_counter, sleep
from types import FunctionType, SimpleNamespace


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "results"
SCRIPT = Path(__file__).resolve()
sys.path[:0] = [str(p) for p in (
    ROOT, ARCHIVE / "depth3", ARCHIVE / "grammar_gate", ARCHIVE / "grammar_dedup",
    ARCHIVE / "method_dev_v1", ARCHIVE / "index_gate",
)]
MIB = 1 << 20
FIXTURE = "F1__low__medium__sparse__d1__s0"
METHODS = ("FULL_FLAT", "GENERIC_ABSTRACT_BEST_FIRST", "CONTRACT_AWARE_INDEX",
           "CURRENT_ON_DEMAND_GRAMMAR_SEARCH", "GENERIC_INDEX")
GRAPH_METHODS = {"FULL_FLAT", "GENERIC_INDEX", "CONTRACT_AWARE_INDEX"}
TREE_NAMES = {"GENERIC_INDEX": "generic", "CONTRACT_AWARE_INDEX": "contract"}
SOFT_QUERY_SECONDS = 12
HARD_CHILD_SECONDS = 90


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frozen_public():
    from certificate_report import public_input
    from runtime import verification_public
    original = read(ARCHIVE / "pilot" / "instances_manifest.json")
    return verification_public(public_input(FIXTURE, original)[0])


def build_graph_lane(method, public):
    from index_controls import IndexControls
    from index_tree import (DEFAULT_PATH, INDEX_VERSION, SHARED_FIELDS, TREE_FIELDS,
                            BoundingTree, Index, PublicBasis, read_arrays, source_hashes)
    from src.fast_exact import FastLibrary

    library = FastLibrary.from_graph(scope="pilot-execution")
    started = perf_counter()
    library.bind_public_basis(public)
    phase = dict(library.load_timings, public_basis_bind_s=perf_counter() - started)
    if method == "FULL_FLAT":
        return library, phase

    started = perf_counter()
    data = read(DEFAULT_PATH / "manifest.json")
    if (data["version"] != INDEX_VERSION or data["source_sha256"] != source_hashes(library)
            or data["class_count"] != len(library.keys)):
        raise ValueError("archived index and verified graph mismatch")
    phase["index_manifest_validation_s"] = perf_counter() - started
    name = TREE_NAMES[method]
    started = perf_counter()
    features = read_arrays(DEFAULT_PATH / "shared", data["features"], SHARED_FIELDS)
    phase["shared_features_load_s"] = perf_counter() - started
    started = perf_counter()
    tree = BoundingTree(read_arrays(DEFAULT_PATH / name, data["tree_arrays"][name], TREE_FIELDS))
    phase[name + "_tree_load_s"] = perf_counter() - started
    # Bind one tree to the original read-only Index public API. The other
    # tree is absent from this isolated cold-working-set measurement.
    index = Index.__new__(Index)
    index.__dict__.update(features)
    index.basis = PublicBasis.frozen()
    index.counts = data["counts"]
    index.trees = {name: tree}
    controls = IndexControls.__new__(IndexControls)
    controls.index = index
    controls.library = library
    return controls, phase


def direct_flat_prefix(library, public, size):
    import public_search
    from grammar_search import Entry, decode_witness
    from index_controls import _RankObservation
    from index_tree import PublicBasis
    from runtime import choose_variant
    from src.enumeration import syntax_key
    from src.state_machine import normalize

    view = public_search.sanitize_public(SimpleNamespace(
        **vars(public), configuration={"composition_depth": 1},
    ))
    PublicBasis.frozen().validate_view(view)
    variant = choose_variant(public, library)
    observer = _RankObservation()
    archived = public_search.make_plan
    make_plan = FunctionType(archived.__code__, dict(vars(public_search), np=observer),
                             archived.__name__, archived.__defaults__)
    plan = make_plan(view, library, variant, 0, "FLAT-FEASIBILITY", budget=5000)
    if observer.scores is None or plan.public_ranked_count != len(observer.scores):
        raise AssertionError("FLAT ranked score observation incomplete")
    for i, class_id in enumerate(plan.order[:size]):
        raw = variant.witness(int(class_id), 1)
        witness = syntax_key(normalize(decode_witness(raw), public))
        yield Entry(library.keys[int(class_id)].tobytes(), float(observer.scores[i]), raw, witness)


def measure(method):
    started = perf_counter()
    from grammar_search import Limits, SearchLimit
    from run_search import MemoryProbe
    from tools.smoke_01 import process_memory
    import numpy as np
    import platform

    reference_asset = None
    public = frozen_public()
    setup_started = perf_counter()
    phase = {}
    if method in GRAPH_METHODS:
        reference_asset, phase = build_graph_lane(method, public)
    elif method == "GENERIC_ABSTRACT_BEST_FIRST":
        from generic_search import GenericCursor as cursor_type
    else:
        from depth_search import DepthCursor as cursor_type
    setup_seconds = perf_counter() - setup_started
    resident_rss, _ = process_memory(os.getpid())
    memory_probe = MemoryProbe(2048 * MIB)
    memory_probe()
    search_start = perf_counter()
    deadline = search_start + SOFT_QUERY_SECONDS
    limits = Limits(SOFT_QUERY_SECONDS, 300_000, 180_000)
    entries = []
    exhausted = False
    limit_reason = None
    try:
        if method == "FULL_FLAT":
            entries = list(direct_flat_prefix(reference_asset, public, 500))
            exhausted = len(entries) < 500
            memory_probe()
        else:
            if method in GRAPH_METHODS:
                cursor = reference_asset.make_cursor(method, public, 1, limits, memory_probe, deadline=deadline)
            else:
                cursor = cursor_type(public, 1, limits, memory_probe, deadline=deadline)
            while len(entries) < 500:
                entry = cursor.next_contract()
                if entry is None:
                    exhausted = cursor.exhausted
                    break
                entries.append(entry)
    except SearchLimit as exc:
        limit_reason = str(exc)

    query_seconds = perf_counter() - search_start
    _, lifetime_peak = process_memory(os.getpid())
    if limit_reason is None and query_seconds > SOFT_QUERY_SECONDS:
        limit_reason = "wall_time_limit_after_noninterruptible_call"
    if limit_reason is None:
        status = "EXACT_DOMAIN_EXHAUSTED_SHORT" if exhausted else "EXACT_TOPK_FULL_LENGTH"
    else:
        status = "NOT_CERTIFIED_WITHIN_BUDGET"
    init_search_seconds = perf_counter() - started

    archived = read(ARCHIVE / "depth3" / "regression" / (FIXTURE + ".json"))["topk"]
    actual = [(x.key.hex(), struct.pack(">d", x.score), x.witness) for x in entries]
    expected = [(x["key"], struct.pack(">d", x["score"]), x["witness"]) for x in archived]
    if (actual != expected[:len(actual)] or
            (status != "NOT_CERTIFIED_WITHIN_BUDGET" and actual != expected)):
        raise AssertionError("fresh-process diagnostic prefix differed from the sealed reference")
    digest = hashlib.sha256(b"".join(s + bytes.fromhex(k) for k, s, _ in actual)).hexdigest()
    return {
        "method": method, "instance_id": FIXTURE, "python": platform.python_version(),
        "numpy": np.__version__, "verified_asset_setup_s": setup_seconds, "setup_phases": phase,
        "cold_public_query_s": query_seconds, "child_init_through_query_s": init_search_seconds,
        "post_setup_resident_working_set_bytes": resident_rss, "os_lifetime_peak_working_set_bytes": lifetime_peak,
        "certification": status, "returned": len(actual), "prefix_sha256": digest, "limit_reason": limit_reason,
    }


def run_diagnostic():
    from src.windows_suspended_job import launch
    from tools.smoke_01 import memory_status, process_memory

    auth = read(ROOT / "PILOT_AUTHORIZATION_STATE.json")
    if auth["namespace_authorizations"]["CONFIRM"]["allowed"] is not False:
        raise ValueError("confirmation execution must stay closed")
    if (ROOT / "FROZEN_CONFIG.yaml").exists():
        raise ValueError("unexpected frozen configuration")
    log_dir = HERE / "cold_diagnostic"
    log_dir.mkdir(exist_ok=False)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               OMP_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    records = []
    for method in METHODS:
        available = memory_status()[1]
        if available < 1280 * MIB:
            raise RuntimeError("PAUSED_MEMORY before fresh-process comparison")
        log = log_dir / (method + ".json")
        started = perf_counter()
        job = launch([sys.executable, "-B", str(SCRIPT), "--child", method],
                     env=env, cwd=ROOT, stdout_path=log)
        sampled_peak = 0
        try:
            while job.poll() is None:
                available = min(available, memory_status()[1])
                if available < 768 * MIB:
                    raise RuntimeError("cold diagnostic emergency memory floor")
                try:
                    used, peak = process_memory(job.pid)
                except OSError:
                    if job.poll() is None:
                        raise
                else:
                    sampled_peak = max(sampled_peak, peak)
                    if used > 2048 * MIB:
                        raise RuntimeError("cold diagnostic worker working-set ceiling")
                if perf_counter() - started > HARD_CHILD_SECONDS:
                    raise TimeoutError("cold diagnostic child process limit")
                sleep(0.025)
            wall = perf_counter() - started
            report = job.finish()
            if not report["pass"]:
                raise RuntimeError(f"cold child failed for {method}, see {log}")
        finally:
            job.close()
        record = read(log)
        records.append(dict(record, parent_launch_to_child_exit_s=wall,
                            parent_sampled_peak_working_set_bytes=sampled_peak,
                            minimum_available_memory_bytes=available,
                            suspended_job_tree_empty=report["job_accounting"]["active_processes"] == 0))

    with (HERE / "cold_start_costs.json").open("x", encoding="utf-8") as output:
        json.dump({"fixture": FIXTURE, "fresh_processes": len(records),
                   "filesystem_cache_controlled": False, "methods": records},
                  output, allow_nan=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=METHODS)
    args = parser.parse_args()
    if args.child:
        print(json.dumps(measure(args.child), allow_nan=False), flush=True)
    else:
        run_diagnostic()

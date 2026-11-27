"""Independent exhaustive differentials on projections of one existing fixture."""

from collections import Counter
from hashlib import sha256
from struct import pack
import argparse
import json

from run_comparison import (
    ABLATIONS, CURRENT, GENERIC, HERE, Limits, fixture_path, require_safe_scope,
    verification_public,
)
from check_reduced_depth3 import CASES, FIXTURE, independent_complete, reduced_public
from depth_search import DepthCursor
from src.engine import ast_depth, required_capabilities
from src.enumeration import syntax_key
from src.instances import deserialize_instance
from src.state_machine import normalize
from grammar_search import decode_witness


def factory(method, public, depth, limits):
    if method == GENERIC:
        from generic_search import GenericCursor
        return GenericCursor(public, depth, limits)
    if method in (CURRENT, "NO_LAZY_STOP"):
        return DepthCursor(public, depth, limits)
    from ablations import make_ablated
    return make_ablated(method, public, depth, limits)


def compare(method, public, depth, expected, representatives):
    cursor = factory(method, verification_public(public), depth, Limits(120.0, 2_000_000, 260_000))
    for rank, (key, score) in enumerate(expected, 1):
        observed = cursor.next_contract()
        raw, ast = representatives[key]
        witness = syntax_key(normalize(ast, public))
        if (observed is None or observed.key != key or pack(">d", observed.score) != pack(">d", score)
                or observed.witness != witness or observed.raw_witness != raw):
            raise AssertionError(f"{method} depth={depth} first rank mismatch at {rank}")
        derivation = decode_witness(observed.raw_witness)
        if ast_depth(derivation) > depth or not required_capabilities(derivation) <= set(public.capabilities):
            raise AssertionError("raw witness violates the original typed scope before normalization")
    if cursor.next_contract() is not None or not cursor.exhausted:
        raise AssertionError("stream did not exhaust exactly at the independently known domain size")
    return cursor.metrics()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", action="append", choices=(CURRENT, GENERIC, *ABLATIONS))
    parser.add_argument("--output", default="reduced_correctness.json")
    args = parser.parse_args()
    require_safe_scope()
    source = fixture_path(FIXTURE)
    raw = source.read_bytes()
    public = deserialize_instance(raw.decode("utf-8")).public
    methods = tuple(args.method or (CURRENT, GENERIC, *ABLATIONS))
    source_files = [HERE / name for name in ("generic_search.py", "ablations.py", "check_reduced.py")
                    if (HERE / name).exists()]
    versions = {p.name: sha256(p.read_bytes()).hexdigest() for p in source_files}
    counts = Counter()
    rows = []
    failed = set()
    for case, fields, unavailable, profiles in CASES:
        projected = reduced_public(public, fields, unavailable, profiles)
        for depth in (1, 2, 3):
            encoder, representatives, expected, _, leaves, _ = independent_complete(projected, depth)
            groups = Counter()
            role_groups = (("apply_conditional_policy", "observe_motion_state"),
                           ("schedule_start",), ("apply_phased_policy", "set_validity_interval"),
                           ("enable_edge_offload", "reserve_edge_compute"))
            for key, _ in expected:
                groups[sum(any(key[1 + 2 * encoder.roles.index(role)] != 255 for role in group)
                           for group in role_groups)] += 1
            for method in methods:
                if method in failed:
                    continue
                row = {"method": method, "case": case, "depth": depth, "raw_leaves": leaves,
                       "eligible_signatures": len(expected), "groups": groups}
                try:
                    metrics = compare(method, projected, depth, expected, representatives)
                    row.update(status="PASS", metrics=metrics)
                    counts[method] += 1
                except (AssertionError, RuntimeError, ValueError) as exc:
                    row.update(status="FAIL", error=str(exc))
                    print(json.dumps(row), flush=True)
                    failed.add(method)
                rows.append(row)
            print(f"{case} depth={depth} raw={leaves} eligible signatures={len(expected)}", flush=True)
    if any(versions[p.name] != sha256(p.read_bytes()).hexdigest() for p in source_files):
        raise RuntimeError("Method source changed during the reduced check")
    result = {"status": "FAIL" if failed else "PASS", "cases": rows, "pass_by_method": counts,
              "source_fixture": FIXTURE, "source_sha256": sha256(raw).hexdigest(),
              "method_sources": versions}
    with (HERE / args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, allow_nan=False, indent=2)
        stream.write("\n")
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())

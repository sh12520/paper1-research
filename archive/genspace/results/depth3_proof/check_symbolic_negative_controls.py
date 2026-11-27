"""Semantic tamper tests for the symbolic coverage checker."""

from copy import deepcopy
import json
from math import inf, nextafter
from time import monotonic

from check_negative_controls import HERE, ROOT, hash_bytes, fixture_for, load, prefix_hash
from audit_common import sealed_payloads
from native_symbolic_producer import produce_symbolic
from symbolic_format import digest, dump
from symbolic_verifier import ProofRejected, verify_symbolic
from unseen_verifier import RejectedEvidence


SYMBOLIC_FIXTURE = "F4__medium__high__sparse__d2__s0"
SHORT_FIXTURE = "F4__high__high__sparse__d2__s0"
CUT_FIELDS = ("compiled", "open_shapes", "open_assignments", "buffered", "prefix")


def bind(case, fixture, snapshot):
    return {"fixture": case, "public_sha256": fixture.public_hash,
            "case_sha256": fixture.seal_hash, "snapshot_sha256": snapshot,
            "capabilities": sorted(fixture.public.capabilities), "effective_depth": 3}


def compact_pool(proof):
    seen = {key for cut in proof["checkpoints"].values() for field in CUT_FIELDS for key in cut[field]}
    pool = proof["nodes"]
    seen.update(pool[key][1] for key in tuple(seen)
                if pool[key][0] in {"OPEN_ASSIGNMENT", "COMPLETE_CANDIDATE"})
    proof["nodes"] = {key: pool[key] for key in sorted(seen)}


def update_node(proof, cut, field, index, record):
    key = digest(record)
    proof["nodes"][key] = record
    cut[field][index] = key


def omit_open_shape(proof, *args):
    del proof["checkpoints"]["10"]["open_shapes"][0]


def omit_parameter_shape(proof, *args):
    cut = proof["checkpoints"]["10"]
    for index, key in enumerate(cut["open_assignments"]):
        record = deepcopy(proof["nodes"][key])
        mask = record[3]
        if mask.bit_count() > 1:
            record[3] = mask & (mask - 1)
            update_node(proof, cut, "open_assignments", index, record)
            return
    raise AssertionError("Fixture has no nonsingleton profile partition")


def raise_cutoff_bound(proof, *args):
    cut = proof["checkpoints"]["10"]
    key = cut["open_shapes"][0]
    record = deepcopy(proof["nodes"][key])
    record[-1] = nextafter(1e6, inf).hex()
    update_node(proof, cut, "open_shapes", 0, record)


def wrong_availability(proof, *args):
    proof["binding"]["capabilities"].pop()


def wrong_reference_merge(proof, *args):
    cut = proof["checkpoints"]["10"]
    field = "open_assignments" if cut["open_assignments"] else "buffered"
    record = deepcopy(proof["nodes"][cut[field][0]])
    template = deepcopy(proof["nodes"][record[1]])
    template[-1] += 1
    replacement = digest(template)
    assert replacement not in proof["nodes"]
    proof["nodes"][replacement] = template
    record[1] = replacement
    update_node(proof, cut, field, 0, record)


def wrong_tie(proof, rows, cuts):
    for position, (left, right) in enumerate(zip(rows, rows[1:])):
        if left["score"].hex() != right["score"].hex():
            continue
        rows[position:position+2] = [right, left]
        for cut in proof["checkpoints"].values():
            if len(cut["prefix"]) >= position+2:
                values = cut["prefix"]
                values[position:position+2] = [values[position+1], values[position]]
        return
    raise AssertionError("Fixture has no genuine binary64 tie")


def omit_frontier_assignment(proof, *args):
    cut = proof["checkpoints"]["10"]
    del cut["open_assignments"][0]


def wrong_fingerprint(proof, *args):
    proof["binding"]["public_sha256"] = "f" * 64


def false_short(proof, rows, cuts):
    rows.pop()
    for k, cut in proof["checkpoints"].items():
        if cut["exhausted"]:
            del cut["prefix"][-1]
            cuts[k]["returned"] -= 1
            cuts[k]["prefix_sha256"] = prefix_hash(rows[:cuts[k]["returned"]])
            cuts[k]["boundary_score"] = rows[cuts[k]["returned"]-1]["score"]
            cuts[k]["boundary_key"] = rows[cuts[k]["returned"]-1]["key"]


def run():
    if any(load(ROOT / "METHOD_AUTHORIZATION_STATE.json")["namespace_authorizations"][key]
           for key in ("METHOD_HOLDOUT", "CONFIRM")):
        raise RuntimeError("Development-only proof checker requires both routes closed")
    if (ROOT / "FROZEN_CONFIG.yaml").exists():
        raise RuntimeError("Unexpected frozen configuration")
    snapshot_path = ROOT / "METHOD_EXECUTION_SNAPSHOT_DRAFT.json"
    snapshot = hash_bytes(snapshot_path.read_bytes())
    old_snapshot = hash_bytes((ROOT / "PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json").read_bytes())
    assert snapshot != old_snapshot
    seal_path = ROOT / "results" / "depth3" / "development" / "search_seal.json"
    seal, cases, seal_sha = sealed_payloads(seal_path)
    manifest = load(ROOT / "results" / "pilot" / "instances_manifest.json")
    source = {}
    positives = {}
    for case in (SYMBOLIC_FIXTURE, SHORT_FIXTURE):
        fixture = fixture_for(case, seal, cases, manifest)
        binding = bind(case, fixture, snapshot)
        proof, body = produce_symbolic(fixture.public, binding, lambda: 0, seconds=12.0)
        assert body["native_prefix"] == fixture.rows
        proof = json.loads(dump(proof))
        verdict = verify_symbolic(fixture.public, proof, binding, fixture.rows, fixture.cuts, lambda: 0)
        assert verdict["status"] == "VERIFIED"
        positives[case] = verdict
        source[case] = (fixture, binding, proof)

    results = {}

    def mutate(name, operation, case=SYMBOLIC_FIXTURE):
        fixture, binding, original = source[case]
        proof, rows, cuts = deepcopy((original, fixture.rows, fixture.cuts))
        operation(proof, rows, cuts)
        compact_pool(proof)
        revised = dump(proof)
        started = monotonic()
        try:
            verify_symbolic(fixture.public, json.loads(revised), binding, rows, cuts, lambda: 0)
        except (ProofRejected, RejectedEvidence) as error:
            results[name] = {"status": "REJECTED", "reason": str(error),
                             "recomputed_mutated_serialization_sha256": hash_bytes(revised),
                             "checker_wall_s": monotonic()-started}
        else:
            raise AssertionError(f"Semantic mutation was accepted: {name}")

    mutate("missing_legal_child", omit_open_shape)
    mutate("missing_parameter_partition", omit_parameter_shape)
    mutate("inflated_claimed_lower_bound", raise_cutoff_bound)
    mutate("incorrect_capability_mask", wrong_availability)
    mutate("incorrect_semantic_merge", wrong_reference_merge)
    mutate("changed_tie_breaking", wrong_tie)
    mutate("deleted_frontier_node", omit_frontier_assignment)
    mutate("changed_query_fingerprint", wrong_fingerprint)
    mutate("false_exhausted_short", false_short, SHORT_FIXTURE)

    # Take the genuinely old-query proof and present it to the checker with
    # a different current query binding. Keep the superseded snapshot as well.
    _, _, old = source[SHORT_FIXTURE]
    fixture, binding, original = source[SYMBOLIC_FIXTURE]
    replay = deepcopy(old)
    replay["binding"] = {**binding, "snapshot_sha256": old_snapshot}
    revised = dump(replay)
    try:
        verify_symbolic(fixture.public, json.loads(revised), binding, fixture.rows, fixture.cuts, lambda: 0)
    except ProofRejected as error:
        results["stale_snapshot_rebound"] = {"status": "REJECTED", "reason": str(error),
                                            "recomputed_mutated_serialization_sha256": hash_bytes(revised)}
    else:
        raise AssertionError("Stale snapshot was accepted with a different query")

    truncated = dump(original)[:-17]
    try:
        json.loads(truncated)
    except json.JSONDecodeError as error:
        results["truncated_proof_file"] = {"status": "REJECTED", "reason": type(error).__name__,
                                           "position": error.pos,
                                           "recomputed_mutated_serialization_sha256": hash_bytes(truncated)}
    else:
        raise AssertionError("Truncation was accepted as a complete JSON proof")

    assert len(results) == 11
    assert hash_bytes(snapshot_path.read_bytes()) == snapshot
    assert hash_bytes(seal_path.read_bytes()) == seal_sha
    result = {"status": "PASS", "passed": len(results), "results": results, "positive_coverage": positives,
              "primary_fixture": SYMBOLIC_FIXTURE, "short_fixture": SHORT_FIXTURE,
              "snapshot_sha256": snapshot, "archive_seal_sha256": seal_sha}
    (HERE / "symbolic_negative_controls.json").write_bytes(dump(result) + b"\n")
    for name, outcome in results.items():
        print(name, outcome["status"], outcome["reason"])


if __name__ == "__main__":
    run()

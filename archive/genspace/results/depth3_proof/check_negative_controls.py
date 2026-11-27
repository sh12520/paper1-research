"""Semantic tamper tests for Depth 3 public proof archives."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from math import inf, nextafter
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "results" / "depth3"), str(HERE)]

from proof_producer import compact, produce
from cover_verifier import UNSOUND, expand, read_proof, verify
from unseen_verifier import AbstractSemantics, PublicReference
from certificate_report import public_input
from audit_common import sealed_payloads


PRIMARY_FIXTURE = "F4__high__high__sparse__d2__s0"
OTHER_FIXTURE = "F3__high__high__sparse__d2__s0"
EXACT = {"EXACT_TOPK_FULL_LENGTH", "EXACT_DOMAIN_EXHAUSTED_SHORT"}


def hash_bytes(raw):
    return sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def prefix_hash(rows):
    return hash_bytes(b"".join(struct.pack(">d", row["score"]) + bytes.fromhex(row["key"]) for row in rows))


@dataclass(frozen=True)
class Fixture:
    public: object
    public_hash: str
    seal_hash: str
    rows: list
    cuts: dict


def rebind_prefix(proof, rows, cuts):
    """Recompute claim digests as an untrusted producer could."""
    for cut in cuts.values():
        returned = rows[:cut["returned"]]
        boundary = returned[-1] if returned else {}
        cut["boundary_score"] = boundary.get("score")
        cut["boundary_key"] = boundary.get("key")
        cut["prefix_sha256"] = prefix_hash(returned)
    proof["prefix_sha256"] = cuts[str(proof["coverage_k"])]["prefix_sha256"]


def walk_contexts(proof, ref):
    grammar = AbstractSemantics(ref.public, 3)

    def walk(node_id, term, parent=None, choice=None):
        frame = proof["nodes"][node_id]
        yield node_id, term, frame, parent, choice
        if frame[0] == "E":
            choices = expand(term, grammar, ref)
            for index, (child, context) in enumerate(zip(frame[1], choices, strict=True)):
                yield from walk(child, context, node_id, index)

    yield from walk(proof["root"], grammar.root)


def delete_legal_child(proof):
    root = proof["nodes"][proof["root"]]
    # Use an operator branch, separately from the scalar-domain control.
    for index in reversed(range(len(root[1]))):
        if proof["nodes"][root[1][index]][0] == "E":
            root[1].pop(index)
            return
    raise AssertionError("Positive control lacks a live operator child")


def omit_profile_partition(proof, ref):
    from src.models import Static

    for _, term, frame, parent, _ in walk_contexts(proof, ref):
        if parent is not None and frame[0] == "E":
            choices = expand(term, AbstractSemantics(ref.public, 3), ref)
            for index, context in enumerate(choices):
                if isinstance(context, Static) or proof["nodes"][frame[1][index]][0] in {"B", "C"}:
                    frame[1].pop(index)
                    return
    raise AssertionError("Positive control lacks a nested parameter choice")


def increase_bound(proof):
    frame = next(frame for frame in proof["nodes"] if frame[0] == "B")
    frame[1] = nextafter(frame[1], inf)


def wrong_availability(proof):
    roles = proof["capabilities"]
    roles.remove("reserve_edge_compute")
    roles.append("schedule_start")
    roles.sort()


def semantic_merge(proof, ref, *, equal):
    original = proof["nodes"]
    frames = []

    def unique_context(node_id):
        frame = original[node_id]
        new_id = len(frames)
        frames.append(list(frame))
        if frame[0] == "E":
            frames[new_id][1] = [unique_context(child) for child in frame[1]]
        return new_id

    proof["root"] = unique_context(proof["root"])
    proof["nodes"] = frames
    complete = [(node_id, ref.encoder.encode(term))
                for node_id, term, frame, _, _ in walk_contexts(proof, ref) if frame[0] == "C"]
    for pos, (from_node, from_key) in enumerate(complete):
        for to_node, to_key in complete[pos+1:]:
            if (from_key == to_key) == equal:
                frames[from_node] = ["M", to_node]
                return
    raise AssertionError("Fixture lacks the two distinct syntax leaves needed for a merge control")


def reverse_a_tie(proof, rows, cuts):
    for position, (left, right) in enumerate(zip(rows, rows[1:])):
        if struct.pack(">d", left["score"]) == struct.pack(">d", right["score"]):
            assert left["key"] < right["key"]
            rows[position:position + 2] = [right, left]
            rebind_prefix(proof, rows, cuts)
            return
    raise AssertionError("Positive control lacks a genuine binary64 score tie")


def delete_frontier_node(proof):
    nodes = proof["nodes"]
    missing = next(i for i, frame in enumerate(nodes) if frame[0] == "B")
    nodes.pop(missing)

    def rename(old_id):
        if old_id == missing:
            return len(nodes)
        return old_id - (old_id > missing)

    for frame in nodes:
        if frame[0] == "E":
            frame[1] = [rename(node_id) for node_id in frame[1]]
        elif frame[0] == "M":
            frame[1] = rename(frame[1])
    proof["root"] = rename(proof["root"])


def false_short_exhaustion(proof, rows, cuts):
    assert cuts[str(proof["coverage_k"])]["full_domain_exhausted"] is True
    rows.pop()
    for cut in cuts.values():
        cut["returned"] = min(cut["returned"], len(rows))
    rebind_prefix(proof, rows, cuts)


def proof_verdict(fixture, proof, snapshot_sha256, rows=None, cuts=None):
    return verify(fixture.public, rows if rows is not None else fixture.rows,
                  cuts if cuts is not None else fixture.cuts, proof, snapshot_sha256=snapshot_sha256,
                  sealed_case_sha256=fixture.seal_hash)


def fixture_for(identity, seal, cases, pilot_manifest):
    item = seal["cases"][identity]
    source = cases[identity]
    public, serialized_hash = public_input(identity, pilot_manifest)
    if serialized_hash != source["serialized_sha256"]:
        raise AssertionError("Existing fixture differs from archived public binding")
    return Fixture(public, pilot_manifest[identity]["public_hash"], item["sha256"],
                   source["topk"], source["k_certificates"])


def run():
    method_auth = load(ROOT / "METHOD_AUTHORIZATION_STATE.json")
    if any(method_auth["namespace_authorizations"][key] is not False for key in ("METHOD_HOLDOUT", "CONFIRM")):
        raise RuntimeError("Development-only proof checker requires both routes closed")
    if (ROOT / "FROZEN_CONFIG.yaml").exists():
        raise RuntimeError("Unexpected frozen configuration")
    snapshot_path = ROOT / "METHOD_EXECUTION_SNAPSHOT_DRAFT.json"
    snapshot = hash_bytes(snapshot_path.read_bytes())
    previous = hash_bytes((ROOT / "PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json").read_bytes())
    assert snapshot != previous
    seal_path = ROOT / "results" / "depth3" / "development" / "search_seal.json"
    seal, cases, seal_sha = sealed_payloads(seal_path)
    manifest = load(ROOT / "results" / "pilot" / "instances_manifest.json")
    main_fixture = fixture_for(PRIMARY_FIXTURE, seal, cases, manifest)
    other = fixture_for(OTHER_FIXTURE, seal, cases, manifest)
    reference = PublicReference(main_fixture.public)
    positive = {}
    for k in ("10", "500"):
        proof, metrics = produce(main_fixture.public, main_fixture.public_hash,
                                 main_fixture.rows, main_fixture.cuts,
                                 snapshot_sha256=snapshot, sealed_case_sha256=main_fixture.seal_hash,
                                 requested_ks=(k,))
        if proof is None:
            raise AssertionError({"missing_positive_at": k, "metrics": metrics})
        decision = proof_verdict(main_fixture, proof, snapshot)
        if decision["cuts"][k]["status"] not in EXACT:
            raise AssertionError({"missing_certified_positive_at": k, "decision": decision})
        positive[k] = proof

    merged_positive = deepcopy(positive["500"])
    semantic_merge(merged_positive, reference, equal=True)
    merged_verdict = proof_verdict(main_fixture, merged_positive, snapshot)
    if merged_verdict["cuts"]["500"]["status"] not in EXACT:
        raise AssertionError({"missing_verified_safe_merge": merged_verdict})

    results = {}

    def mutate(name, k, operation):
        proof, rows, cuts = deepcopy((positive[k], main_fixture.rows, main_fixture.cuts))
        operation(proof, rows, cuts)
        result = proof_verdict(main_fixture, proof, snapshot, rows, cuts)
        if result["status"] != UNSOUND:
            raise AssertionError({"expected": UNSOUND, "negative_case": name, "actual": result})
        results[name] = {"status": "REJECTED", "verdict": result,
                         "recomputed_mutated_serialization_sha256": hash_bytes(compact(proof))}

    mutate("missing_legal_child", "10", lambda proof, *_: delete_legal_child(proof))
    mutate("missing_parameter_partition", "10", lambda proof, *_: omit_profile_partition(proof, reference))
    mutate("inflated_claimed_lower_bound", "10", lambda proof, *_: increase_bound(proof))
    mutate("incorrect_capability_mask", "10", lambda proof, *_: wrong_availability(proof))
    mutate("incorrect_semantic_merge", "500", lambda proof, *_: semantic_merge(proof, reference, equal=False))
    mutate("changed_tie_breaking", "10", reverse_a_tie)
    mutate("deleted_frontier_node", "10", lambda proof, *_: delete_frontier_node(proof))
    mutate("changed_query_fingerprint", "10", lambda proof, *_: proof.update(public_hash=other.public_hash))
    mutate("false_exhausted_short", "500", false_short_exhaustion)

    old_proof = deepcopy(positive["500"])
    old_proof.update(snapshot_sha256=previous, public_hash=other.public_hash,
                     sealed_case_sha256=other.seal_hash, prefix_sha256=prefix_hash(other.rows))
    replay = proof_verdict(other, old_proof, snapshot)
    if replay["status"] != UNSOUND:
        raise AssertionError({"expected": UNSOUND, "negative_case": "stale_snapshot_rebound", "actual": replay})
    results["stale_snapshot_rebound"] = {"status": "REJECTED", "verdict": replay,
                                        "recomputed_mutated_serialization_sha256": hash_bytes(compact(old_proof))}

    truncated = compact(positive["10"])[:-17]
    with TemporaryDirectory(prefix="depth3-negative-", dir=HERE) as dirname:
        path = Path(dirname) / "truncated.json"
        path.write_bytes(truncated)
        try:
            read_proof(path)
        except json.JSONDecodeError as error:
            results["truncated_proof_file"] = {"status": "REJECTED",
                                               "reason": type(error).__name__, "position": error.pos,
                                               "recomputed_mutated_serialization_sha256": hash_bytes(truncated)}
        else:
            raise AssertionError("Truncation was accepted as a complete JSON proof")

    assert hash_bytes(seal_path.read_bytes()) == seal_sha
    assert hash_bytes(snapshot_path.read_bytes()) == snapshot
    assert len(results) == 11
    result = {"status": "PASS", "fixture": PRIMARY_FIXTURE, "archive_seal_sha256": seal_sha,
              "snapshot_sha256": snapshot, "passed": len(results), "results": results,
              "positive_same_key_terminal_merge": merged_verdict["cuts"]["500"]["status"],
              "positive_coverage": {k: dict(Counter(frame[0] for frame in proof["nodes"]))
                                    for k, proof in positive.items()}}
    (HERE / "negative_controls.json").write_bytes(compact(result) + b"\n")
    for name, row in results.items():
        print(f"{name}: {row['status']}")


if __name__ == "__main__":
    run()

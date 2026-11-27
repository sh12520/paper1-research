"""Exercise detached proof consumption with an existing sealed short-domain fixture."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from math import inf, nextafter

from symbolic_format import ARCHIVE, HERE, ROOT
from cover_verifier import BLOCKED, CAPPED, FULL, SHORT
from method_proof_bridge import (METHODS, AttemptIdentity, IntegrityError, QueryBinding,
                                 adjudicate, authenticate_shared_proof)
from src.instances import deserialize_instance


FIXTURE = "F1__low__high__sparse__d2__s0"
GENERIC = "GENERIC_ABSTRACT_BEST_FIRST"


def existing_fixture():
    def load(path):
        return json.loads(path.read_bytes())

    folder = HERE / "work" / FIXTURE
    serialized = (ARCHIVE / "pilot" / "instances" / (FIXTURE + ".json")).read_bytes()
    sealed = (ARCHIVE / "depth3" / "development" / (FIXTURE + ".json")).read_bytes()
    archived = load(folder / "target.json")
    source = json.loads(sealed)
    assert archived == {k: source[k] for k in archived}
    prior_snapshot = (ROOT / "METHOD_EXECUTION_SNAPSHOT_DRAFT.json").read_bytes()
    snapshot_sha256 = sha256(prior_snapshot).hexdigest()
    snapshot = json.loads(prior_snapshot)["payload"]
    fixture = deserialize_instance(serialized.decode("utf-8"))
    expected = load(folder / "public.json")["binding"]
    proof_sha256 = load(folder / "emit.json")["proof_sha256"]
    assert expected["sealed_case_sha256"] == sha256(sealed).hexdigest()
    query = QueryBinding(FIXTURE, fixture.namespace, sha256(serialized).hexdigest(),
                         fixture.instance_hash, fixture.public_hash, snapshot_sha256,
                         snapshot["candidate_source_tree_sha256"], snapshot["plan_sha256"])
    proof_path = HERE / "proofs" / (FIXTURE + ".json.gz")
    proof = authenticate_shared_proof(query, fixture.public, proof_path, proof_sha256,
                                      expected, archived["topk"], archived["k_certificates"],
                                      lambda: 0)
    return serialized, fixture, query, archived, expected, proof_path, proof_sha256, proof


def check():
    _, fixture, query, archived, expected, proof_path, proof_sha256, proof = existing_fixture()
    passed = []

    def attempt(method):
        return AttemptIdentity(query.query_id, method, 3, query.instance_hash,
                               query.serialized_sha256, query.method_digest(method),
                               query.plan_sha256)

    def staged(method):
        return {"status": "PROOF_PENDING", "search": {
            "method": method, "effective_depth": 3, "instance_hash": query.instance_hash,
            "serialized_sha256": query.serialized_sha256,
            "prefix": deepcopy(archived["topk"]), "cuts": deepcopy(archived["k_certificates"]),
        }}

    def audit(outcome, evidence=proof):
        return adjudicate(query, fixture.public, attempt(GENERIC), outcome, evidence)

    def rejected(name, func):
        try:
            func()
        except IntegrityError:
            passed.append(name)
            return
        raise AssertionError(name + " unexpectedly accepted")

    for method in sorted(METHODS):
        status, receipt = adjudicate(query, fixture.public, attempt(method), staged(method), proof)
        assert status == SHORT and receipt["independently_verified"]
        assert [row["status"] for row in receipt["independent_checkpoints"].values()] == [FULL, SHORT, SHORT]
    passed.append("all_eight_method_labels_match_same_proven_prefix")

    result = staged(GENERIC)
    status, receipt = audit(result, None)
    assert status == "BLOCKED" and receipt["independent_checkpoints"]["500"]["status"] == BLOCKED
    passed.append("missing_proof_blocks_native_exact")

    timed = staged(GENERIC)
    timed.update(status=CAPPED, reason="wall_time_limit")
    timed["search"]["cuts"]["500"] = {"status": CAPPED}
    status, receipt = audit(timed)
    assert status == CAPPED and not receipt["independently_verified"]
    assert receipt["independent_checkpoints"]["100"]["status"] == SHORT
    assert receipt["independent_checkpoints"]["500"]["status"] == CAPPED
    passed.append("checkpoint_resource_cap_does_not_become_proof_success")

    # A5 can finish K=500 and still exceed the budget during mandatory extra work.
    after = staged(GENERIC)
    after.update(status=CAPPED, reason="wall_time_limit")
    status, receipt = audit(after)
    assert status == CAPPED and not receipt["independently_verified"]
    assert receipt["independent_checkpoints"]["500"]["status"] == SHORT
    passed.append("post_cut_resource_cap_retains_parent_status")

    first = archived["k_certificates"]["10"]
    interrupted = {"status": CAPPED, "reason": "expansion_limit", "preserved_checkpoints": {
        "10": {"prefix": archived["topk"][:10], "cut": first},
    }}
    status, receipt = audit(interrupted)
    assert status == CAPPED and receipt["independent_checkpoints"]["10"]["status"] == FULL
    assert audit(interrupted, None)[0] == CAPPED
    passed.append("parent_preserved_prefix_checked_without_upgrading_limit")

    changed = staged(GENERIC)
    changed["search"]["prefix"][0]["score"] = nextafter(changed["search"]["prefix"][0]["score"], inf)
    assert audit(changed)[0] == "UNSOUND"
    passed.append("binary64_one_ulp_rejected")

    swapped = staged(GENERIC)
    rows = swapped["search"]["prefix"]
    rows[0], rows[1] = rows[1], rows[0]
    assert audit(swapped)[0] == "UNSOUND"
    passed.append("wrong_rank_rejected")

    falsely_short = staged(GENERIC)
    falsely_short["search"]["cuts"]["500"]["returned"] -= 1
    assert audit(falsely_short)[0] == "UNSOUND"
    passed.append("false_short_domain_rejected")

    rejected("method_spoof_rejected", lambda: audit(staged("NO_LAZY_STOP")))
    rejected("method_fingerprint_rejected", lambda: adjudicate(
        query, fixture.public, replace(attempt(GENERIC),method_sha256="0"*64), result, proof))
    rejected("prior_snapshot_proof_cannot_match_new_binding", lambda: authenticate_shared_proof(
        replace(query, snapshot_sha256="1"*64), fixture.public, proof_path, proof_sha256, expected,
        archived["topk"], archived["k_certificates"], lambda: 0))
    rejected("proof_bytes_mismatch_rejected", lambda: authenticate_shared_proof(
        query, fixture.public, proof_path, "2"*64, expected, archived["topk"],
        archived["k_certificates"], lambda: 0))
    rejected("receipt_reuse_across_serialized_inputs_rejected", lambda: adjudicate(
        replace(query, serialized_sha256="3"*64), fixture.public,
        replace(attempt(GENERIC), serialized_sha256="3"*64), result, proof))
    rejected("foreign_namespace_rejected", lambda: replace(query, namespace="GENSPACE-FAIL-01-CONFIRM"))
    rejected("development_proof_cannot_fill_holdout_admission", lambda: authenticate_shared_proof(
        replace(query, namespace="GENSPACE-METHOD-HOLDOUT-V1"), fixture.public, proof_path,
        proof_sha256, expected, archived["topk"], archived["k_certificates"], lambda: 0))
    return {"status": "PASS", "fixture": FIXTURE, "fixture_proof_sha256": proof_sha256,
            "snapshot_sha256": query.snapshot_sha256, "passed": passed,
            "development_scope": "One staged supervised attempt envelope. No method run or input generation."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))

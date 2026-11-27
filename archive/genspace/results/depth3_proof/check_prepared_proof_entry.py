"""Validate the disabled successor and use its parent callbacks on an archived fixture."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from check_method_proof_bridge import FIXTURE, GENERIC, existing_fixture
from cover_verifier import CAPPED, FULL, SHORT
from holdout_supervisor import WindowsWarmSupervisor, formal_budget
from holdout_transactions import AttemptIdentity, IntegrityError, TransactionStore, bind_result
from method_proof_cache import ProofCache
from prepare_holdout_proof_entry import (ADDENDUM, HERE, refine_depth3, route, validate_addendum,
                                         validate_preparation, verify_prior_depth3)
from tools.smoke_01 import memory_status


def check():
    prepared = validate_preparation()
    for args in ((), ("--namespace", "GENSPACE-FAIL-01-CONFIRM")):
        result = subprocess.run([sys.executable, "-B", str(HERE / "prepare_holdout_proof_entry.py"), *args],
                                check=False, capture_output=True, text=True)
        assert result.returncode == 2 and json.loads(result.stdout) == {"status": "AUTHORIZATION_DENIED"}
    assert not route.RELEASE_ROOT.exists() and not route.RESULT_ROOT.exists()
    if memory_status()[1] < 2048 * (1 << 20):
        raise RuntimeError("PAUSED_MEMORY_BEFORE_START")

    raw, instance, query, *_ = existing_fixture()
    body, snapshot_sha256, plan = route.validate_preparation()
    assert snapshot_sha256 == query.snapshot_sha256
    draft = route.Intake(snapshot_sha256, "", {}, body["model"], plan, body)
    changed = json.loads(ADDENDUM.read_bytes())
    changed["proof_policy"]["pool_nodes"] += 1
    try:
        validate_addendum(route.canonical(changed), draft)
    except IntegrityError:
        pass
    else:
        raise AssertionError("Successor accepted the wrong proof budget")

    addendum_sha256 = prepared["depth3_proof_addendum_sha256"]
    key = b"archive-only engineering proof entry test"

    def draft_binding():
        if route.digest_file(ADDENDUM) != addendum_sha256:
            raise IntegrityError("Draft addendum changed")
        return route.digest_file(route.SNAPSHOT_PATH)

    payload = {"query_id": FIXTURE, "serialized": raw.decode("utf-8"), "effective_depth": 3,
               "serialized_sha256": query.serialized_sha256}
    found = []
    with TemporaryDirectory(prefix="prepared-proof-entry-", dir=HERE) as folder:
        root = Path(folder)
        cache = ProofCache(root / "proofs", key, addendum_sha256, draft_binding)
        store = TransactionStore(root / "attempts", snapshot_sha256, key, draft_binding)
        supervisor = WindowsWarmSupervisor(root / "ipc", route.SNAPSHOT_PATH,
                                           [sys.executable, "-B", str(route.HERE / "holdout_worker.py")],
                                           {"lane": "synth", "engineering": True}, verify_binding=draft_binding)
        cases = (
            (GENERIC, formal_budget(3), SHORT, [FULL, SHORT, SHORT]),
            (route.CURRENT, replace(formal_budget(3), expansions=1), CAPPED, [CAPPED] * 3),
        )
        try:
            for method, budget, expected, checks in cases:
                identity = AttemptIdentity(query.query_id, method, 3, query.instance_hash,
                                           query.serialized_sha256, query.method_digest(method), query.plan_sha256)
                measured = supervisor.run(dict(payload, method=method), budget)
                status, receipt, detail = refine_depth3(measured, identity, query, instance.public, cache)
                assert status == expected, (status, detail.get("reason"))
                assert [item["status"] for item in receipt["independent_checkpoints"].values()] == checks
                store.commit(identity, raw, bind_result(identity, snapshot_sha256, status,
                                                         certificate=receipt, detail=detail))
                published = store.read(identity)
                # A new cache has no in-process receipt and must recheck the archive.
                resumed = ProofCache(root / "proofs", key, addendum_sha256, draft_binding)
                verify_prior_depth3(published, identity, query, instance.public, resumed)
                found.append({"method": method, "adjudicated_status": status, "checkpoints": checks,
                              "archive_rechecked_on_resume": resumed.latest is not None,
                              "sidecar_proof_sha256": resumed.latest.compressed_sha256 if resumed.latest else None})
        finally:
            supervisor.close()
    assert len(found) == 2 and found[0]["archive_rechecked_on_resume"]
    assert not found[1]["archive_rechecked_on_resume"]
    assert not route.RELEASE_ROOT.exists() and not route.RESULT_ROOT.exists()
    return {"status": "PASS", "preparation": prepared, "default_disabled": True, "confirm_denied": True,
            "wrong_proof_budget_rejected": True, "fixture": FIXTURE, "engineering_handoff": found}


if __name__ == "__main__":
    output = json.dumps(check(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    (HERE / "prepared_proof_entry_checks.json").write_text(output, encoding="utf-8")
    print(output, end="")

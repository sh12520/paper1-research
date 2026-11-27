"""Run two supervised attempts on one existing archived pilot development fixture."""

from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from check_method_proof_bridge import FIXTURE, GENERIC, existing_fixture
from symbolic_format import HERE
from cover_verifier import CAPPED, FULL, SHORT
import holdout_route as route
from holdout_statistics_adapter import observation_from_transaction
from holdout_supervisor import WindowsWarmSupervisor, formal_budget
from holdout_transactions import AttemptIdentity, IntegrityError, TransactionStore, bind_result
from method_proof_bridge import adjudicate
from tools.smoke_01 import memory_status


def check():
    if memory_status()[1] < 2048 * (1 << 20):
        raise RuntimeError("PAUSED_MEMORY_BEFORE_START")
    _, snapshot_sha256, _ = route.validate_preparation()
    try:
        route.verify_authorization(snapshot_sha256)
    except route.RouteDenied:
        pass
    else:
        raise AssertionError("Test requires disabled holdout authorization")
    raw, instance, query, _, _, _, proof_sha256, proof = existing_fixture()
    assert query.snapshot_sha256 == snapshot_sha256
    payload = {"query_id": FIXTURE, "serialized": raw.decode("utf-8"), "effective_depth": 3,
               "serialized_sha256": query.serialized_sha256}
    cases = (
        (GENERIC, formal_budget(3), "PROOF_PENDING", SHORT),
        (route.CURRENT, replace(formal_budget(3), expansions=1), CAPPED, CAPPED),
    )
    found = []
    with TemporaryDirectory(prefix="bridge-engineering-", dir=HERE) as folder:
        temp = Path(folder)
        live = lambda: route.digest_file(route.SNAPSHOT_PATH)
        supervisor = WindowsWarmSupervisor(temp / "ipc", route.SNAPSHOT_PATH,
                                           [sys.executable, "-B", str(route.HERE / "holdout_worker.py")],
                                           {"lane": "synth", "engineering": True}, verify_binding=live)
        store = TransactionStore(temp / "attempts", snapshot_sha256,
                                 b"engineering-fixture-proof-bridge-only", live)
        try:
            for method,budget,parent_status,terminal in cases:
                attempt = AttemptIdentity(query.query_id, method, 3, query.instance_hash,
                                          query.serialized_sha256, query.method_digest(method),
                                          query.plan_sha256)
                outcome = supervisor.run(dict(payload, method=method), budget)
                assert outcome["status"] == parent_status, (outcome["status"], outcome.get("reason"))
                adjudicated, certificate = adjudicate(query, instance.public, attempt, outcome, proof)
                assert adjudicated == terminal, (adjudicated, certificate)
                saved = store.commit(attempt, raw, bind_result(attempt, snapshot_sha256, adjudicated,
                                                              certificate=certificate, detail=outcome))
                assert saved == store.read(attempt)
                observation = observation_from_transaction({"query_id": FIXTURE}, method,
                                                           query.serialized_sha256, saved)
                assert observation.status == terminal and observation.evidence_verified
                checks = [v["status"] for v in certificate["independent_checkpoints"].values()]
                if terminal == SHORT:
                    assert checks == [FULL, SHORT, SHORT] and observation.returned == len(proof.prefix)
                else:
                    assert checks == [CAPPED] * 3 and outcome["reason"] == "expanded_limit"
                    assert outcome["job"]["accounting"]["active_processes"] == 0
                    assert outcome["job"]["assignment_before_resume"] is True
                found.append({
                    "method": method, "parent_status": parent_status, "adjudicated_status": adjudicated,
                    "terminal_reason": outcome.get("reason"), "checkpoints": checks,
                    "online_interval_ns": outcome["online_interval_ns"],
                    "worker_peak_rss_bytes": outcome["os_lifetime_peak_rss_bytes"],
                    "authenticated_transaction_reread": True, "statistics_adapter_evidence_verified": True,
                })
                try:
                    adjudicate(replace(query, snapshot_sha256="0"*64),
                               instance.public, attempt, outcome, proof)
                except IntegrityError:
                    found[-1]["stale_snapshot_rejected"] = True
                else:
                    raise AssertionError("An actual supervised attempt was accepted under a stale snapshot")
        finally:
            supervisor.close()
    assert live() == snapshot_sha256
    assert not route.RELEASE_ROOT.exists() and not route.RESULT_ROOT.exists()
    return {"status": "PASS", "fixture": FIXTURE, "snapshot_sha256": snapshot_sha256,
            "proof_sha256": proof_sha256, "windows_job_active_processes_after_cap": 0,
            "attempts": found}


if __name__ == "__main__":
    output = json.dumps(check(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    (HERE / "method_supervised_bridge_checks.json").write_text(output, encoding="utf-8")
    print(output, end="")

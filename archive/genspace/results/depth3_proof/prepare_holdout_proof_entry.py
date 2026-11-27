"""Draft successor for the gated holdout parent with a depth-3 proof referee."""

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

from symbolic_format import HERE
import holdout_route as route
from holdout_runner import (EXACT, READINESS_RECEIPT, assert_live as assert_base_live,
                            refine as refine_base, worker_payload)
from holdout_supervisor import WindowsWarmSupervisor, formal_budget
from holdout_transactions import AttemptIdentity, IntegrityError, TransactionStore, bind_result
from method_proof_bridge import QueryBinding, adjudicate


ADDENDUM = HERE / "METHOD_DEPTH3_PROOF_EXECUTION_ADDENDUM_DRAFT.json"
FORMAT = "method-depth3-proof-execution-addendum-v1"
FILES = frozenset({
    "prepare_holdout_proof_entry.py", "method_proof_cache.py", "method_proof_bridge.py",
    "symbolic_format.py", "symbolic_verifier.py", "cover_verifier.py", "native_symbolic_producer.py",
    "run_depth3_proofs.py",
})
PROOF_POLICY = {
    "stage_wall_s": 180,
    "worker_working_set_bytes": 2 * (1 << 30),
    "prelaunch_available_bytes": 2 * (1 << 30),
    "emergency_available_bytes": 768 * (1 << 20),
    "proof_bytes": 96 * (1 << 20),
    "pool_nodes": 200_000,
}


def _expected_files():
    return {(HERE / name).relative_to(route.ROOT).as_posix() for name in FILES}


def _draft(body, snapshot_sha256):
    return {"format": FORMAT, "status": "DRAFT_PREPARED_EXECUTION",
            "scope": route.NAMESPACE, "base_snapshot_sha256": snapshot_sha256,
            "plan_sha256": body["plan_sha256"], "proof_policy": PROOF_POLICY,
            "infrastructure_sha256_by_file": {
                name: route.digest_file(route.ROOT / name) for name in sorted(_expected_files())}}


def build_addendum():
    """Hash-ready manifest draft. This path performs no authorization or run."""
    body, snapshot_sha256, _ = route.validate_preparation()
    return _draft(body, snapshot_sha256)


def validate_addendum(raw, intake):
    value = route.parse_document(raw.decode("utf-8"))
    expected = {"format": FORMAT, "status": "DRAFT_PREPARED_EXECUTION",
                "scope": route.NAMESPACE, "base_snapshot_sha256": intake.snapshot_sha256,
                "plan_sha256": intake.snapshot["plan_sha256"], "proof_policy": PROOF_POLICY}
    if set(value) != set(expected) | {"infrastructure_sha256_by_file"} or any(
            value[k] != v for k, v in expected.items()):
        raise IntegrityError("DEPTH3_PROOF_ADDENDUM_BINDING_MISMATCH")
    source_map = value["infrastructure_sha256_by_file"]
    if not isinstance(source_map, dict) or set(source_map) != _expected_files():
        raise IntegrityError("DEPTH3_PROOF_SOURCE_COVERAGE_MISMATCH")
    route._verify_files(source_map, route.ROOT)
    return source_map


def validate_preparation():
    """Check only draft bindings in the real disabled state."""
    body, snapshot_sha256, plan = route.validate_preparation()
    intake = route.Intake(snapshot_sha256, "", {}, body["model"], plan, body)
    raw = ADDENDUM.read_bytes()
    source_map = validate_addendum(raw, intake)
    return {"status": "DRAFT_PREPARED_DEPTH3_PROOF_EXECUTION", "snapshot_sha256": snapshot_sha256,
            "depth3_proof_addendum_sha256": route.sha256(raw).hexdigest(),
            "bound_proof_sources": len(source_map), "counts": plan["counts"]}


@dataclass(frozen=True)
class ExecutionBinding:
    intake: route.Intake
    addendum_sha256: str
    source_map: dict

    def live(self):
        snapshot_hash = assert_base_live(self.intake)
        if route.digest_file(READINESS_RECEIPT) != self.intake.approval["approved_readiness_sha256"]:
            raise IntegrityError("READINESS_ATTESTATION_MISMATCH")
        if route.digest_file(ADDENDUM) != self.addendum_sha256:
            raise IntegrityError("DEPTH3_PROOF_ADDENDUM_CHANGED")
        route._verify_files(self.source_map, route.ROOT)
        return snapshot_hash


def authorize_successor(namespace):
    """Require the base gate, then an explicitly approved depth-3 addendum."""
    intake = route.authorize_request(namespace)
    if not READINESS_RECEIPT.is_file():
        raise route.RouteDenied("READINESS_ATTESTATION_REQUIRED")
    raw = READINESS_RECEIPT.read_bytes()
    if route.sha256(raw).hexdigest() != intake.approval["approved_readiness_sha256"]:
        raise IntegrityError("READINESS_ATTESTATION_MISMATCH")
    receipt = route.parse_document(raw.decode("utf-8"))
    if (receipt.get("status") != "READY_TO_FREEZE" or receipt.get("snapshot_sha256") != intake.snapshot_sha256
            or receipt.get("plan_sha256") != intake.snapshot["plan_sha256"]):
        raise route.RouteDenied("READINESS_ATTESTATION_REQUIRED")
    expected_sha256 = receipt.get("depth3_proof_addendum_sha256")
    if not route.hex_sha256(expected_sha256) or not ADDENDUM.is_file():
        raise route.RouteDenied("DEPTH3_PROOF_ADDENDUM_APPROVAL_REQUIRED")
    addendum = ADDENDUM.read_bytes()
    if route.sha256(addendum).hexdigest() != expected_sha256:
        raise IntegrityError("DEPTH3_PROOF_ADDENDUM_BINDING_MISMATCH")
    binding = ExecutionBinding(intake, expected_sha256, validate_addendum(addendum, intake))
    binding.live()
    return binding


def _key_from_environment():
    variable = os.environ.pop("METHOD_HOLDOUT_TRANSACTION_KEY_FILE", None)
    if not variable:
        raise route.RouteDenied("TRANSACTION_KEY_CUSTODY_REQUIRED")
    file = Path(variable).resolve(strict=True)
    if file.is_relative_to(route.ROOT):
        raise route.IntegrityError("Transaction key must be held outside the workspace")
    key = file.read_bytes()
    if len(key) < 32:
        raise route.IntegrityError("Transaction signing key is too short")
    return key


class FlatReference:
    """Reuse the base route's independent full reference and warm query result."""

    def __init__(self):
        self.engine = self.key = self.result = None

    def rank(self, public_reference, depth, k):
        if self.engine is None:
            from unseen_verifier import FrozenFlatReference
            self.engine = FrozenFlatReference()
        key = (route.object_digest(vars(public_reference.view)), depth, k)
        if key != self.key:
            self.result = self.engine.rank(public_reference, depth, k)
            self.key = key
        return self.result


def needs_depth3_proof(outcome):
    from cover_verifier import EXACT_CLAIMS

    if outcome["status"] in {"ABNORMAL_EXIT", "BLOCKED"}:
        return False
    search = outcome.get("search")
    if search is not None:
        return any(c.get("status") in EXACT_CLAIMS for c in search["cuts"].values())
    return any(v["cut"].get("status") in EXACT_CLAIMS
               for v in outcome.get("preserved_checkpoints", {}).values())


def verify_prior_depth3(prior, identity, query, public, cache):
    """An authenticated prior transaction is skipped only after proof revalidation."""
    certificate = prior.get("certificate") or {}
    claimed = certificate.get("independent_checkpoints", {})
    shas = {cut.get("compressed_proof_sha256") for cut in claimed.values() if cut["status"] in EXACT}
    if len(shas) > 1 or any(not route.hex_sha256(sha) for sha in shas):
        raise IntegrityError("Prior transaction has no unique archived depth-3 proof")
    if prior["status"] in EXACT and not shas:
        raise IntegrityError("Prior exact transaction lacks an archived depth-3 proof")
    shared = cache.verify_cached(query, public, next(iter(shas))) if shas else None
    status, new_certificate = adjudicate(query, public, identity, prior["detail"], shared)
    if (status, new_certificate) != (prior["status"], prior.get("certificate")):
        raise IntegrityError("Prior depth-3 proof or candidate stream changed")


def refine_depth3(outcome, identity, query, public, cache):
    """Receive a supervised measurement and independently adjudicate its exact claims."""
    from method_proof_cache import ProofUnavailable

    shared = None
    if needs_depth3_proof(outcome):
        try:
            shared = cache.load_or_prove(query, public)
        except ProofUnavailable as exc:
            outcome = dict(outcome, independent_proof_unavailable=str(exc))
    status, certificate = adjudicate(query, public, identity, outcome, shared)
    return status, certificate, outcome


def execute_with_depth3_proof(namespace, phase):
    """Run the old schedule and execution stack under an explicitly approved addendum."""
    if type(phase) is not int or phase not in (1, 2, 3):
        raise ValueError("Unsupported holdout phase")
    binding = authorize_successor(namespace)
    intake = binding.intake
    key = _key_from_environment()
    release = route.Release(intake)
    # A different addendum can never mix with an earlier transaction or proof cache.
    scope = route.RESULT_ROOT / "proof-bound-v1" / binding.addendum_sha256
    if any(path.resolve() != path for path in (route.RESULT_ROOT, scope, scope/"attempts",
                                               scope/"depth3_proofs", scope/"ipc")):
        raise IntegrityError("Authorized result scope is redirected")
    store = TransactionStore(scope / "attempts", intake.snapshot_sha256, key, binding.live)
    from method_proof_cache import ProofCache

    cache = ProofCache(scope / "depth3_proofs", key, binding.addendum_sha256, binding.live)
    flat = FlatReference()
    done = skipped = 0
    with ExitStack() as stack:
        supervisor = None
        for slot, method in route.method_schedule(intake.plan, phase):
            binding.live()
            raw, instance = release.read(slot)
            payload = worker_payload(slot, raw)
            depth = slot["effective_depth"]
            method_sha256 = route.object_digest({
                "candidate_source_tree_sha256": intake.snapshot["candidate_source_tree_sha256"],
                "snapshot_sha256": intake.snapshot_sha256, "method": method,
            })
            identity = AttemptIdentity(slot["query_id"], method, depth, instance.instance_hash,
                                       payload["serialized_sha256"], method_sha256, intake.snapshot["plan_sha256"])
            query = (QueryBinding(identity.slot_id, instance.namespace, identity.serialized_sha256,
                                  identity.instance_hash, instance.public_hash, intake.snapshot_sha256,
                                  intake.snapshot["candidate_source_tree_sha256"], identity.plan_sha256)
                     if depth == 3 else None)
            prior = store.read(identity)
            if prior is not None:
                if prior["status"] in ("BLOCKED", "UNSOUND"):
                    raise IntegrityError("Existing transaction blocks this execution phase")
                if query is not None:
                    verify_prior_depth3(prior, identity, query, instance.public, cache)
                skipped += 1
                continue
            if supervisor is None:
                lane = "graph" if phase == 3 else "synth"
                startup = {"lane": lane, "engineering": False}
                if lane == "graph":
                    startup.update(payload)
                supervisor = WindowsWarmSupervisor(
                    scope / "ipc", route.SNAPSHOT_PATH,
                    [sys.executable, "-B", str(route.HERE / "holdout_worker.py")],
                    startup, verify_binding=binding.live,
                )
                stack.callback(supervisor.close)
            measured = supervisor.run(dict(payload, method=method), formal_budget(depth))
            if query is None:
                status, certificate = refine_base(measured, instance, depth, flat)
            else:
                # Native online metrics are sealed before this independent proof stage.
                status, certificate, measured = refine_depth3(measured, identity, query, instance.public, cache)
            store.commit(identity, raw, bind_result(identity, intake.snapshot_sha256, status,
                                                    certificate=certificate, detail=measured))
            done += 1
            if status in ("BLOCKED", "UNSOUND"):
                raise IntegrityError("Independent checkpoint verification blocked the phase")
    return {"terminal_attempts": done, "revalidated_skips": skipped, "phase": phase,
            "depth3_proof_addendum_sha256": binding.addendum_sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default=route.NAMESPACE)
    parser.add_argument("--phase", type=int, choices=(1, 2, 3), default=1)
    preparation = parser.add_mutually_exclusive_group()
    preparation.add_argument("--draft-addendum", action="store_true")
    preparation.add_argument("--validate-preparation", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.draft_addendum:
            result = build_addendum()
        elif args.validate_preparation:
            result = validate_preparation()
        else:
            result = execute_with_depth3_proof(args.namespace, args.phase)
    except (route.RouteDenied, route.IntegrityError, IntegrityError, OSError, ValueError) as exc:
        print(json.dumps({"status": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Detached depth-3 referee for authenticated attempts and one shared public proof.

The caller owns admission, supervision, atomic storage, and the executable snapshot.
Importing this module does not open a release, generate input, or run any method.
"""

from dataclasses import asdict, dataclass
import gzip
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

from symbolic_format import K_VALUES, digest
from cover_verifier import (BLOCKED, CAPPED, CAPPED_CLAIMS, EXACT_CLAIMS, FULL,
                            MAX_PROOF_BYTES, SHORT)
from holdout_transactions import AttemptIdentity, IntegrityError, decode
from src.instances import digest as public_digest
from symbolic_verifier import verify_symbolic
from unseen_verifier import PublicReference, compare_rows, exact_cut


METHODS = frozenset({
    "CURRENT_ON_DEMAND_GRAMMAR_SEARCH",
    "GENERIC_ABSTRACT_BEST_FIRST",
    "NO_EARLY_SEMANTIC_DEDUP",
    "GENERIC_BOUND_ONLY",
    "DEFER_CAPABILITY_PRUNING",
    "WEAK_STATE_TIME_RESOURCE_ENVELOPE",
    "NO_LAZY_STOP",
    "NO_SEARCH_TIME_DOMAIN_NORMALIZATION",
})
EXACT = frozenset((FULL, SHORT))
_ISSUER = object()


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def is_hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class QueryBinding:
    """Identity and digests constructed from an admitted depth-3 release slot."""

    query_id: str
    namespace: str
    serialized_sha256: str
    instance_hash: str
    public_hash: str
    snapshot_sha256: str
    candidate_source_tree_sha256: str
    plan_sha256: str

    def __post_init__(self):
        require(type(self.query_id) is str and bool(self.query_id), "Empty depth-3 identity")
        require(self.namespace in {"GENSPACE-METHOD-HOLDOUT-V1", "GENSPACE-FAIL-01-PILOT",
                                   "GENSPACE-FAIL-01-ENGINEERING", "GENSPACE-FAIL-01-ENGINEERING-SHADOW"},
                "Unsupported depth-3 source namespace")
        fields = asdict(self)
        require(all(is_hash(v) for k, v in fields.items() if k not in {"query_id", "namespace"}),
                "Invalid trusted identity digest")

    def method_digest(self, method):
        require(method in METHODS, "Unsupported depth-3 method")
        return digest({
            "candidate_source_tree_sha256": self.candidate_source_tree_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "method": method,
        })

    def check_attempt(self, attempt):
        require(isinstance(attempt, AttemptIdentity), "Missing authenticated attempt identity")
        require((attempt.slot_id, attempt.effective_depth, attempt.instance_hash,
                 attempt.serialized_sha256, attempt.plan_sha256, attempt.method_sha256)
                == (self.query_id, 3, self.instance_hash, self.serialized_sha256,
                    self.plan_sha256, self.method_digest(attempt.method)),
                "Attempt does not belong to the admitted query, method or snapshot")

    def check_public(self, public):
        require(public.configuration["composition_depth"] == 2 and
                public_digest(asdict(public)) == self.public_hash,
                "Public projection does not belong to the admitted depth-3 query")

    def check_proof_binding(self, binding):
        required = {
            "instance_id": self.query_id,
            "serialized_sha256": self.serialized_sha256,
            "public_hash": self.public_hash,
            "effective_depth": 3,
            "snapshot_sha256": self.snapshot_sha256,
            "candidate_source_tree_sha256": self.candidate_source_tree_sha256,
        }
        if self.namespace == "GENSPACE-METHOD-HOLDOUT-V1":
            required.update(namespace=self.namespace, instance_hash=self.instance_hash,
                            plan_sha256=self.plan_sha256)
        require(all(binding.get(k) == v for k, v in required.items()),
                "Shared proof belongs to a different query, plan or snapshot")


@dataclass(frozen=True)
class _VerifiedPublicProof:
    """Transient result of executing the local independent proof checker."""

    issuer: object
    query: QueryBinding
    compressed_sha256: str
    prefix: tuple
    cut_statuses: tuple
    exhausted: bool


def authenticate_shared_proof(query, public, path, expected_sha256, expected_binding,
                              source_prefix, source_cuts, sample):
    """Read one immutable byte sequence, validate it, and independently check its DAG."""
    query.check_public(public)
    query.check_proof_binding(expected_binding)
    require(is_hash(expected_sha256), "Invalid pinned proof archive SHA-256")
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_PROOF_BYTES + 1)
    require(len(raw) <= MAX_PROOF_BYTES, "Compressed proof exceeds byte ceiling")
    measured_sha256 = sha256(raw).hexdigest()
    require(measured_sha256 == expected_sha256, "Proof archive SHA-256 mismatch")
    with gzip.GzipFile(fileobj=BytesIO(raw), mode="rb") as stream:
        expanded = stream.read(MAX_PROOF_BYTES + 1)
    require(len(expanded) <= MAX_PROOF_BYTES, "Expanded proof exceeds byte ceiling")
    proof = decode(expanded)
    result = verify_symbolic(public, proof, expected_binding, source_prefix, source_cuts, sample)
    statuses = tuple((int(k), status) for k, status in result["checkpoints"].items())
    require(statuses and all(status in EXACT for _, status in statuses),
            "Shared proof has no independently verified checkpoint")
    k = str(statuses[-1][0])
    prefix = PublicReference(public).validated_prefix(source_prefix, 3)
    covered, _ = exact_cut(int(k), source_cuts[k], prefix)
    return _VerifiedPublicProof(_ISSUER, query, measured_sha256, tuple(covered),
                                statuses, proof["checkpoints"][k]["exhausted"])


def _native_evidence(attempt, outcome):
    search = outcome.get("search")
    preserved = outcome.get("preserved_checkpoints", {})
    require(set(preserved) <= set(map(str, K_VALUES)), "Invalid preserved checkpoint key")
    if search is not None:
        require((search["method"], search["effective_depth"], search["instance_hash"],
                 search["serialized_sha256"])
                == (attempt.method, 3, attempt.instance_hash, attempt.serialized_sha256),
                "Supervised candidate stream does not match attempt")
        require(set(search["cuts"]) == set(map(str, K_VALUES)),
                "Supervised candidate stream lacks prescribed checkpoints")
        return search["prefix"], search["cuts"], preserved
    require(outcome["status"] != "PROOF_PENDING", "Missing supervised candidate stream")
    last = preserved[max(preserved, key=int)] if preserved else None
    return (last["prefix"] if last else [], {
        str(k): (preserved[str(k)]["cut"] if str(k) in preserved else {"status": CAPPED})
        for k in K_VALUES
    }, preserved)


def adjudicate(query, public, attempt, outcome, shared=None):
    """Refine a supervisor-authenticated attempt, obtaining no data from disk."""
    query.check_public(public)
    query.check_attempt(attempt)
    parent_status = outcome["status"]
    require(parent_status in {"PROOF_PENDING", "BLOCKED", "ABNORMAL_EXIT", CAPPED},
            "Attempt has no recognized parent-supervised terminal state")
    if parent_status in {"BLOCKED", "ABNORMAL_EXIT"}:
        return parent_status, None
    if parent_status == CAPPED:
        require(type(outcome.get("reason")) is str and bool(outcome["reason"]),
                "Resource limit lacks a parent-supervised reason")
    if shared is not None:
        require(isinstance(shared, _VerifiedPublicProof) and shared.issuer is _ISSUER and
                shared.query == query, "Shared checker receipt does not belong to the admitted query")
    prefix, cuts, preserved = _native_evidence(attempt, outcome)
    checks = {}
    try:
        reference = PublicReference(public)
        rows = reference.validated_prefix(prefix, 3)
        if len(rows) > max(K_VALUES):
            raise ValueError("Supervised prefix exceeds prescribed maximum")
        if shared:
            compare_rows(rows[:len(shared.prefix)], shared.prefix[:len(rows)])
            if shared.exhausted and len(rows) > len(shared.prefix):
                raise ValueError("Supervised prefix exceeds independently exhausted domain")
        for k in K_VALUES:
            name = str(k)
            cut = cuts[name]
            claim = cut.get("status")
            if claim in CAPPED_CLAIMS:
                if parent_status != CAPPED:
                    raise ValueError("Native resource limit lacks parent confirmation")
                checks[name] = {"status": CAPPED, "reason": outcome["reason"]}
                continue
            if claim not in EXACT_CLAIMS:
                raise ValueError("Unsound native exact claim")
            actual, short = exact_cut(k, cut, rows)
            if name in preserved:
                individual = reference.validated_prefix(preserved[name]["prefix"], 3)
                compare_rows(individual, actual)
                if preserved[name]["cut"] != cut:
                    raise ValueError("Preserved and terminal checkpoint claims conflict")
            if shared is None or (not shared.exhausted and k > len(shared.prefix)):
                checks[name] = {"status": BLOCKED, "reason": "Missing independently covered cutoff"}
                continue
            compare_rows(actual, shared.prefix[:k])
            if short and not shared.exhausted:
                raise ValueError("A short stream lacks independent domain exhaustion")
            if cut.get("full_domain_exhausted") is True and (
                    not shared.exhausted or len(actual) != len(shared.prefix)):
                raise ValueError("Native exhaustion contradicts the independently covered domain")
            checks[name] = {"status": SHORT if short else FULL, "returned": len(actual),
                            "proof": "independently-checked-shared-symbolic-depth3",
                            "compressed_proof_sha256": shared.compressed_sha256}
        if parent_status == CAPPED:
            status = CAPPED
        else:
            status = ("BLOCKED" if any(c["status"] == BLOCKED for c in checks.values())
                      else checks["500"]["status"])
    except (ValueError, KeyError, IndexError, TypeError, ArithmeticError, RecursionError) as exc:
        status = "UNSOUND"
        checks = {str(k): {"status": status, "reason": str(exc)} for k in K_VALUES}
    return status, {"status": status, "effective_depth": 3,
                    "independently_verified": status in EXACT, "independent_checkpoints": checks}

"""Bounded offline proof export over the frozen public Depth 3 DSL.

This module does not invoke a negotiation, a candidate ranker, or a sampler.
The sealed public prefix supplies the statements to prove, never proof axioms.
"""

from collections import Counter
from pathlib import Path
import json
import sys
from time import perf_counter


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "results" / "method_holdout_readiness"),
                str(ROOT / "results" / "grammar_gate"), str(ROOT / "results" / "method_dev_v1")]

from abstract_semantics import AbstractSemantics
from cover_verifier import expand, lower_bound, unavailable
from unseen_verifier import PublicReference, prefix_digest


CHECKPOINTS = ("10", "100", "500")
EXACT = frozenset(("EXACT_TOPK_CERTIFIED", "EXACT_TOPK_FULL_LENGTH", "EXACT_DOMAIN_EXHAUSTED_SHORT"))


class ExportLimit(RuntimeError):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(reason)


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


class CoverBuilder:
    """Independently partitions raw typed syntax for one public score cutoff."""

    def __init__(self, reference, grammar, boundary, budget):
        self.reference, self.grammar, self.boundary = reference, grammar, boundary
        self.budget = budget
        self.records = []
        self.interned = {}
        self.kind_counts = Counter()
        self.bytes_so_far = 0
        self.visited = 0

    def store(self, record):
        # Expansion identities have explicit contextual paths and child
        # indices. Closed rule rows can be reused in several contexts because
        # the checker repeats the rule application at every use.
        key = ("E", tuple(record[1])) if record[0] == "E" else tuple(record)
        if key not in self.interned:
            self.bytes_so_far += len(compact(record)) + 1
            if self.bytes_so_far >= self.budget.max_bytes:
                raise ExportLimit("PROOF_TOO_LARGE", "encoded proof node body exceeded byte budget")
            self.interned[key] = len(self.records)
            self.records.append(record)
        return self.interned[key]

    def visit(self, term):
        self.budget.guard()
        self.visited += 1
        if unavailable(term, self.reference):
            record = ["I"]
        elif self.grammar.envelope(term).max_groups == 0:
            record = ["X"]
        elif self.boundary is not None and (bound := lower_bound(self.reference, self.grammar, term)) > self.boundary:
            record = ["B", bound]
        elif self.grammar.is_complete(term):
            record = ["C"]
        else:
            options = expand(term, self.grammar, self.reference)
            if not options:
                raise AssertionError("unresolved typed term has no descendants")
            record = ["E", [self.visit(child) for child in options]]
        self.kind_counts[record[0]] += 1
        return self.store(record)


class ExportBudget:
    def __init__(self, wall_s, max_nodes, max_bytes, rss_bytes, sample):
        if wall_s <= 0 or max_nodes <= 0 or max_bytes <= 0 or rss_bytes <= 0:
            raise ValueError("proof budget must be positive")
        self.started = perf_counter()
        self.wall_s, self.max_nodes, self.max_bytes = wall_s, max_nodes, max_bytes
        self.rss_bytes, self.sample = rss_bytes, sample
        self.visits, self.peak_rss = 0, 0

    def observe_memory(self):
        if self.sample is not None:
            self.peak_rss = max(self.peak_rss, self.sample())
            if self.peak_rss > self.rss_bytes:
                raise ExportLimit("PROOF_TOO_LARGE", "proof process working-set budget exceeded")

    def guard(self):
        if perf_counter() - self.started >= self.wall_s:
            raise ExportLimit("PROOF_GENERATION_TOO_SLOW", "offline proof emission wall-clock budget exceeded")
        if self.visits >= self.max_nodes:
            raise ExportLimit("PROOF_TOO_LARGE", "typed coverage visitation budget exhausted")
        if self.visits % 256 == 0:
            self.observe_memory()
        self.visits += 1


def produce(public, public_hash, sealed_rows, cuts, *, snapshot_sha256, sealed_case_sha256,
            wall_s=30, max_nodes=200_000, max_bytes=32 * 1024**2, rss_bytes=2 * 1024**3, sample=None,
            requested_ks=CHECKPOINTS):
    """Return the widest completed single-cover DAG and auditable export metadata.

    A shared cover for a larger K can also check smaller K. As K grows, two
    different proof contexts must not be substituted by just comparing their
    hashes. When a later attempt is limited, the earlier complete cover is
    retained unchanged. No incomplete cover is returned.
    """
    budget = ExportBudget(wall_s, max_nodes, max_bytes, rss_bytes, sample)
    reference = PublicReference(public)
    validated = reference.validated_prefix(sealed_rows, 3)
    grammar = AbstractSemantics(public, 3)
    proof = None
    trials = {}
    last = None
    # Several short-domain checkpoints can carry the identical prefix. A
    # completed exhaustiveness proof for the first such checkpoint can serve
    # every later request without repeating raw syntax verification.
    if not requested_ks or tuple(k for k in CHECKPOINTS if k in requested_ks) != tuple(requested_ks):
        raise ValueError("checkpoints must be an ordered subset of K=10,100,500")
    for text_k in requested_ks:
        cut = cuts[text_k]
        if cut["status"] not in EXACT:
            trials[text_k] = {"status": "NOT_CERTIFIED_RESOURCE_LIMIT", "reason": "no exact online claim"}
            continue
        k = int(text_k)
        count = cut["returned"]
        if type(count) is not int or count < 0 or count > min(len(validated), k):
            raise ValueError("invalid sealed cutoff cardinality")
        short = count < k or cut.get("full_domain_exhausted") is True
        if short and cut.get("full_domain_exhausted") is not True:
            raise ValueError("sealed short request has no exhaustion claim")
        prior_exhausted = (last is not None and last["claims_exhaustion"] and last["count"] == count)
        if prior_exhausted:
            # Bind the same explicitly exhaustive graph to the widest request.
            proof["coverage_k"] = k
            trials[text_k] = {"status": "EMITTED", "seconds": 0., "reused_complete_domain_dag": True}
            continue
        begin = perf_counter()
        boundary = None if short else validated[count-1][1]
        builder = CoverBuilder(reference, grammar, boundary, budget)
        try:
            root = builder.visit(grammar.root)
            candidate = {"version": "typed-cover-dag-v2", "public_hash": public_hash,
                         "effective_depth": 3, "snapshot_sha256": snapshot_sha256,
                         "sealed_case_sha256": sealed_case_sha256, "coverage_k": k,
                         "prefix_sha256": prefix_digest(validated[:count]),
                         "capabilities": sorted(reference.roles), "root": root, "nodes": builder.records}
            if len(compact(candidate)) > max_bytes:
                raise ExportLimit("PROOF_TOO_LARGE", "encoded proof exceeds byte budget")
            budget.observe_memory()
            if perf_counter() - budget.started >= wall_s:
                raise ExportLimit("PROOF_GENERATION_TOO_SLOW", "proof serialization crossed deadline")
        except ExportLimit as exc:
            trials[text_k] = {"status": exc.status, "reason": exc.reason,
                              "logical_nodes": builder.visited, "unique_nodes": len(builder.records),
                              "seconds": perf_counter() - begin}
            break
        proof = candidate
        last = {"claims_exhaustion": short, "count": count, "logical_nodes": builder.visited,
                "unique_nodes": len(builder.records), "node_kinds": dict(builder.kind_counts)}
        trials[text_k] = {"status": "EMITTED", "seconds": perf_counter() - begin}

    return proof, {"status": "EMITTED" if proof is not None else "MISSING",
                   "proof_generation_s": perf_counter() - budget.started,
                   "peak_proof_generation_rss_bytes": budget.peak_rss or None,
                   "visited_work": budget.visits, "coverage_k": proof["coverage_k"] if proof else None,
                   "logical_nodes": last["logical_nodes"] if last else 0,
                   "unique_nodes": last["unique_nodes"] if last else 0,
                   "shared_nodes": last["logical_nodes"] - last["unique_nodes"] if last else 0,
                   "node_kinds": last["node_kinds"] if last else {}, "trials": trials}

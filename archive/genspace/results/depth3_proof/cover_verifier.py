"""Root-anchored independent typed-cover certificate verifier."""

from dataclasses import asdict
from functools import lru_cache
import gzip
import json
from math import isfinite
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "results" / "method_holdout_readiness")]
from unseen_verifier import (AbstractSemantics, ClauseHole, PublicReference, RejectedEvidence,
                             children_and_value, compare_rows, exact_cut, prefix_digest, rank_terms,
                             score_bits)
from src.engine import STRUCTURAL
from src.instances import digest
from src.models import Delay, If, Offload, Sequence, Static, ValidFor

VERSION = "typed-cover-dag-v2"
FULL = "EXACT_TOPK_FULL_LENGTH"
SHORT = "EXACT_DOMAIN_EXHAUSTED_SHORT"
CAPPED = "NOT_CERTIFIED_RESOURCE_LIMIT"
BLOCKED = "BLOCKED_MISSING_INDEPENDENT_FRONTIER_PROOF"
UNSOUND = "PROOF_UNSOUND"
EXACT_CLAIMS = frozenset((FULL, SHORT, "EXACT_TOPK_CERTIFIED"))
CAPPED_CLAIMS = frozenset((CAPPED, "NOT_CERTIFIED_WITHIN_BUDGET"))
PROOF_TOO_LARGE = "PROOF_TOO_LARGE"
CHECKPOINTS = frozenset((10, 100, 500))
MAX_CONTEXT_VISITS = 500_000
MAX_PROOF_BYTES = 96 * 1024 * 1024
UNARY = (Delay, ValidFor, Offload)
BINARY = (If, Sequence)
OPERATORS = ((If, "conditions"), (Sequence, "durations"), (Delay, "offsets"),
             (ValidFor, "intervals"), (Offload, "offload_levels"))
PROOF_KEYS = {"version", "public_hash", "effective_depth", "snapshot_sha256",
              "sealed_case_sha256", "prefix_sha256", "capabilities", "coverage_k", "root", "nodes"}


def unavailable(term, ref):
    kind = type(term)
    if kind in (ClauseHole, Static):
        return False
    _, operands = children_and_value(term)
    return not STRUCTURAL[kind] <= ref.roles or any(unavailable(c, ref) for c in operands)


def expand(term, grammar, ref):
    """Partition the first clause hole, including explicitly excluded productions."""
    kind = type(term)
    if kind is ClauseHole:
        choices = [Static(p) for p in ref.public.b2_profiles]
        if term.remaining_depth:
            child = grammar.clause_holes[term.remaining_depth - 1]
            for constructor, field in OPERATORS:
                for parameter in getattr(ref.public, field):
                    if constructor in BINARY:
                        choices.append(constructor(parameter, child, child))
                    else:
                        choices.append(constructor(parameter, child))
        return tuple(choices)
    if kind is Static:
        return ()
    value, operands = children_and_value(term)
    for i, child in enumerate(operands):
        alternatives = expand(child, grammar, ref)
        if alternatives:
            return tuple(kind(value, *operands[:i], c, *operands[i + 1:]) for c in alternatives)
    return ()


class PublicBound:
    """Recompute FLAT lower bounds without invoking either ranking cursor."""

    def __init__(self, reference, grammar):
        self.ref = reference
        self.grammar = grammar
        self.capacities = tuple(reference.capacity[t, s] for t in range(reference.public.horizon)
                                for s in reference.public.states)
        self.demand_terms = lru_cache(maxsize=4096)(self._terms)
        self.cell_min = lru_cache(maxsize=8192)(self._cell_minimum)
        self.cells = tuple(
            tuple(tuple(self._joint_cell(self._terms(j, loads), float(profile.quality))
                        for profile, loads in zip(grammar.profiles, level, strict=True))
                  for level in grammar.demand_basis)
            for j in range(len(self.capacities))
        )
        self.idle = tuple(self._joint_cell(self._terms(j, (0., 0., 0.)), 0.) for j in range(len(self.capacities)))
        max_excess = max(v for j in range(len(self.capacities)) for level in grammar.demand_basis
                         for loads in level for v in self._terms(j, loads)[0])
        a, b, c = map(float, reference.costs[-1])
        max_cost = float(reference.execution[-1]) + ((a+b)+c)
        # The domain and operation count are the ones proved in GRAMMAR_BOUND_SPEC.md.
        self.allowance = 2.**-38 * (32. + 32.*max_excess + 12.*max_cost)
        if not isfinite(self.allowance):
            raise RejectedEvidence("Unsupported finite FLAT bound domain")

    def _terms(self, position, demands):
        cap = self.capacities[position]
        excess = tuple((d-c)/max(c, 1.e-9) for d,c in zip(demands, cap, strict=True))
        return tuple(max(x, 0.) for x in excess), tuple(max(-1., min(-x, 1.)) for x in excess)

    @staticmethod
    def _joint_cell(terms, quality):
        v,m = terms
        return (((v[0]+v[1])+v[2])/18. - 0.025*((m[0]+m[1])+m[2])/18. - 0.08*quality/6.)

    def _cell_minimum(self, position, local, edge, may_idle):
        lo = self.idle[position] if may_idle else float("inf")
        for mask, table in zip((local, edge), self.cells[position], strict=True):
            while mask:
                bit = mask & -mask
                lo = min(lo, table[bit.bit_length()-1])
                mask ^= bit
        return lo

    def envelope(self, envelope):
        violation = margin = quality = cost = joint = 0.
        for position, cell in enumerate(envelope.cells):
            v,m = self.demand_terms(position, cell.demand_min)
            for x in v:
                violation += x
            for x in m:
                margin += x
            quality += cell.quality_max
            cost += cell.min_cost
            joint += self.cell_min(position, cell.local_profiles, cell.edge_profiles, cell.may_idle)
        component = violation/18. - 0.025*(margin/18.) + 0.02*(cost/6.) + 0.08*(1.-quality/6.)
        component += 0.01 * envelope.min_groups
        joint += 0.02*(cost/6.) + 0.08 + 0.01*envelope.min_groups
        result = max(component, joint - self.allowance)
        score_bits(result)
        return result


@lru_cache(maxsize=2)
def bound_checker(reference, grammar):
    return PublicBound(reference, grammar)


def lower_bound(ref, grammar, term):
    return bound_checker(ref, grammar).envelope(grammar.envelope(term))


def _unique_pairs(pairs):
    data = dict(pairs)
    if len(data) != len(pairs):
        raise RejectedEvidence("Duplicate JSON key")
    return data


def _nonfinite(value):
    raise RejectedEvidence("Non-finite JSON constant: " + value)


def read_proof(path):
    """Bound final bytes as well as decompressed bytes before parsing."""
    path = Path(path)
    if path.stat().st_size > MAX_PROOF_BYTES:
        raise OverflowError("Certificate file exceeds supported byte ceiling")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        value = stream.read(MAX_PROOF_BYTES+1)
    if len(value) > MAX_PROOF_BYTES:
        raise OverflowError("Uncompressed certificate exceeds supported byte ceiling")
    return json.loads(value, object_pairs_hook=_unique_pairs, parse_constant=_nonfinite)


def _covered_prefix(ref, proof, rows, coverage_cut, visits):
    grammar = AbstractSemantics(ref.public, 3)
    nodes = proof["nodes"]
    if not isinstance(nodes, list) or not nodes:
        raise RejectedEvidence("Proof nodes must be a nonempty array")
    if len(nodes) > MAX_CONTEXT_VISITS:
        raise OverflowError("Stored certificate exceeds supported node ceiling")
    target_k = proof["coverage_k"]
    limit = None if coverage_cut["full_domain_exhausted"] else rows[-1][1]
    reached, active = set(), set()
    candidates, keys_by_leaf, merged = [], {}, []
    counts = {"EXPAND": 0, "COMPLETE_CANDIDATE": 0, "BOUND_PRUNED": 0, "CAPABILITY_IMPOSSIBLE": 0,
              "EXHAUSTED": 0, "CANONICALLY_MERGED": 0}

    def node_number(value):
        if type(value) is not int or not 0 <= value < len(nodes):
            raise RejectedEvidence("Invalid proof node reference")
        return value

    def visit(term, index):
        index = node_number(index)
        visits[0] += 1
        if visits[0] > MAX_CONTEXT_VISITS:
            raise OverflowError("Expanded proof contexts exceed supported visit ceiling")
        if index in active:
            raise RejectedEvidence("Cyclic covering dependency")
        reached.add(index)
        frame = nodes[index]
        if not isinstance(frame, list) or not frame:
            raise RejectedEvidence("Malformed proof frame")
        kind, *data = frame
        excluded = unavailable(term, ref)
        if kind == "I" and not data and excluded:
            counts["CAPABILITY_IMPOSSIBLE"] += 1
            return
        if excluded:
            raise RejectedEvidence("Unavailable production lacks its capability proof")
        if kind == "E" and len(data) == 1 and isinstance(data[0], list):
            alternatives = expand(term, grammar, ref)
            if not alternatives or len(alternatives) != len(data[0]):
                raise RejectedEvidence("Missing or extra constructor/parameter alternatives")
            counts["EXPAND"] += 1
            active.add(index)
            for child, child_index in zip(alternatives, data[0], strict=True):
                visit(child, child_index)
            active.remove(index)
        elif kind == "B" and len(data) == 1 and limit is not None:
            exact = lower_bound(ref, grammar, term)
            if score_bits(data[0]) != score_bits(exact) or exact <= limit:
                raise RejectedEvidence("Unsafe, altered, or tied child cutoff bound")
            counts["BOUND_PRUNED"] += 1
        elif kind == "X" and not data and grammar.envelope(term).max_groups == 0:
            counts["EXHAUSTED"] += 1
        elif ((kind == "C" and not data) or (kind == "M" and len(data) == 1)) and grammar.is_complete(term):
            key = ref.encoder.encode(term)
            if len(key) != 49 or key[0] != 1:
                raise RejectedEvidence("Invalid typed derivation in cover proof")
            candidates.append(term)
            if kind == "C":
                keys_by_leaf.setdefault(index, set()).add(key)
                counts["COMPLETE_CANDIDATE"] += 1
            else:
                merged.append((node_number(data[0]), key))
                counts["CANONICALLY_MERGED"] += 1
        else:
            raise RejectedEvidence("Unknown or unjustified proof terminal")

    visit(grammar.root, proof["root"])
    if len(reached) != len(nodes):
        raise RejectedEvidence("Unreachable proof records")
    for target, key in merged:
        if keys_by_leaf.get(target) != {key}:
            raise RejectedEvidence("Merge target lacks an unambiguous equal complete canonical key")
    expected, total = rank_terms(ref, candidates, target_k)
    compare_rows(rows, expected)
    return expected, total, counts


def _unproved(cuts):
    return {str(k): {"status": CAPPED if c.get("status") in CAPPED_CLAIMS else BLOCKED}
            for k, c in cuts.items()}


def verify(ref_or_public, prefix, cuts, proof, *, snapshot_sha256, sealed_case_sha256):
    """Adjudicate a shared proof for the supplied archived public prefix."""
    observed = 0
    keys = tuple(str(k) for k in cuts)
    visits = [0]
    try:
        cut_map = {int(k): v for k, v in cuts.items()}
        if len(cut_map) != len(cuts) or not cut_map or set(cut_map)-CHECKPOINTS:
            raise RejectedEvidence("Unsupported or repeated checkpoint request")
        ref = ref_or_public if isinstance(ref_or_public, PublicReference) else PublicReference(ref_or_public)
        if ref.public.configuration["composition_depth"] != 2 or len(prefix) > 500:
            raise RejectedEvidence("Unexpected source depth or prefix size")
        rows = ref.validated_prefix(prefix, 3)
        if proof is None:
            return {"status": BLOCKED, "cuts": _unproved(cuts)}
        if not isinstance(proof, dict) or set(proof) != PROOF_KEYS:
            raise RejectedEvidence("Unknown certificate fields")
        target = proof["coverage_k"]
        if (proof["version"] != VERSION or proof["public_hash"] != digest(asdict(ref.public))
                or proof["effective_depth"] != 3 or proof["snapshot_sha256"] != snapshot_sha256
                or proof["sealed_case_sha256"] != sealed_case_sha256 or proof["capabilities"] != sorted(ref.roles)
                or type(target) is not int or target not in cut_map):
            raise RejectedEvidence("Snapshot, public scope, capabilities or checkpoint binding mismatch")
        coverage_cut = cut_map[target]
        if coverage_cut.get("status") not in EXACT_CLAIMS:
            raise RejectedEvidence("No original exact claim at cover boundary")
        coverage_rows, short = exact_cut(target, coverage_cut, rows)
        if short and not coverage_cut["full_domain_exhausted"]:
            raise RejectedEvidence("Missing short-domain exhaustion proof")
        if proof["prefix_sha256"] != prefix_digest(coverage_rows):
            raise RejectedEvidence("Shared coverage prefix mismatch")
        expected, total, counts = _covered_prefix(ref, proof, coverage_rows, coverage_cut, visits)
        observed = visits[0]
        result = {}
        for k, cut in sorted(cut_map.items()):
            if cut.get("status") in CAPPED_CLAIMS:
                result[str(k)] = {"status": CAPPED}
            elif k > target:
                result[str(k)] = {"status": BLOCKED}
            else:
                if cut.get("status") not in EXACT_CLAIMS:
                    raise RejectedEvidence("Unexpected source checkpoint status")
                actual, short = exact_cut(k, cut, rows)
                compare_rows(actual, expected[:k])
                if len(actual) != min(k, total):
                    raise RejectedEvidence("Short cut inconsistent with verified root coverage")
                if cut["full_domain_exhausted"] and (len(actual) != total or counts["BOUND_PRUNED"]):
                    raise RejectedEvidence("Exhaustion omits a part of the eligible grammar")
                result[str(k)] = {"status": SHORT if short else FULL, "returned": len(actual)}
        return {"status": BLOCKED if any(x["status"] == BLOCKED for x in result.values()) else "VERIFIED",
                "coverage_k": target, "cuts": result, "context_visits": observed, "stored_nodes": len(proof["nodes"]),
                "shared_context_visits": observed - len(proof["nodes"]), "terminals": counts}
    except OverflowError as exc:
        return {"status": PROOF_TOO_LARGE, "reason": str(exc), "context_visits": visits[0],
                "cuts": _unproved(cuts)}
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, RecursionError) as exc:
        return {"status": UNSOUND, "reason": str(exc), "context_visits": visits[0],
                "cuts": {k: {"status": UNSOUND} for k in keys}}

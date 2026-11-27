"""Compare actual generic heap bounds with independent tiny-domain descendants."""

from dataclasses import fields
import json
from pathlib import Path
from struct import pack
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), *(str(ROOT / "results" / name) for name in (
    "depth3", "grammar_gate", "grammar_dedup", "method_dev_v1",
))]

from abstract_semantics import ClauseHole, ProfileHole
from check_reduced_depth3 import FIXTURE, independent_complete, reduced_public
from generic_search import GenericCursor
from grammar_search import Limits
from src.engine import ast_depth, enumerate_compositions
from src.enumeration import public_domain, syntax_key
from src.instances import deserialize_instance
from src.models import Static
from src.state_machine import normalize


CASES = (
    ("conditional", ("conditions",), (0, -1), 2),
    ("conditional-delay", ("conditions", "offsets"), (0, -1), 2),
    ("validity-offload", ("intervals", "offload_levels"), (0, -1), 3),
    ("four-groups", ("conditions", "durations", "offsets", "offload_levels"), (-1,), 2),
)


def contains(partial, concrete, profile_index):
    if isinstance(partial, ClauseHole):
        return ast_depth(concrete) <= partial.remaining_depth
    if type(partial) is not type(concrete):
        return False
    if isinstance(partial, Static):
        if isinstance(partial.profile, ProfileHole):
            return bool(partial.profile.allowed_mask & (1 << profile_index[concrete.profile]))
        return partial == concrete
    for slot in fields(partial):
        left, right = getattr(partial, slot.name), getattr(concrete, slot.name)
        if hasattr(left, "__dataclass_fields__"):
            if not contains(left, right, profile_index):
                return False
        elif left != right:
            return False
    return True


def check_case(public, depth, strategy):
    encoder, witnesses, ordering, scores, syntax_count, _shapes = independent_complete(public, depth)
    assert syntax_count < 100
    completions = tuple((node, *scores[encoder.encode(node)]) for node in enumerate_compositions(
        public_domain(public), depth, public.capabilities,
    ))
    checks = {"frontier_terms": 0, "covering_terms": 0, "pruned_terms": 0}

    class AuditedGenericCursor(GenericCursor):
        def assess(self, node):
            envelope, score = super().assess(node)
            checks["frontier_terms"] += 1
            eligible = [
                concrete_score
                for concrete, concrete_score, groups in completions
                if 1 <= groups <= self.group_limit and contains(node, concrete, self.grammar.profile_index)
            ]
            if eligible:
                if score is None or score > min(eligible):
                    raise AssertionError("generic frontier bound skipped or exceeded an eligible descendant")
                checks["covering_terms"] += 1
            if score is None:
                checks["pruned_terms"] += 1
            return envelope, score

    cursor = AuditedGenericCursor(public, depth, Limits(60, 5000, 5000), strategy=strategy)
    for key, score in ordering:
        entry = cursor.next_contract()
        raw, witness = witnesses[key]
        assert entry.key == key and pack(">d", entry.score) == pack(">d", score)
        assert entry.raw_witness == raw and entry.witness == syntax_key(normalize(witness, public))
        frontier_min = cursor.metrics()["frontier_min_lb"]
        assert frontier_min is None or frontier_min > score
    assert cursor.next_contract() is None and cursor.exhausted
    return dict(raw_syntax=syntax_count, eligible_signatures=len(ordering), **checks)


def main():
    source = ROOT / "results" / "pilot" / "instances" / (FIXTURE + ".json")
    instance = deserialize_instance(source.read_text(encoding="utf-8"))
    rows = []
    for name, operators, profiles, depth in CASES:
        public = reduced_public(instance.public, operators, (), profiles)
        for strategy in ("mrv", "preorder"):
            rows.append(dict(scope=name, depth=depth, strategy=strategy,
                             **check_case(public, depth, strategy)))
    print(json.dumps({"status": "PASS", "source_fixture": FIXTURE, "checks": rows}, indent=2))


if __name__ == "__main__":
    main()

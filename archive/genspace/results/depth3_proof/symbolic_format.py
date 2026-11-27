"""Content identities and public term encoding for the symbolic proof lane."""

from hashlib import sha256
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "results"
sys.dont_write_bytecode = True
sys.path[:0] = [str(p) for p in (ROOT, ARCHIVE/"depth3", ARCHIVE/"grammar_gate",
                                ARCHIVE/"grammar_dedup", ARCHIVE/"method_dev_v1",
                                ARCHIVE/"method_holdout_readiness")]

from abstract_semantics import ClauseHole, ProfileHole
from src.models import Delay, If, Offload, Sequence, Static, ValidFor


FORMAT = "symbolic-typed-cover-dag-v2"
K_VALUES = (10, 100, 500)
OPERATORS = {cls.__name__: cls for cls in (Delay, If, Offload, Sequence, ValidFor)}


def dump(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(dump(value)).hexdigest()


def parts(node):
    if isinstance(node, If):
        return node.condition, (node.then_clause, node.else_clause)
    if isinstance(node, Sequence):
        return node.duration, (node.first, node.second)
    if isinstance(node, Delay):
        return node.offset, (node.clause,)
    if isinstance(node, ValidFor):
        return node.interval, (node.clause,)
    if isinstance(node, Offload):
        return node.level, (node.clause,)
    if isinstance(node, Static):
        return node.profile, ()
    raise ValueError("Unsupported public syntax")


def descriptor(node):
    if isinstance(node, ClauseHole):
        return ("Clause", node.remaining_depth)
    if isinstance(node, Static):
        if not isinstance(node.profile, ProfileHole):
            raise ValueError("Symbolic skeleton has a fixed profile")
        return ("Profile", node.profile.allowed_mask)
    value, children = parts(node)
    return (type(node).__name__, value, *(descriptor(child) for child in children))


def template_descriptor(prefix, cells, visible, groups):
    return (prefix.hex(), tuple(cells), visible, groups)

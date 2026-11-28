#!/usr/bin/env python3
"""Verify the exported G1-A task tables and plans against the execution audit."""

import csv
import hashlib
import json
from pathlib import Path


EVIDENCE = (Path(__file__).resolve().parents[1] / "rdinp" / "experiments" /
            "durable-worker" / "evidence" / "g1a-20261128")


def verify():
    verification = json.loads((EVIDENCE / "g1a-execution-verification-v2.json").read_bytes())
    studies = verification["studies"]
    names = ("study-4x1", "study-8x2-retry-01")
    if set(studies) != set(names):
        raise ValueError("Unexpected G1-A study set")
    for name in names:
        record = studies[name]
        for filename, digest in (("plan.json", "plan_digest"), ("per_task.csv", "table_digest")):
            path = EVIDENCE / name / filename
            if hashlib.sha256(path.read_bytes()).hexdigest() != record[digest]:
                raise ValueError(f"G1-A checksum mismatch: {name}/{filename}")
        with (EVIDENCE / name / "per_task.csv").open(encoding="utf-8", newline="") as file:
            rows = sum(1 for _ in csv.DictReader(file))
        if record["pairs"] != 72 or rows != record["rows"] or rows != 2592:
            raise ValueError(f"G1-A coverage mismatch: {name}")
    print("Verified exported plans and 5,184 task rows from 144 existing G1-A pairs.")
    print("Scope: shared export integrity. Full event logs are sealed separately.")


if __name__ == "__main__":
    try:
        verify()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"G1-A evidence check failed: {error}") from error

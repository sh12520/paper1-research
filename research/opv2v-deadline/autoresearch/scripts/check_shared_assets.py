#!/usr/bin/env python3
"""Run the read-only checks shipped with the Paper 1 OPV2V research branch."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1]
DIRECTION = WORKFLOW.parent
LOCAL = WORKFLOW / "local"
EVIDENCE_ATTEMPT = "20261124T153454170423Z-3541052b"


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_local_assets():
    provenance = json.loads((LOCAL / "PROVENANCE.json").read_bytes())
    for row in provenance["files"]:
        path = LOCAL / row["shared"]
        if file_sha256(path) != row["shared_sha256"]:
            raise ValueError(f"Local handoff checksum mismatch: {row['shared']}")
    print(f"Verified {len(provenance['files'])} local handoff files.", flush=True)


def check_workflow_assets():
    manifest = WORKFLOW / "SOURCE_SHA256SUMS.txt"
    entries = manifest.read_text(encoding="utf-8").splitlines()
    for entry in entries:
        expected, relative = entry.split("  ", 1)
        path = WORKFLOW / relative
        if file_sha256(path) != expected:
            raise ValueError(f"Archived workflow checksum mismatch: {relative}")
    print(f"Verified {len(entries)} archived workflow files.", flush=True)


def check_sealed_dair_receipt():
    # The shared snapshot contains one completed attempt. Its verification uses no task lock.
    directory = WORKFLOW / "experiments" / "research-harness" / "evidence-46" / EVIDENCE_ATTEMPT
    reservation = directory / "reservation.json"
    snapshot = json.loads(reservation.read_bytes())
    receipt = json.loads((directory / "receipt.json").read_bytes())
    if (snapshot["schema"], snapshot["task"], snapshot["attempt"]) != (1, "evidence-46", EVIDENCE_ATTEMPT):
        raise ValueError("Unexpected DAIR reservation identity")
    if snapshot["identity"] != json_sha256(snapshot["inputs"]):
        raise ValueError("DAIR input digest mismatch")
    if receipt.pop("receipt_sha256") != json_sha256(receipt):
        raise ValueError("DAIR receipt digest mismatch")
    if receipt["reservation_sha256"] != file_sha256(reservation):
        raise ValueError("DAIR reservation does not match receipt")
    if receipt["result"]["status"] != "passed":
        raise ValueError("Sealed DAIR attempt must have passed")
    outputs = {}
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Unexpected DAIR evidence entry: {path.name}")
        if path.name not in {"reservation.json", "receipt.json"}:
            outputs[path.name] = file_sha256(path)
    if outputs != receipt["outputs"]:
        raise ValueError("DAIR evidence files do not match receipt")
    print("Verified sealed DAIR training-example receipt.", flush=True)


def main():
    try:
        check_local_assets()
        check_workflow_assets()
        check_sealed_dair_receipt()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Shared evidence check failed: {exc}", file=sys.stderr)
        return 1
    checks = (
        (
            "Original R1 packet timing ledger",
            [sys.executable, "-B", "-E", str(DIRECTION / "src/check_packet_clock.py")],
        ),
        (
            "R1 to R2.6 portable result evidence",
            [sys.executable, "-B", "-E", str(DIRECTION / "results/export_evidence.py")],
        ),
    )
    for label, command in checks:
        print(f"Checking {label}", flush=True)
        result = subprocess.run(command, cwd=WORKFLOW, check=False)
        if result.returncode:
            return result.returncode
    print("All shared OPV2V and DAIR evidence checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

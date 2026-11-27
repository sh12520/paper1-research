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


def check_local_assets():
    provenance = json.loads((LOCAL / "PROVENANCE.json").read_bytes())
    for row in provenance["files"]:
        path = LOCAL / row["shared"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["shared_sha256"]:
            print(f"Local handoff checksum mismatch: {row['shared']}", file=sys.stderr)
            return False
    print(f"Verified {len(provenance['files'])} local handoff files.", flush=True)
    return True


def main():
    if not check_local_assets():
        return 1
    checks = (
        ("Archived workflow files", ["sha256sum", "-c", "SOURCE_SHA256SUMS.txt"]),
        (
            "Sealed DAIR training example receipt",
            [sys.executable, "-B", "scripts/research_harness.py", "verify", "evidence-46",
             "--attempt", EVIDENCE_ATTEMPT],
        ),
        (
            "Original R1 packet timing ledger",
            [sys.executable, "-B", str(DIRECTION / "src/check_packet_clock.py")],
        ),
        (
            "R1 to R2.6 portable result evidence",
            [sys.executable, "-B", str(DIRECTION / "results/export_evidence.py")],
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

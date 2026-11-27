#!/usr/bin/env python3
"""Check the original OPV2V scheduler against one archived R1 ledger."""

import json
from hashlib import sha256
from pathlib import Path

from opv2v_network import schedule


def main():
    location = Path(__file__).resolve().parent
    fixture = json.loads((location / "r1_packet_clock_frame0000.json").read_bytes())
    module = location / "opv2v_network.py"
    if sha256(module.read_bytes()).hexdigest() != fixture["original_module_sha256"]:
        raise SystemExit("Archived timing module digest mismatch")
    fields = ("transmissions", "detection_stages", "total_bytes")
    for case in fixture["cases"]:
        replay = schedule(case["mode"], case["bandwidth_mbps"], case["rtt_ms"], case["channels"])
        # Round-trip tuple packet IDs to their original JSON array representation.
        replay = json.loads(json.dumps(replay, allow_nan=False))
        if any(replay[field] != case[field] for field in fields):
            raise SystemExit(f"Timing ledger mismatch for {case['mode']}")
        transmissions = replay["transmissions"]
        total = replay["total_bytes"]
        if total != sum(row["bytes"] for row in transmissions) or total > case["budget_kib"] * 1024:
            raise SystemExit(f"Application budget mismatch for {case['mode']}")
        stages = replay["detection_stages"]
        final = max(stage["ready_ms"] for stage in stages if stage["ready_ms"] <= 50)
        print(f"{case['mode']}: {total} B, latest modeled stage at 50 ms: {final:.6f} ms")
    print(f"{fixture['frame_key']}: {len(fixture['cases'])} archived timing cases matched")


if __name__ == "__main__":
    main()

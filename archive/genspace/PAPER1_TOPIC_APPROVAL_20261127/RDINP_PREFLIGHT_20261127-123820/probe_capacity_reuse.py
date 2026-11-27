"""Two logical quota cases using frozen C2, loopback HTTP and a manual authority clock."""

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "runs" / "source"
sys.path.insert(0, str(SOURCE))

import initiator
from contracts import parse
from test_candidate import Harness, Manual


def observe(harness):
    state = harness.authority.snapshot()
    original = next(row for row in state["negotiations"] if row["neg"] == "first")
    commits = sum(
        row["event"] == "COMMIT" and row["neg"] == "first"
        for row in state["effects"]
    )
    return {"state": original["state"], "lease_ns": original["lease"], "commits": commits}


def run_case(destination, fault):
    manual = Manual()

    def response_policy(message, _kind, _body):
        return {"drop": fault == "response_loss" and message["kind"] == "COMMIT"}

    harness = Harness(destination / fault, manual=manual, policy=response_policy, capacity=10)
    original_post = initiator.post
    suppressed = []

    def client_post(host, port, path, raw, timeout=2):
        message = parse(raw)
        if fault == "request_loss" and message["kind"] == "COMMIT":
            suppressed.append({"phase": message["phase"], "attempt": message["attempt"]})
            raise ConnectionError("local fixture suppressed the request before HTTP")
        return original_post(host, port, path, raw, timeout)

    try:
        with patch("initiator.post", client_post):
            local = harness.client.run(harness.server.host, harness.server.port, "first", "intent-first", 10)
            harness.client.drain()
        initial = observe(harness)
        before = harness.reserve(neg="next-before-expiry", units=1)["status"]
        manual.set(initial["lease_ns"] + 1)
        harness.authority.cleanup()
        later = observe(harness)
        after = harness.reserve(neg="next-after-expiry", units=1)["status"]
        expected = {
            "request_loss": ("RESERVED", "EXPIRED", 0, "RESERVED"),
            "response_loss": ("CONFIRMED", "CONFIRMED", 1, "REJECTED"),
        }[fault]
        assert (local["status"], local["effectKnowledge"]) == ("RECOVERY_REQUIRED", "UNKNOWN")
        assert before == "REJECTED"
        assert (initial["state"], later["state"], later["commits"], after) == expected
        return {
            "fault": fault,
            "application_control_terminal": local["status"],
            "effect_knowledge": local["effectKnowledge"],
            "authority_before_expiry": initial,
            "authority_after_reserved_lease_expiry": later,
            "independent_request_before_expiry": before,
            "independent_request_after_expiry": after,
            "suppressed_commit_requests": suppressed,
        }
    finally:
        harness.close()


if __name__ == "__main__":
    out = ROOT / "logical_capacity_probe"
    out.mkdir(exist_ok=False)
    result = {
        "scope": "LOCAL_LOOPBACK_SQLITE_LOGICAL_CAPACITY_ONLY",
        "authority_clock": "manual; crossed the recorded reservation expiry by 1 ns",
        "physical_compute": False,
        "wireless_measurement": False,
        "probe_capacity_units": 10,
        "original_request_units": 10,
        "subsequent_request_units": 1,
        "source_sha256": {
            name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
            for name in ("initiator.py", "authority.py", "test_candidate.py", "endpoint.py")
        },
        "cases": [run_case(out, fault) for fault in ("request_loss", "response_loss")],
    }
    encoded = json.dumps(result, indent=2) + "\n"
    (out / "results.json").write_text(encoded, encoding="utf-8")
    print(encoded, end="")


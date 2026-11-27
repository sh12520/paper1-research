"""Check-to-publication deadline witnesses in isolated, actual SQLite transactions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "SERVICE_WORKER_DEV_01"))
from run_study import compute_edge

NS_PER_MS = 1_000_000
TAIL_BUDGET_MS = 80
CASES = {
    "normal_slack": {"slack_ms": 250, "pause_ms": 0},
    "injected_pause_low_slack": {"slack_ms": 25, "pause_ms": 80},
}
POLICIES = ("CHECK_ONLY", "RESERVE_TAIL_BUDGET")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run_case(directory, name, policy, payload, slack_ms, pause_ms):
    with sqlite3.connect(directory / f"{name}_{policy}.sqlite", isolation_level=None) as sink:
        sink.execute("PRAGMA synchronous=FULL")
        sink.execute("CREATE TABLE slot (position INTEGER PRIMARY KEY, output BLOB NOT NULL)")
        sink.execute("BEGIN IMMEDIATE")
        release_ns = time.monotonic_ns()
        deadline_ns = release_ns + slack_ms * NS_PER_MS
        check_ns = time.monotonic_ns()
        reserve_ns = TAIL_BUDGET_MS * NS_PER_MS if policy == "RESERVE_TAIL_BUDGET" else 0
        permitted = check_ns + reserve_ns < deadline_ns
        entry_ns = exit_ns = None
        if permitted:
            sink.execute("INSERT INTO slot VALUES(0,?)", (payload,))
            if pause_ms:
                time.sleep(pause_ms / 1000)
            entry_ns = time.monotonic_ns()
            sink.commit()
            exit_ns = time.monotonic_ns()
        else:
            sink.rollback()
        row = sink.execute("SELECT output FROM slot WHERE position=0").fetchone()
        outcome = {
            "case": name, "policy": policy, "pause_ms": pause_ms,
            "tail_budget_ms": reserve_ns / NS_PER_MS,
            "check_slack_ms": (deadline_ns - check_ns) / NS_PER_MS,
            "entry_relative_deadline_ms": (entry_ns - deadline_ns) / NS_PER_MS if entry_ns else None,
            "return_relative_deadline_ms": (exit_ns - deadline_ns) / NS_PER_MS if exit_ns else None,
            "applied": permitted, "visible_effect": row is not None,
            "digest_equal": digest(row[0]) == digest(payload) if row else None,
            "late_commit_proved": bool(permitted and entry_ns >= deadline_ns),
            "observed_commit_finished_by_deadline": bool(permitted and exit_ns < deadline_ns),
        }
        assert outcome["applied"] == outcome["visible_effect"]
        return outcome


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    if output == ROOT or not output.is_relative_to(ROOT):
        raise ValueError("output must be a fresh directory within this study")
    output.mkdir(exist_ok=False)
    image = compute_edge(args.asset.read_bytes())
    records = [
        run_case(output, name, policy, image, **case)
        for name, case in CASES.items() for policy in POLICIES
    ]
    for row in records:
        if row["case"] == "normal_slack":
            assert row["observed_commit_finished_by_deadline"]
        elif row["policy"] == "CHECK_ONLY":
            assert row["late_commit_proved"]
        else:
            assert not row["visible_effect"]
    report = {
        "scope": "controlled check-to-persistence witness; pause is deliberately inserted before SQLite COMMIT",
        "tail_budget_source": "engineering test parameter; not a measured or general time bound",
        "comparison": records,
    }
    text = json.dumps(report, indent=2)
    (output / "results.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()


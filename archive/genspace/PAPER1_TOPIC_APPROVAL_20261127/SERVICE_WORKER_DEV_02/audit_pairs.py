"""Independently check publication, worker reuse, and signed control outcomes."""

import argparse
import base64
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics


def events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capacity_rejections(raw_log):
    count = 0
    for event in raw_log:
        if event["event"] != "RESPONSE_EGRESS" or event.get("negotiationId") != "next":
            continue
        encoded = event["rawBase64"]
        response = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        body = response["body"]
        if response["kind"] == "DECISION" and body["status"] == "REJECTED" and body["reason"] == "CAPACITY":
            count += 1
    return count


def audit(run):
    run = run.resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    with (run / "per_task.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    cases = {}
    for row in rows:
        cases.setdefault(row["pair_id"], []).append(row)
    assert len(cases) * 2 == len(rows) == 24
    assert len({(r["method"], r["condition"], r["asset"], r["task_id"]) for r in rows}) == 24
    for name, h in manifest["files"].items():
        assert sha(run.parent / name) == h
    assert sha(run.parent / "STUDY_SPEC.md") == manifest["spec_sha256"]
    prior = run.parent.parent
    c2_root = prior / "RDINP_PREFLIGHT_20261127-123820" / "runs" / "source"
    assert all(sha(c2_root / name) == h for name, h in manifest["frozen_c2"].items())
    assert sha(prior / "SERVICE_WORKER_DEV_01" / "run_study.py") == manifest["workload_sha256"]

    causal = []
    for key, group in cases.items():
        assert [r["task_id"] for r in group] == ["first", "next"]
        pair = run / key
        worker = events(pair / "worker_events.jsonl")
        app = events(pair / "app_events.jsonl")
        pids = json.loads((pair / "endpoint_pids.json").read_text(encoding="utf-8"))
        assert pids["worker_pid"] != pids["app_pid"]
        assert {e["pid"] for e in worker} == {pids["worker_pid"]}
        assert {e["pid"] for e in app} == {pids["app_pid"]}
        assert sum(e["event"] == "SERVER_START" for e in worker) == 1
        assert sum(e["event"] == "SERVER_END" for e in worker) == 1
        assert not any(e["event"].endswith("_ERROR") for e in worker)
        assert int(group[1]["release_ns"]) - int(group[0]["release_ns"]) >= 900_000_000
        for row in group:
            task = row["task_id"]
            release = [e for e in app if e["event"] == "RELEASE" and e["task_id"] == task]
            published = [e for e in app if e["event"] == "PUBLISHED" and e["task_id"] == task]
            starts = [e for e in worker if e["event"] == "APP_START" and e["task_id"] == task]
            finishes = [e for e in worker if e["event"] == "APP_COMPLETE" and e["task_id"] == task]
            assert len(release) == len(published) == 1
            assert len(starts) == len(finishes) <= 1
            assert int(row["publish_ns"]) == published[0]["publish_ns"]
            assert (int(row["publish_ns"]) < release[0]["deadline_ns"]) == (row["on_time"] == "True")
            assert row["result_sha256"] == manifest["assets"][row["asset"]]["outputs"][row["published_source"]]
            assert published[0]["result_sha256"] == row["result_sha256"]
            for start in starts:
                assert start["activation_ns"] < release[0]["cutoff_ns"]
            if row["published_source"] == "edge":
                assert len(starts) == 1 and int(row["publish_ns"]) < release[0]["cutoff_ns"]
        first_release = [e for e in worker if e["event"] == "APP_RELEASE" and e["task_id"] == "first"]
        first_grant = [e for e in worker if e["event"] == "APP_GRANT" and e["task_id"] == "first"]
        next_grant = any(e["event"] == "APP_GRANT" and e["task_id"] == "next" for e in worker)
        assert len(first_release) <= 1 and len(first_grant) <= 1
        blocked = 0
        first_commit = None
        first_state = None
        second_state = None
        if group[0]["method"] == "C2_AUTH_QUERY":
            quota = json.loads((pair / "c2_quota_final.json").read_text(encoding="utf-8"))
            states = {n["task_id"]: n["state"] for n in quota["negotiations"]}
            first_state, second_state = states.get("first"), states.get("next")
            first_commit = sum(e["event"] == "COMMIT" and e["task_id"] == "first" for e in quota["effects"])
            blocked = capacity_rejections(events(pair / "c2_server.jsonl"))
        causal.append({
            "pair_id": key, "condition": group[0]["condition"], "method": group[0]["method"],
            "first_granted": bool(first_grant),
            "first_release_reason": first_release[0]["release_reason"] if first_release else None,
            "first_released_before_next": bool(first_release and first_release[0]["monotonic_ns"] < int(group[1]["release_ns"])),
            "first_observed_release_to_next_ms": (int(group[1]["release_ns"]) - first_release[0]["monotonic_ns"]) / 1e6 if first_release else None,
            "first_original_commits": first_commit, "first_original_state": first_state,
            "next_original_state": second_state, "next_capacity_rejection_receipts": blocked,
            "next_application_grant": next_grant,
        })

    assert sum(x["condition"] == "clean" for x in causal) == 6
    summary = []
    for condition in manifest["conditions"]:
        for method in manifest["methods"]:
            for task in ("first", "next"):
                matched = [r for r in rows if (r["condition"], r["method"], r["task_id"]) == (condition, method, task)]
                counts = Counter((r["published_source"], r["on_time"]) for r in matched)
                summary.append({
                    "condition": condition, "method": method, "task": task, "released": len(matched),
                    "edge_on_time": counts["edge", "True"], "local_on_time": counts["local", "True"],
                    "late": sum(r["on_time"] != "True" for r in matched),
                    "median_ms": round(statistics.median(float(r["latency_ms"]) for r in matched), 3),
                })
    for name, table in (("summary.csv", summary), ("quota_attribution.csv", causal)):
        with (run / name).open("x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
    print("AUDITED", len(rows), "tasks,", len(cases), "pairs")
    for row in summary:
        print(row)
    print("slot released before next", sum(x["first_released_before_next"] for x in causal))
    print("C2 capacity reconstruction", sum(x["next_capacity_rejection_receipts"] > 0 for x in causal))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    audit(parser.parse_args().run)


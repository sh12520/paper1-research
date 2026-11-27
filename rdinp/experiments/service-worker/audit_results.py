"""Recompute the paired study summary and check raw event invariants."""

from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics


def audit(path):
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    with (path / "per_case.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(manifest["methods"]) * len(manifest["scenarios"]) * len(manifest["assets"])
    assert len({(r["asset"], r["scenario"], r["method"]) for r in rows}) == len(rows)
    for row in rows:
        event_path = path / row["task_id"] / "events.jsonl"
        events = [json.loads(x) for x in event_path.read_text(encoding="utf-8").splitlines()]
        assert list(range(len(events))) == [e["index"] for e in events]
        assert sorted(e["monotonic_ns"] for e in events) == [e["monotonic_ns"] for e in events]
        starts = [e for e in events if e["event"] == "EDGE_START"]
        grants = [e for e in events if e["event"] == "EDGE_GRANT"]
        releases = [e for e in events if e["event"] == "EDGE_RELEASE"]
        outputs = [e for e in events if e["event"] == "APP_FINAL"]
        release = next(e for e in events if e["event"] == "APP_RELEASE")
        assert len(outputs) == 1 and len(starts) <= 1 and len(grants) <= 1
        assert outputs[0]["selected"] == row["selected"]
        assert (outputs[0]["publish_ns"] < release["deadline_ns"]) == (row["on_time"] == "True")
        assert int(row["edge_starts"]) == len(starts)
        assert int(row["edge_grants"]) == len(grants) == len(releases)
        if grants:
            assert grants[0]["monotonic_ns"] <= releases[0]["monotonic_ns"]
        for event in starts:
            assert event["monotonic_ns"] < release["fallback_cutoff_ns"]
        if row["selected"] == "edge":
            assert len(starts) == 1
            assert outputs[0]["publish_ns"] < release["fallback_cutoff_ns"]
        else:
            assert any(e["event"] == "LOCAL_START" and e["monotonic_ns"] >= release["fallback_cutoff_ns"]
                       for e in events)
        assert outputs[0]["output_sha256"] == manifest["assets"][row["asset"]][row["selected"] + "_sha256"]
        assert outputs[0]["output_sha256"] == row["valid_output_sha256"]

    result = []
    for scenario in manifest["scenarios"]:
        for method in manifest["methods"]:
            cohort = [r for r in rows if r["scenario"] == scenario and r["method"] == method]
            latency = [float(r["end_to_end_ms"]) for r in cohort]
            assert len(cohort) == len(manifest["assets"])
            result.append({
                "scenario": scenario, "method": method, "released": len(cohort),
                "edge_on_time": sum(r["selected"] == "edge" and r["on_time"] == "True" for r in cohort),
                "fallback_on_time": sum(r["selected"] == "local" and r["on_time"] == "True" for r in cohort),
                "missed": sum(r["on_time"] != "True" for r in cohort),
                "edge_starts": sum(int(r["edge_starts"]) for r in cohort),
                "end_to_end_ms_median": round(statistics.median(latency), 3),
                "end_to_end_ms_min": round(min(latency), 3),
                "end_to_end_ms_max": round(max(latency), 3),
                "unused_slot_ms_mean": round(statistics.mean(float(r["unused_lease_ms"]) for r in cohort), 3),
                "control_body_bytes_median": statistics.median(int(r["control_body_bytes"]) for r in cohort),
                "data_body_bytes_median": statistics.median(int(r["data_body_bytes"]) for r in cohort),
            })
    with (path / "summary.csv").open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(result[0]))
        w.writeheader()
        w.writerows(result)
    captured = [f for f in sorted(path.rglob("*")) if f.is_file() and f.suffix != ".sqlite"]
    (path / "evidence_sha256.txt").write_text(
        "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(path).as_posix()}\n"
                for f in captured),
        encoding="utf-8",
    )
    print("AUDITED", len(rows), "paired-case rows")
    for row in result:
        print(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("study", type=Path)
    audit(parser.parse_args().study)


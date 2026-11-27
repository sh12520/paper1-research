#!/usr/bin/env python3
"""Project historical OPV2V archives into portable evidence. No model imports."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = ("A_deferred_original", "B_receive_compute", "C_compact_receive_compute")
COMPARISON = "C_compact_receive_compute_minus_B_receive_compute"
DIRECT = {
    "r1-marginal-abcd.json": "results/autoresearch/marginal-abcd.json",
    "r1-b-deadline35.json": "results/autoresearch/r1d-ordinary-35-complete.json",
    "r2-order-cpu-repeat.json": "results/opv2v-r2-order-cpu-dev-repeat/report.json",
    "r23-incremental-control.json": "results/opv2v-r23/incremental-control.json",
    "r23-nms-probe.json": "results/opv2v-r23/nms-probe/completion.json",
    "r25-compact-wire.json": "results/opv2v-r25/compact-wire-timing.json",
    "r25-pose-grid-probe.json": "results/opv2v-r25/pose-grid-probe.json",
    "r26-completion-seal.json": "results/opv2v-r26/screen/completion.json",
    "r26-deadline-complete-rate.png": "results/opv2v-r26/figures/deadline-complete-rate.png",
}
DAIR = "results/dair-tmc-validation-preflight/official-panel-inputs.json"
R23 = "results/opv2v-r23/report.json"
R24 = "results/opv2v-r24/report.json"
R25 = "results/opv2v-r25/report.json"
R26 = "results/opv2v-r26/report.json"
SEAL = DIRECT["r26-completion-seal.json"]
EXAMPLE = "results/opv2v-r26/screen/per-frame/1332.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def select(obj, keys):
    return {key: obj[key] for key in keys}


def verify(location):
    manifest = json.loads((location / "SOURCES.json").read_bytes())
    for name, item in manifest.items():
        assert sha((location / name).read_bytes()) == item["sha256"], name
    with (location / "r26-deadline-table.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    frontier = json.loads((location / "r26-deadline-summary.json").read_bytes())
    by_mode = {(row["arm"], row["deadline_ms"]): int(row["complete_frames"]) for row in rows}
    assert len(rows) == len(by_mode) == 18
    assert by_mode[MODES[2], "35"] == 0
    assert by_mode[MODES[2], "45"] == 37
    assert by_mode[MODES[2], "50"] == 60
    for deadline, cells in frontier["by_deadline_ms"].items():
        for arm, metrics in cells["modes"].items():
            assert by_mode[arm, deadline] == metrics["complete_frames"]
    case = json.loads((location / "r26-frame-1332.json").read_bytes())
    seal = json.loads((location / "r26-completion-seal.json").read_bytes())
    assert seal["frame_sha256"][case["frame_key"]] == manifest["r26-frame-1332.json"]["source_sha256"][EXAMPLE]
    compact = case["replay_arms"][MODES[2]]
    assert sum(p["bytes"] for p in compact["packet_ledger"]) == compact["application_bytes"]
    assert compact["dependency_timestamps_ms"]["T_complete_ms"] > 50
    r1 = json.loads((location / "r1-marginal-abcd.json").read_bytes())
    assert r1["effects"]["C-B"]["delta"]["ap70"] < 0
    print(f"verified {len(manifest)} artifacts, 18 deadline cells, R1 contrast and sealed R2.6 case identity")


def export(source, location):
    location.mkdir(parents=True, exist_ok=True)
    manifest = {}

    def source_record(name, sources, method):
        manifest[name] = {
            "method": method,
            "sha256": sha((location / name).read_bytes()),
            "source_sha256": {path: sha((source / path).read_bytes()) for path in sources},
        }

    def load(path):
        return json.loads((source / path).read_bytes())

    for name, path in DIRECT.items():
        raw = (source / path).read_bytes()
        if name.endswith(".json"):
            assert b"/home/" not in raw and b"GPU-" not in raw, path
        (location / name).write_bytes(raw)
        source_record(name, [path], "byte-identical")

    dair = load(DAIR)
    del dair["dataset"]
    name = "dair-official-panel-inputs.json"
    dump(location / name, dair)
    source_record(name, [DAIR], "projection: local dataset path omitted")

    r23 = load(R23)
    name = "r23-prefilter-timing.json"
    dump(location / name, select(r23, ("status", "equivalence_gate", "timing", "scope")))
    source_record(name, [R23], "projection: seal and stage-level measured timing, excluding per-frame cutoff outputs")

    r24 = load(R24)
    summary = select(r24, ("status", "exactness_gate", "decision", "scope"))
    summary["by_deadline_ms"] = {}
    for deadline, metrics in r24["by_deadline_ms"].items():
        arms = {}
        for arm, values in metrics["mode"].items():
            schedule = select(values["schedule"], ("frames", "complete_detection_frames", "work_and_queue_totals_across_frames"))
            arms[arm] = {
                "first_detection_ap70": values["first_detection"]["ap70"],
                "final_detection_ap70": values["final_detection"]["ap70"],
                "schedule": schedule,
            }
        summary["by_deadline_ms"][deadline] = {"arms": arms, "E_minus_controls": metrics["E_minus_controls"]}
    name = "r24-coalescing-summary.json"
    dump(location / name, summary)
    source_record(name, [R24], "projection: exactness, scope, decisions and aggregate/paired outcomes")

    r25 = load(R25)
    name = "r25-pipeline-decision.json"
    dump(location / name, select(r25, ("status", "exactness_gate", "decision", "scope")))
    source_record(name, [R25], "projection: exactness, scope and published decision metrics")

    r26 = load(R26)
    summary = select(r26, ("status", "scope", "decision", "exactness_gate", "by_deadline_ms",
                           "thresholds_ms", "paired_threshold_differences_ms", "arm_summary"))
    del summary["exactness_gate"]["gpu_sources"]
    name = "r26-deadline-summary.json"
    dump(location / name, summary)
    source_record(name, [R26], "projection: aggregate deadline, scope, uncertainty and decision records; GPU UUID omitted")

    name = "r26-deadline-table.csv"
    with (location / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["deadline_ms", "arm", "panel_frames", "complete_frames", "complete_rate",
                         "full_only_ap70", "with_local_fallback_ap70"])
        for deadline, block in r26["by_deadline_ms"].items():
            for arm, item in block["modes"].items():
                evaluations = item["evaluations"]
                writer.writerow([deadline, arm, r26["exactness_gate"]["expected_frames"], item["complete_frames"],
                                 item["complete_rate"], evaluations["full_task_only"]["ap70"],
                                 evaluations["with_local_fallback"]["ap70"]])
    source_record(name, [R26], "projection: 6 deadlines × 3 arms")

    receipt = load(EXAMPLE)
    key = receipt["frame_key"]
    assert load(SEAL)["frame_sha256"][key] == sha((source / EXAMPLE).read_bytes())
    name = "r26-frame-1332.json"
    dump(location / name, {
        **select(receipt, ("frame_key", "ordinal", "status", "full_state_sha256", "detector_sha256", "equivalence")),
        "replay_arms": r26["per_frame"][key]["arms"],
        "measured_compact_tail": receipt["tail"],
        "measured_compact_packet_profiles": receipt["packet_profiles"],
        "scope": "Per-frame trace positions are modeled; hardware service receipts are stopwatch and CUDA stage events for the same full-state detector. Machine identity and detection boxes omitted.",
    })
    source_record(name, [EXAMPLE, R26, SEAL], "projection: sealed frame identity, per-arm replay and compact service timings")
    dump(location / "SOURCES.json", manifest)
    verify(location)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="local source project; omit for a read-only packaged evidence check")
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    if args.source_root:
        export(args.source_root, args.output)
    else:
        verify(args.output)


if __name__ == "__main__":
    main()

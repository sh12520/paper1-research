"""Read admitted C2 first-attempt bodies and estimate clean Step 1 timing headroom."""
import argparse
import hashlib
import json
import re
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path

from sim import AIR_RATES, BASE_TRANSIT_MS, CONTROL_SERVICE_MS, FRAME_BYTES, FRAME_HEADER_BYTES

PHASES = ("INTENT_INITIAL", "INTENT_REPLAY", "COMMIT_INITIAL", "COMMIT_REPLAY")
CLEAN_B1 = re.compile(r"(study-(4x1|8x2-retry-01)/runs/[^/]+-clean/B1)/(.*\.jsonl)")
HERE = Path(__file__).resolve().parent
DURABLE = HERE.parent / "durable-worker"
ARCHIVE_NAME = "g1a-evidence-v1.tar.gz"
DEFAULT_ARCHIVE = DURABLE / "runs" / "g1a-decision-01" / ARCHIVE_NAME
ARCHIVE_RECEIPT = DURABLE / "evidence" / "g1a-20261128" / (ARCHIVE_NAME + ".sha256")
STEP1_PLAN = HERE / "evidence" / "step1-20261128-r02" / "plan.json"


def describe(values):
    if not values:
        raise ValueError("empty measurement")
    return {
        "n": len(values), "min": min(values), "median": statistics.median(values),
        "p95": statistics.quantiles(values, n=20, method="inclusive")[18],
        "max": max(values),
    }


def collect(path):
    relays = defaultdict(dict)
    traces = []
    with tarfile.open(path, mode="r|gz") as archive:
        for entry in archive:
            match = CLEAN_B1.fullmatch(entry.name.removeprefix("./"))
            if not entry.isfile() or match is None:
                continue
            run, layout, name = match.groups()
            if name != "events.jsonl" and re.fullmatch(r"c2/terminal-\d+/task-\d+-events\.jsonl", name) is None:
                continue
            with archive.extractfile(entry) as lines:
                if name == "events.jsonl":
                    for line in lines:
                        event = json.loads(line)
                        if event["event"] != "C2_RELAY_RX":
                            continue
                        key = (event["request_raw_sha256"], event["direction"])
                        if key in relays[run]:
                            raise ValueError(f"duplicated relay receipt in {run}, {key[1]}")
                        relays[run][key] = event
                    continue
                selected = {}
                for line in lines:
                    event = json.loads(line)
                    label = event["event"]
                    if label == "PHASE_WINNER_LATCH":
                        label = event["phase"]
                    if label in (*PHASES, "NEGOTIATION_START", "TERMINAL_PUBLISHED"):
                        if label in selected:
                            raise ValueError(f"duplicated client event {label} in {run}/{name}")
                        selected[label] = event
                traces.append((run, layout, selected))
    return relays, traces


def measured_bodies(archive):
    relays, traces = collect(archive)
    per_phase = {name: {direction: [] for direction in ("uplink", "downlink")} for name in PHASES}
    totals = []
    durations = defaultdict(list)
    excluded = defaultdict(int)
    for run, layout, trace in traces:
        terminal = trace.get("TERMINAL_PUBLISHED", {}).get("result", {})
        if terminal.get("status") != "COMMITTED" or not terminal.get("confirmationComplete"):
            excluded["no_committed_terminal"] += 1
            continue
        if not all(phase in trace for phase in PHASES):
            raise ValueError(f"confirmed trace missing phase: {run}")
        if any(trace[phase]["attempt"] != 0 for phase in PHASES):
            excluded["winner_not_first_attempt"] += 1
            continue
        total = 0
        for phase in PHASES:
            winner = trace[phase]
            req = winner["requestRawSha256"]
            for direction in ("uplink", "downlink"):
                observed = relays[run][req, direction]
                if observed["phase"] != phase or observed["attempt"] != 0:
                    raise ValueError(f"relay and winning phase disagree: {run}")
                if direction == "downlink" and (
                    observed["response_raw_sha256"] != winner["rawSha256"] or observed["http_status"] != 200
                ):
                    raise ValueError(f"reply and winner disagree: {run}")
                size = observed["body_bytes"]
                per_phase[phase][direction].append(size)
                total += size
        totals.append(total)
        duration = (trace["TERMINAL_PUBLISHED"]["observedNs"] - trace["NEGOTIATION_START"]["observedNs"]) / 1e6
        if duration <= 0:
            raise ValueError(f"invalid negotiation span: {run}")
        durations[layout].append(duration)
        durations["all"].append(duration)
    return {
        "clean_b1_runs": len(relays), "client_traces": len(traces),
        "excluded": dict(excluded), "complete_first_attempt_samples": len(totals),
        "json_body_bytes": {
            phase: {direction: describe(values) for direction, values in arm.items()}
            for phase, arm in per_phase.items()
        },
        "total_body_bytes": describe(totals),
        "negotiation_elapsed_ms": {layout: describe(values) for layout, values in durations.items()},
        "per_task_control_only_within_step1_edge_windows": {
            layout: {str(window): sum(t < window for t in values) for window in (345, 545, 745)}
            for layout, values in durations.items()
        },
    }


def send_ms(payload, rate, fronthaul=None):
    air_end = fh_end = 0.0
    for first in range(0, payload, FRAME_BYTES):
        framed = min(payload - first, FRAME_BYTES) + FRAME_HEADER_BYTES
        work = framed * 0.008
        if fronthaul is not None:
            fh_end += work / fronthaul
        air_end = max(air_end, fh_end) + work / rate
    return air_end + BASE_TRANSIT_MS


def budget(plan, sizes):
    assumed_two = [(720, 448), (320, 416)]
    estimate = []
    for dip, fh in ((0.0, 2250), (0.5, 1000), (0.75, 1000)):
        up = AIR_RATES["up"] * (1 - dip)
        down = AIR_RATES["down"] * (1 - dip)
        for level, phases in (("step1_two_modeled_exchanges", assumed_two),
                              ("c2_four_measured_body_sizes", sizes)):
            control = sum(send_ms(req, up) + send_ms(reply, down, fh) + CONTROL_SERVICE_MS
                          for req, reply in phases)
            for grade, upload_grade, execution_grade in (
                ("high", "high", "high"),
                ("light", "light", "light"),
                ("light_after_full_upload", "high", "light"),
            ):
                times = []
                for profiles in plan["profiles"].values():
                    send = profiles[upload_grade]
                    execute = profiles[execution_grade]
                    times.append(
                        control + send["prepare"] + send_ms(send["upload"] + 64, up)
                        + execute["service"] + send_ms(execute["download"] + 64, down, fh)
                    )
                for deadline in (400, 600, 800):
                    limit = deadline - plan["local_fallback_reserve_ms"]
                    estimate.append({
                        "air_rate_drop": dip, "control_model": level, "tier": grade, "deadline_ms": deadline,
                        "edge_adoption_window_ms": limit, "control_ms": control,
                        "no_queue_total_ms": describe(times),
                        "images_fit_before_fallback": sum(t < limit for t in times),
                        "median_margin_ms": limit - statistics.median(times),
                    })
    return estimate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with args.archive.open("rb") as handle:
        archive_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    want = ARCHIVE_RECEIPT.read_text(encoding="utf-8").split()[0]
    if archive_sha256 != want:
        raise ValueError("sealed archive digest mismatch")
    result = measured_bodies(args.archive)
    sizes = [
        tuple(round(row["median"]) for row in
              (result["json_body_bytes"][phase]["uplink"], result["json_body_bytes"][phase]["downlink"]))
        for phase in PHASES
    ]
    result.update(
        archive_sha256=archive_sha256, step1_plan_sha256=hashlib.sha256(STEP1_PLAN.read_bytes()).hexdigest(),
        modeled_c2_body_sizes=dict(zip(PHASES, sizes)),
        headroom=budget(json.loads(STEP1_PLAN.read_text(encoding="utf-8")), sizes),
    )
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Read-only evidence and readiness adapters for the local research harness."""

from collections import Counter
from functools import partial
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


CONFIG = Path("configs/dair-v2x")
FORMAL_PLAN = CONFIG / "FORMAL_VALIDATION.md"
VALIDATION = CONFIG / "val.json"
TRAINING = CONFIG / "train.json"
SAMPLE = CONFIG / "sample-train-pairs.json"
FROZEN_HASHES = {
    FORMAL_PLAN: "54809f0805d29f56d10ea3bd784446bbaf3a94e3b2c5273f6facdfccbd3f77b3",
    VALIDATION: "a0993520f5f91af282a96a2d542f3d837434b7a68392636f90bff050883fd832",
}
SAMPLE_SHA = "30e50f9063e10a7aef3f23e7a481b8e608d5d03916ec94144acbe8095b4a6cd2"
DAIR_ROOT = Path("datasets/dair-full-official/cooperative-vehicle-infrastructure")
DAIR_AUDIT = Path("scripts/audit_dair_validation_panel.py")
GPU_RUNNER = Path("scripts/run_blindmap_dair.py")
NATIVE_DIR = Path("experiments/dair-tmc-pilot-02")
REPLAY_DIRS = tuple(Path(f"experiments/dair-tmc-budget-{name}") for name in (
    "prefix", "prefix-resume", "continuation", "last-frame"
))
EVIDENCE = Path("results/dair-tmc-budget")
NATIVE_MODES = ("local", "blindmap_1mib", "dense_shared")
REQUEST_BYTES = {
    "blindmap": 0, "binary": 4112, "quantized": 8208,
    "sparse": 272, "observation": 0, "confidence": 4112,
}
HEADS = {"cls_preds", "reg_preds", "dir_preds"}
IOU_LEVELS = ("0.5", "0.7")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, report):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def jsonl(path):
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{number}: invalid JSON record") from exc


def dair_preflight(root, attempt):
    observed = {str(path): sha256(root / path) for path in FROZEN_HASHES}
    expected = {str(path): digest for path, digest in FROZEN_HASHES.items()}
    write_json(attempt / "frozen-inputs.json", {"expected": expected, "observed": observed})
    if observed != expected:
        return {"status": "failed", "summary": "正式方案或验证划分 SHA-256 与冻结记录不一致。"}
    panel = read_json(root / VALIDATION)
    require(len(panel) == len(set(panel)) == 1783, "Expected 1,783 unique validation frame IDs")
    report_path = attempt / "dair-panel.json"
    collected = subprocess.run(
        [sys.executable, str(root / DAIR_AUDIT), str(root / DAIR_ROOT), str(report_path)],
        cwd=root, capture_output=True, text=True, timeout=120,
    )
    (attempt / "audit.log").write_text(collected.stdout + collected.stderr, encoding="utf-8")
    if collected.returncode:
        return {"status": "failed", "summary": f"数据盘点退出码为 {collected.returncode}。"}
    report = read_json(report_path)
    require(report["split_sha256"] == observed[str(VALIDATION)] and report["requested_frames"] == len(panel),
            "Data auditor did not use the frozen validation split")
    ready_ids = {row["frame"] for row in report["ready"]}
    require(len(ready_ids) == len(report["ready"]) and ready_ids <= set(panel),
            "Data auditor returned duplicate or foreign frame IDs")
    native_missing = sum(not row["official_occlusion_exists"] for row in report["ready"])
    summary = {
        "ready_frames": len(ready_ids), "requested_frames": len(panel),
        "ready_scenes": len(report["ready_by_scene"]),
        "missing_metadata": report["missing_tables"],
        "ready_frames_missing_native_occlusion": native_missing,
        "frozen_panel_complete": ready_ids == set(panel),
        "native_entry_data_ready": ready_ids == set(panel) and not native_missing,
        "formal_evaluation_started": False,
    }
    write_json(attempt / "readiness.json", summary)
    sentence = f"正式面板现有 {len(ready_ids)}/{len(panel)} 帧，覆盖 {summary['ready_scenes']} 个路侧批次。"
    if len(ready_ids) != len(panel):
        return {"status": "blocked", "summary": sentence}
    if native_missing:
        return {
            "status": "blocked",
            "summary": sentence + f"公开原生入口所需的遮挡辅助表仍缺 {native_missing} 帧。",
        }
    return {"status": "passed", "summary": sentence}


def read_detection(row):
    boxes, scores, gt = (row[key] for key in ("boxes", "scores", "gt"))
    require(isinstance(gt, list) and len(boxes or []) == len(scores or []),
            f"{row['frame']}: inconsistent box, score or GT record")
    require(all(isinstance(score, (int, float)) and math.isfinite(score) for score in scores or []),
            f"{row['frame']}: invalid detection score")
    return gt


def verify_46(root, attempt):
    require(sha256(root / SAMPLE) == SAMPLE_SHA, "Exploratory sample manifest changed")
    require(sha256(root / VALIDATION) == FROZEN_HASHES[VALIDATION], "Validation split changed")
    panel = read_json(root / SAMPLE)
    frames = set(panel)
    require(len(panel) == len(frames) == 46
            and frames <= set(read_json(root / TRAINING))
            and frames.isdisjoint(read_json(root / VALIDATION)),
            "Exploratory sample must remain 46 training IDs disjoint from validation")
    native_rows = list(jsonl(root / NATIVE_DIR / "detections.jsonl"))
    native = {(row["frame"], row["mode"]): read_detection(row) for row in native_rows}
    require(len(native) == len(native_rows)
            and set(native) == {(frame, mode) for frame in panel for mode in NATIVE_MODES},
            "Native detections must cover each frame and mode exactly once")
    for frame in panel:
        require(all(native[frame, mode] == native[frame, "local"] for mode in NATIVE_MODES),
                f"{frame}: native conditions disagree on ground truth")
    native_summary = read_json(root / NATIVE_DIR / "summary.json")
    require(native_summary["seed"] == 303 and native_summary["frames"] == len(panel),
            "Native summary seed/count mismatch")

    replay = {}
    cache_checks = {}
    cache_counts = Counter()
    diagnostic_counts = Counter()
    for run in REPLAY_DIRS:
        cfg = read_json(root / run / "config.json")
        require(cfg["seed"] == 303 and set(cfg["frames"]) <= frames
                and cfg["scope"] == "DAIR official example training panel"
                and set(cfg["policies"]) == set(REQUEST_BYTES)
                and cfg["budgets_kib"] == [32, 64, 128, 256, 512, 1024],
                f"{run.name}: inconsistent replay experiment manifest")
        for row in jsonl(root / run / "detections.jsonl"):
            frame = row["frame"]
            require(frame in cfg["frames"], f"{run.name}: frame {frame} outside its manifest")
            kind = row["kind"]
            if kind == "cache_validation":
                errors = row["max_abs_error"]
                require(set(errors) == HEADS and all(type(value) in (int, float) and value == 0
                                                    for value in errors.values()),
                        f"{frame}: cached and uncached detection heads disagree")
                if frame in cache_checks:
                    require(row["modality"] == cache_checks[frame]["modality"],
                            f"{frame}: replayed cache check changed modality")
                cache_checks[frame] = row
                cache_counts[frame] += 1
                continue
            if kind in {"sender_only", "oracle_skip"} or (
                kind == "evaluation" and row["mode"] == "hindsight_patch"
            ):
                diagnostic_counts["hindsight_patch" if kind == "evaluation" else kind] += 1
                continue
            require(kind == "evaluation", f"{frame}: unknown replay record kind {kind}")
            mode, kib = row["mode"], row["kib"]
            key = (frame, kib, mode)
            require(mode in REQUEST_BYTES and key not in replay, f"{key}: invalid or duplicate policy result")
            require(read_detection(row) == native[frame, "local"], f"{frame}: replay changed ground truth")
            feature, request = row["feature_bytes"], row["request_bytes"]
            require(type(feature) is int and 0 <= feature and type(request) is int
                    and request == REQUEST_BYTES[mode] and feature + request <= kib * 1024
                    and row["messages"] == int(feature > 0) + int(request > 0),
                    f"{key}: communication accounting mismatch")
            matches = row["matched"]
            require(set(matches) == set(IOU_LEVELS)
                    and all(len(ids) == len(set(ids)) and all(type(i) is int and
                            0 <= i < len(row["gt"]) for i in ids) for ids in matches.values()),
                    f"{key}: invalid matched target IDs")
            replay[key] = matches

    expected = {(frame, 1024, mode) for frame in panel for mode in REQUEST_BYTES}
    expected.update((frame, kib, mode) for frame in panel[:3]
                    for kib in (32, 64, 128, 256, 512) for mode in REQUEST_BYTES)
    require(set(replay) == expected, "Replay coverage does not match the frozen exploratory panel")
    require(set(cache_checks) == frames, "Cached equivalence was not recorded for all 46 frames")

    coverage = read_json(root / EVIDENCE / "coverage.json")
    # The aggregate also read diagnostic runs, which can contribute a second
    # cache receipt with a different wall time for an already verified frame.
    def cache_signature(checks):
        return {frame: (row["kind"], row["frame"], row["max_abs_error"], row["modality"])
                for frame, row in checks.items()}

    require(coverage["fixed"] == coverage["complete_packed_1024"] == panel
            and coverage["complete_budget_sweep"] == panel[:3]
            and coverage["native"] == len(native)
            and cache_signature(coverage["cache_checks"]) == cache_signature(cache_checks)
            and coverage["single_infrastructure_batch"] == "0",
            "Published coverage does not match raw detection records")
    paired = read_json(root / EVIDENCE / "paired-1024.json")
    for mode in REQUEST_BYTES:
        require(paired[mode]["frames"] == len(panel)
                and len(paired[mode]["ap"]) == 2
                and all(0 <= ap <= 1 for ap in paired[mode]["ap"]),
                f"{mode}: invalid paired summary")
        for threshold in IOU_LEVELS:
            delta = [len(replay[frame, 1024, mode][threshold]) -
                     len(replay[frame, 1024, "blindmap"][threshold]) for frame in panel]
            require(paired[mode][f"paired_tp_delta_{threshold}"] == {
                "gained_frames": sum(x > 0 for x in delta), "lost_frames": sum(x < 0 for x in delta),
                "tied_frames": sum(x == 0 for x in delta), "net_targets": sum(delta),
            }, f"{mode}: paired matched-target change disagrees with raw records")
    provenance = (root / EVIDENCE / "reproduction-versions.txt").read_text(encoding="utf-8")
    revision = "075b2c7120277a619f41bc49a58e3905ffad7aa7"
    checkpoint = "10511d4a9419f42051f01be2b9e6313b6718b2843f74795b5d9ceac7b200f7f5"
    checkpoint_line = f"{checkpoint}  models/blindmap-tmc/dair/heterogeneous/net_epoch_bestval_at35.pth"
    require(provenance.splitlines()[0] == revision and checkpoint_line in provenance.splitlines(),
            "Missing recorded baseline/model identity")
    write_json(attempt / "evidence-46.json", {
        "panel": "DAIR official example training split, single infrastructure batch",
        "independent_validation_frames": 0,
        "model_rerun": False, "ap_recomputed": False, "seed": 303,
        "recorded_model_revision": revision, "recorded_checkpoint_sha256": checkpoint,
        "native_detection_records": len(native), "replay_policy_records": len(replay),
        "complete_packed_1024_frames": len(panel), "complete_budget_sweep_frames": len(panel[:3]),
        "verified_cache_frames": len(cache_checks), "recorded_cache_events": sum(cache_counts.values()),
        "max_abs_head_error": {key: 0.0 for key in sorted(HEADS)},
        "separate_diagnostic_records": dict(diagnostic_counts),
        "archived_paired_summary": str(EVIDENCE / "paired-1024.json"),
    })
    return {
        "status": "passed",
        "summary": f"核对 {len(native)} 条原始记录、{len(replay)} 条策略记录及 46 帧缓存一致性。范围为训练例。",
    }


def gpu_preflight(root, attempt):
    thresholds = {"free_mib": 16000, "utilization": 10, "temperature_c": 75}
    devices, errors = [], []
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader,nounits"], text=True, timeout=15,
            stderr=subprocess.STDOUT,
        )
        indices = [int(line.strip()) for line in output.splitlines() if line.strip()]
        for index in indices:
            result = subprocess.check_output(
                [sys.executable, str(root / GPU_RUNNER), "--gpu-status", str(index)],
                text=True, timeout=15, stderr=subprocess.STDOUT,
            )
            snapshot = json.loads(result)
            blockers = []
            if snapshot["compute_processes"]:
                blockers.append("existing_compute_processes")
            if snapshot["free_mib"] < thresholds["free_mib"]:
                blockers.append("free_memory_below_limit")
            if snapshot["utilization"] > thresholds["utilization"]:
                blockers.append("utilization_above_limit")
            if snapshot["temperature_c"] > thresholds["temperature_c"]:
                blockers.append("temperature_above_limit")
            devices.append(dict(snapshot, index=index, blockers=blockers))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        errors.append(str(exc))
    ready = bool(devices) and not errors and any(not gpu["blockers"] for gpu in devices)
    write_json(attempt / "gpu-readiness.json", {
        "devices": devices, "probe_errors": errors, "thresholds": thresholds,
        "ready_for_resource_check": ready, "gpu_leased": False, "job_started": False,
    })
    return {
        "status": "passed" if ready else "blocked",
        "summary": f"读取到 {len(devices)} 张 GPU。"
                   + ("至少一张满足资源阈值。" if ready else "没有可确认满足资源阈值的 GPU。"),
    }


def tasks(root: Path):
    """Return the only tasks allowed to run in the scoped harness."""
    evidence_inputs = [
        SAMPLE, TRAINING, VALIDATION, NATIVE_DIR / "detections.jsonl", NATIVE_DIR / "summary.json",
        *(EVIDENCE / name for name in ("coverage.json", "paired-1024.json", "reproduction-versions.txt")),
        *(job / name for job in REPLAY_DIRS for name in ("config.json", "detections.jsonl")),
    ]
    return {
        "dair-preflight": {
            "description": "核对冻结方案并盘点 DAIR 正式面板。",
            "inputs": [FORMAL_PLAN, VALIDATION, DAIR_AUDIT], "live": True,
            "run": partial(dair_preflight, root),
        },
        "evidence-46": {
            "description": "复核已有 46 帧训练例证据与通信预算，不重跑模型。",
            "inputs": evidence_inputs, "live": False, "run": partial(verify_46, root),
        },
        "gpu-preflight": {
            "description": "只读检查 GPU 资源阈值与其他作业。",
            "inputs": [GPU_RUNNER], "live": True, "run": partial(gpu_preflight, root),
        },
    }

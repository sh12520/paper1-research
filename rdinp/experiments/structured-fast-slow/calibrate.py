"""Calibrate a three-tier CPU edge-map workload with matched source images."""

import argparse
import hashlib
import io
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parent
WORKER_DIR = ROOT.parent / "service-worker"
sys.path.insert(0, str(WORKER_DIR))
from image_workload import compute_edge, detect_edges

IMAGES = ("astronaut.png", "camera.png", "coffee.png")
SIDE = {"main": 512, "light": 384, "local": 256}
BORDER = 4


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def transport_input(source, side):
    """Perform the detector's first step at the terminal and encode a wire image."""
    with Image.open(io.BytesIO(source)) as image:
        gray = image.convert("L").resize((side, side), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    gray.save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def timed_ms(function, *args):
    start_ns = time.perf_counter_ns()
    result = function(*args)
    return result, (time.perf_counter_ns() - start_ns) / 1e6


def edge_values(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        aligned = image.resize((SIDE["main"], SIDE["main"]), Image.Resampling.BILINEAR)
        width, height = aligned.size
        return aligned.crop((BORDER, BORDER, width - BORDER, height - BORDER)).tobytes()


def similarity(reference, candidate):
    """Soft Dice on aligned edge intensities in the common interior."""
    total = sum(reference) + sum(candidate)
    return (2 * sum(map(min, reference, candidate)) / total) if total else 1.0


def calibrate(assets, repetitions):
    samples = {name: (assets / name).read_bytes() for name in IMAGES}
    profiles = {name: {} for name in IMAGES}
    inputs = {}
    durations = {}
    for name, source in samples.items():
        with Image.open(io.BytesIO(source)) as image:
            inputs[name] = {"shape_px": list(image.size), "original_bytes": len(source),
                            "sha256": sha256(source)}
        for mode, side in SIDE.items():
            payload = source if mode == "local" else transport_input(source, side)
            output = detect_edges(payload, side)
            if mode == "main" and output != compute_edge(source):
                raise RuntimeError(f"main tier diverged from the historical detector for {name}")
            profiles[name][mode] = {
                "output_side_px": side,
                "upload_bytes": 0 if mode == "local" else len(payload),
                "download_bytes": 0 if mode == "local" else len(output),
                "detector_input_sha256": sha256(payload),
                "output_sha256": sha256(output),
            }
            durations[name, mode] = {"prepare": [], "cpu": []}
            if mode == "main":
                reference = edge_values(output)
            profiles[name][mode]["utility"] = similarity(reference, edge_values(output))
        if profiles[name]["light"]["upload_bytes"] >= profiles[name]["main"]["upload_bytes"]:
            raise RuntimeError(f"light tier upload is not smaller for {name}")

    # Discard two complete warm-up rounds. Rotate the balanced sequence
    # to avoid attributing a fixed position in each timing round to one tier.
    trials = [(name, mode) for name in IMAGES for mode in SIDE]
    for index in range(repetitions + 2):
        start = index % len(trials)
        for name, mode in trials[start:] + trials[:start]:
            side = SIDE[mode]
            source = samples[name]
            if mode == "local":
                payload, prep_ms = source, 0.0
            else:
                payload, prep_ms = timed_ms(transport_input, source, side)
            output, cpu_ms = timed_ms(detect_edges, payload, side)
            if sha256(output) != profiles[name][mode]["output_sha256"]:
                raise RuntimeError(f"detector output changed for {name}/{mode}")
            if index >= 2:
                durations[name, mode]["prepare"].append(prep_ms)
                durations[name, mode]["cpu"].append(cpu_ms)

    for (name, mode), timing in durations.items():
        profile = profiles[name][mode]
        profile.update({
            "cpu_ms": statistics.median(timing["cpu"]),
            "prepare_ms": statistics.median(timing["prepare"]),
            "cpu_samples_ms": timing["cpu"],
            "prepare_samples_ms": timing["prepare"],
        })

    return {
        "format": "rdinp-workload-calibration-v1",
        "scope": "development, local CPU and three scikit-image sample PNGs",
        "runtime": {"python": platform.python_version(), "pillow": PIL.__version__,
                    "system": platform.system(), "machine": platform.machine(),
                    "processor": platform.processor()},
        "workload_sha256": sha256((WORKER_DIR / "image_workload.py").read_bytes()),
        "input_fixtures": inputs,
        "measurement": {
            "repetitions_per_image_tier": repetitions,
            "discarded_warmups_per_image_tier": 2,
            "cpu_ms": "Warm median wall time for existing image_workload.detect_edges.",
            "prepare_ms": "Warm median grayscale, resize and PNG encoding before edge upload.",
            "payload_bytes": "Exact application PNG body size. Excludes network headers, control and retransmission. Local tier has zero wire bytes.",
            "utility": "Soft Dice 2*sum(min(ref,pred))/sum(ref+pred) with bilinear alignment to the same 512x512 grid and 4-pixel border discarded. Reference is the main output of that source. This is an edge-map proxy without external labels.",
        },
        "workloads": profiles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "calibration.json")
    parser.add_argument("--repetitions", type=int, default=45)
    args = parser.parse_args()
    if args.repetitions < len(IMAGES) * len(SIDE):
        parser.error("--repetitions must cover one complete rotation (at least 9)")
    result = calibrate(args.assets, args.repetitions)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()

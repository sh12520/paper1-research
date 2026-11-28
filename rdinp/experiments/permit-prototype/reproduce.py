"""Reproduce the scoped live RDINP permit experiment in a fresh directory.

Example (Windows):
    py -3.11 -B rdinp/experiments/permit-prototype/reproduce.py --assets D:/fixtures --out D:/permit-reproduction

Optionally pass --python with an interpreter from an existing environment
that has the locked dependencies. Step 1 uses the archived simulation.
A valid SCIENTIFIC_STOP is a successfully reproduced decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RDINP = HERE.parents[1]
LOCK = RDINP / "requirements.txt"
STEP1 = HERE.parent / "structured-fast-slow" / "evidence" / "step1-20261128-r02"
VALID_DECISIONS = {"PROCEED_STEP3", "SCIENTIFIC_STOP"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locked_packages(path):
    """Read the exact pins and relative includes in this experiment's lock."""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.partition("#")[0].strip()
        if not entry:
            continue
        if entry.startswith("-r "):
            rows = locked_packages(path.parent / entry[3:].strip()).items()
        else:
            match = re.fullmatch(r"([a-zA-Z0-9_.-]+)==([a-zA-Z0-9_.+-]+)", entry)
            if match is None:
                raise ValueError(f"Expected an exact dependency pin in {path.name}: {entry}")
            rows = [match.groups()]
        for name, version in rows:
            if name in pins and pins[name] != version:
                raise ValueError(f"Conflicting versions for {name} in dependency lock")
            pins[name] = version
    return pins


def check_assets(assets):
    calibration = HERE.parent / "structured-fast-slow" / "calibration.json"
    required = json.loads(calibration.read_text(encoding="utf-8"))["input_fixtures"]
    hashes = {}
    for name, fixture in required.items():
        computed = digest(assets / name)
        if computed != fixture["sha256"]:
            raise ValueError(f"Input fixture digest mismatch: {name}")
        hashes[name] = computed
    return hashes


def write_record(path, data):
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    staging.replace(path)


def run_phase(name, args, output, record):
    log = output / f"{len(record['phases']) + 1:02d}-{name}.log"
    argv = [str(arg) for arg in args]
    progress = {"phase": name, "argv": argv, "log": log.name, "started_utc": utc_now(), "returncode": None}
    record["phases"].append(progress)
    write_record(output / "reproduction.json", record)
    started = time.perf_counter()
    print(f"Running {name}; log: {log}", flush=True)
    try:
        with log.open("xb") as stream:
            completed = subprocess.run(argv, cwd=RDINP, stdout=stream, stderr=subprocess.STDOUT)
        progress["returncode"] = completed.returncode
        completed.check_returncode()
    finally:
        progress["finished_utc"] = utc_now()
        progress["elapsed_s"] = time.perf_counter() - started
        write_record(output / "reproduction.json", record)


def reproduce(output, assets, existing_python):
    hashes = check_assets(assets)
    pins = locked_packages(LOCK)
    output.mkdir(parents=True, exist_ok=False)
    archive_refs = [
        STEP1 / name for name in ("plan.json", "AUDIT.json", "COMPLETE.json", "analysis/overall.csv")
    ]
    record = {
        "started_utc": utc_now(),
        "status": "RUNNING",
        "decision": None,
        "assets_sha256": hashes,
        "requirements_sha256": {
            path.relative_to(RDINP).as_posix(): digest(path)
            for path in (LOCK, RDINP / "protocol" / "c2" / "requirements.txt")
        },
        "locked_packages": pins,
        "step1_rerun": False,
        "step1_archive_sha256": {
            path.relative_to(RDINP).as_posix(): digest(path) for path in archive_refs if path.is_file()
        },
        "phases": [],
    }
    write_record(output / "reproduction.json", record)
    try:
        def phase(name, args):
            run_phase(name, args, output, record)

        if existing_python is None:
            environment = output / "environment"
            phase("create-venv", [sys.executable, "-m", "venv", environment])
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            phase("install-dependencies",
                  [python, "-m", "pip", "install", "--disable-pip-version-check", "-r", LOCK])
        else:
            python = existing_python

        pin_check = (
            "import importlib.metadata, json, sys\n"
            "expected = json.loads(sys.argv[1])\n"
            "observed = {package: importlib.metadata.version(package) for package in expected}\n"
            "print(json.dumps({'python': sys.version, 'packages': observed}))\n"
            "if observed != expected:\n"
            "    raise SystemExit('Locked dependency mismatch')\n"
        )
        verify = [python, "-B", "-c", pin_check, json.dumps(pins)]
        phase("verify-dependencies", verify)
        phase("release-safety", [python, "-B", HERE / "check_protocol.py", "--out", output / "safety"])
        phase("four-phase-c2", [python, "-B", HERE / "measure_c2.py", "--trials", "24",
                                "--out", output / "c2"])
        phase("scored-pairs", [python, "-B", HERE / "run_pairs.py", "--assets", assets,
                              "--out", output / "pairs"])
        gate = output / "gate.json"
        phase("decision", [
            python, "-B", HERE / "gate.py",
            "--pairs", output / "pairs",
            "--matrix", output / "safety" / "safety.json",
            "--c2", output / "c2" / "c2_cost.json",
            "--out", gate,
        ])
        findings = json.loads(gate.read_text(encoding="utf-8"))
        decision = findings.get("decision")
        if decision not in VALID_DECISIONS or findings.get("scientific_gate_evaluated") is not True:
            raise ValueError(f"Unexpected gate decision: {decision}")
        record.update(status="COMPLETE", decision=decision, gate_sha256=digest(gate))
        print(f"{decision}; net utility delta: {findings['net_utility_delta']}; gate: {gate}", flush=True)
    except subprocess.CalledProcessError as error:
        stage = record["phases"][-1]
        record.update(status="ENGINEERING_ERROR", error=f"{stage['phase']} exited {error.returncode}")
        print(f"{record['error']}; see {output / stage['log']}", file=sys.stderr)
        return error.returncode if error.returncode > 0 else 1
    except (OSError, ValueError, KeyError) as error:
        record.update(status="ENGINEERING_ERROR", error=str(error))
        print(f"Reproduction failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        record.update(status="INTERRUPTED")
        return 130
    finally:
        record["finished_utc"] = utc_now()
        write_record(output / "reproduction.json", record)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", type=Path, required=True, help="Directory with the three calibrated PNGs")
    parser.add_argument("--out", type=Path, required=True, help="New, unused reproduction directory")
    parser.add_argument("--python", type=Path, help="Optional interpreter from an existing locked environment")
    args = parser.parse_args()
    # A POSIX venv executable can be a symlink. Keep the venv path when invoking it.
    python = Path(os.path.abspath(args.python)) if args.python else None
    if python is not None and not python.is_file():
        parser.error("--python must point to an existing executable")
    try:
        return reproduce(args.out.resolve(), args.assets.resolve(), python)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())

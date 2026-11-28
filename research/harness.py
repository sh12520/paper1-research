#!/usr/bin/env python3
"""Shared, allowlisted research checks with optional immutable run receipts."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from time import time_ns
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "runs" / "research-harness"
OPV2V = Path("research/opv2v-deadline")
RDINP = Path("rdinp/experiments/durable-worker/evidence/g1a-20261128")
ATTEMPT = re.compile(r"[0-9]+-[a-f0-9]{12}\Z")
TERMINAL = {"passed", "failed", "interrupted"}


@dataclass(frozen=True)
class Task:
    description: str
    checker: Path
    inputs: tuple[Path, ...]


TASKS = {
    "opv2v-evidence": Task(
        "Verify the shared OPV2V and DAIR development evidence",
        OPV2V / "autoresearch/scripts/check_shared_assets.py",
        (OPV2V / "autoresearch", OPV2V / "src", OPV2V / "results"),
    ),
    "rdinp-g1a-evidence": Task(
        "Verify recorded RDINP G1-A plans and task-table exports",
        Path("research/verify_rdinp.py"),
        (RDINP,),
    ),
}


class HarnessError(Exception):
    """A reservation, receipt or execution invariant failed."""


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def snapshot(task):
    files = {Path(__file__).resolve(), ROOT / task.checker}
    for relative in task.inputs:
        path = ROOT / relative
        if not path.exists():
            raise HarnessError(f"Missing declared input: {relative}")
        if path.is_dir():
            files.update(item for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts)
        else:
            files.add(path)
    return {
        "files": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(files)},
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
    }


def read_object(path):
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise HarnessError(f"Expected a JSON object: {path}")
    return value


def publish(path, data):
    # Publish a complete file in the same directory, without overwriting an earlier result.
    file = tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}-", suffix=".pending", delete=False)
    pending = Path(file.name)
    try:
        with file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if os.name == "nt":
            pending.rename(path)
        else:
            os.link(pending, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        pending.unlink(missing_ok=True)


def publish_json(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    publish(path, data.encode("utf-8"))


@contextmanager
def lock_task(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a+b") as lock:
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise HarnessError(f"Could not acquire task lock: {directory.name}") from exc
        yield


def artifacts(directory):
    files = {}
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise HarnessError(f"Unexpected child in attempt: {path}")
        if path.name in {"reservation.json", "receipt.json"}:
            continue
        if path.name.endswith(".pending") and path.name.startswith((".reservation.json-", ".receipt.json-", ".output.log-")):
            continue
        files[path.name] = sha256(path)
    return files


def reservation(directory):
    record = read_object(directory / "reservation.json")
    expected = (1, directory.parent.name, directory.name)
    if (record["schema"], record["task"], record["attempt"]) != expected:
        raise HarnessError(f"Reservation identity mismatch: {directory}")
    if record["input_sha256"] != json_digest(record["inputs"]):
        raise HarnessError(f"Reservation input digest mismatch: {directory}")
    return record


def finish(directory, status, exit_code):
    record = {
        "reservation_sha256": sha256(directory / "reservation.json"),
        "status": status,
        "exit_code": exit_code,
        "artifacts": artifacts(directory),
    }
    publish_json(directory / "receipt.json", {**record, "receipt_sha256": json_digest(record)})


def verify(directory):
    expected = reservation(directory)
    receipt = read_object(directory / "receipt.json")
    if receipt.pop("receipt_sha256") != json_digest(receipt):
        raise HarnessError(f"Receipt digest mismatch: {directory}")
    if receipt["reservation_sha256"] != sha256(directory / "reservation.json"):
        raise HarnessError(f"Receipt does not match reservation: {directory}")
    if receipt["status"] not in TERMINAL or receipt["artifacts"] != artifacts(directory):
        raise HarnessError(f"Receipt status or artifact mismatch: {directory}")
    return expected, receipt


def attempts(directory):
    if directory.is_dir():
        return sorted((path for path in directory.iterdir()
                       if not path.is_symlink() and path.is_dir() and ATTEMPT.fullmatch(path.name)), reverse=True)
    return []


def recover(directory):
    count = 0
    for attempt in attempts(directory):
        if (attempt / "receipt.json").exists() or not (attempt / "reservation.json").is_file():
            continue
        reservation(attempt)
        finish(attempt, "interrupted", None)
        count += 1
    return count


def execute(task, capture=False):
    command = [sys.executable, "-B", "-E", str(ROOT / task.checker)]
    return subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None, check=False)


def run_task(directory, task):
    with lock_task(directory):
        recover(directory)
        inputs = snapshot(task)
        identity = json_digest(inputs)
        reusable = None
        for prior in attempts(directory):
            if not (prior / "reservation.json").is_file():
                continue
            saved, receipt = verify(prior)
            if reusable is None and saved["input_sha256"] == identity and receipt["status"] == "passed":
                reusable = prior
        if reusable is not None:
            print(f"Reused verified attempt {reusable.name}: {reusable}")
            return 0
        attempt = directory / f"{time_ns()}-{uuid4().hex[:12]}"
        attempt.mkdir()
        publish_json(attempt / "reservation.json", {
            "schema": 1, "task": directory.name, "attempt": attempt.name,
            "inputs": inputs, "input_sha256": identity,
        })
        result = execute(task, capture=True)
        publish(attempt / "output.log", result.stdout)
        unchanged = snapshot(task) == inputs
        passed = result.returncode == 0 and unchanged
        finish(attempt, "passed" if passed else "failed", result.returncode)
        print(f"{'Passed' if passed else 'Failed'} attempt {attempt.name}: {attempt}")
        if not unchanged:
            print("Input snapshot changed during the check.", file=sys.stderr)
        return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=STATE, help="local directory for run receipts")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="list supported tasks")
    for action in ("check", "run", "verify", "recover"):
        subparser = actions.add_parser(action)
        subparser.add_argument("task", choices=TASKS)
        if action == "verify":
            subparser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    if args.action == "list":
        for name, task in TASKS.items():
            print(f"{name}: {task.description}")
        return 0
    directory = args.state_dir.resolve() / args.task
    task = TASKS[args.task]
    if args.action == "check":
        return execute(task).returncode
    if args.action == "run":
        return run_task(directory, task)
    if args.action == "recover":
        with lock_task(directory):
            print(f"Recorded {recover(directory)} interrupted attempts.")
        return 0
    if not ATTEMPT.fullmatch(args.attempt):
        raise HarnessError("Invalid attempt identifier")
    _, receipt = verify(directory / args.attempt)
    print(f"Verified attempt {args.attempt}: {receipt['status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HarnessError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Research harness: {error}", file=sys.stderr)
        raise SystemExit(1) from error

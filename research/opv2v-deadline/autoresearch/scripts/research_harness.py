#!/usr/bin/env python3
"""Run and verify the local project's allowlisted research tasks."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import traceback
from uuid import uuid4

from research_harness_tasks import tasks


PROJECT = Path(__file__).resolve().parents[1]
STATE_ROOT = PROJECT / "experiments" / "research-harness"
SCHEMA = 1
RESERVATION = "reservation.json"
RECEIPT = "receipt.json"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
TERMINAL = {"passed", "blocked", "failed", "interrupted"}


class HarnessError(Exception):
    """An execution contract or evidence integrity check failed."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(value):
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path):
    checksum = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def input_identity(task):
    paths = {Path(__file__).resolve(), Path(__file__).with_name("research_harness_tasks.py").resolve()}
    for entry in task["inputs"]:
        path = (PROJECT / entry).resolve()
        paths.add(path)
    files = {}
    for path in sorted(paths):
        display = str(path.relative_to(PROJECT)) if path.is_relative_to(PROJECT) else str(path)
        files[display] = file_sha256(path) if path.is_file() else None
    return {"files": files, "python": sys.version.split()[0]}


def task_dir(name):
    path = STATE_ROOT / name
    if not path.resolve().is_relative_to(PROJECT):
        raise HarnessError(f"State directory resolves outside the project: {path}")
    return path


@contextmanager
def locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HarnessError(f"Task is already running: {directory.name}") from exc
        yield


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HarnessError(f"Expected a JSON object: {path}")
    return value


def write_once(path, value):
    tmp = path.parent / f".{path.name}-{uuid4().hex}.pending"
    try:
        with tmp.open("x", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.link(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)


def attempt_dirs(directory):
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_dir() and not p.is_symlink())


def outputs(directory):
    artifacts = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            raise HarnessError(f"Unexpected symlink in evidence: {path}")
        if path.is_dir() or relative in {RESERVATION, RECEIPT}:
            continue
        if any(relative.startswith(f".{name}-") for name in (RESERVATION, RECEIPT)) and relative.endswith(".pending"):
            continue
        if not path.is_file():
            raise HarnessError(f"Unexpected non-file evidence: {path}")
        artifacts[relative] = file_sha256(path)
    return artifacts


def verify_receipt(directory):
    snapshot = read_json(directory / RESERVATION)
    receipt = read_json(directory / RECEIPT)
    if snapshot.get("schema") != SCHEMA or snapshot.get("attempt") != directory.name:
        raise HarnessError(f"Invalid reservation schema or attempt identity: {directory}")
    if snapshot.get("task") != directory.parent.name:
        raise HarnessError(f"Reservation belongs to a different task: {directory}")
    if snapshot.get("identity") != digest(snapshot.get("inputs")):
        raise HarnessError(f"Reservation input digest mismatch: {directory}")
    checksum = receipt.pop("receipt_sha256", None)
    if checksum != digest(receipt):
        raise HarnessError(f"Receipt digest mismatch: {directory}")
    if receipt.get("reservation_sha256") != file_sha256(directory / RESERVATION):
        raise HarnessError(f"Reservation does not match receipt: {directory}")
    if receipt.get("result", {}).get("status") not in TERMINAL:
        raise HarnessError(f"Invalid terminal status: {directory}")
    if outputs(directory) != receipt.get("outputs"):
        raise HarnessError(f"Evidence files do not match receipt: {directory}")
    return receipt["result"]


def finish(directory, result):
    receipt = {
        "reservation_sha256": file_sha256(directory / RESERVATION),
        "finished_at": now(),
        "result": result,
        "outputs": outputs(directory),
    }
    write_once(directory / RECEIPT, {**receipt, "receipt_sha256": digest(receipt)})


def recover_attempts(directory):
    recovered = []
    for attempt in attempt_dirs(directory):
        if (attempt / RECEIPT).exists():
            continue
        reservation = attempt / RESERVATION
        if not reservation.is_file():
            continue
        finish(attempt, {
            "status": "interrupted",
            "summary": "The earlier attempt lost its task lock before a terminal receipt was published.",
        })
        recovered.append(attempt.name)
    return recovered


def run_task(name, task):
    directory = task_dir(name)
    with locked(directory):
        recovered = recover_attempts(directory)
        inputs = input_identity(task)
        missing = [path for path, checksum in inputs["files"].items() if checksum is None]
        identity = digest(inputs)
        if not task.get("live", False):
            for attempt in reversed(attempt_dirs(directory)):
                if not (attempt / RESERVATION).is_file() or not (attempt / RECEIPT).is_file():
                    continue
                if read_json(attempt / RESERVATION).get("identity") != identity:
                    continue
                if read_json(attempt / RECEIPT).get("result", {}).get("status") == "passed":
                    result = verify_receipt(attempt)
                    return {**result, "task": name, "attempt": attempt.name, "reused": True,
                            "recovered": recovered}

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        attempt = directory / f"{stamp}-{uuid4().hex[:8]}"
        attempt.mkdir()
        write_once(attempt / RESERVATION, {
            "schema": SCHEMA, "task": name, "attempt": attempt.name, "reserved_at": now(),
            "pid": os.getpid(), "identity": identity, "inputs": inputs,
        })
        try:
            if missing:
                result = {"status": "blocked", "summary": "Required inputs are missing",
                          "missing": missing}
            else:
                result = task["run"](attempt)
            if not isinstance(result, dict) or result.get("status") not in TERMINAL - {"interrupted"}:
                raise HarnessError("Task callback must return passed, blocked or failed in result.status")
            if input_identity(task) != inputs:
                raise HarnessError("Declared inputs changed while task was running")
            digest(result)
        except KeyboardInterrupt:
            result = {"status": "interrupted", "summary": "Task was interrupted"}
        except (Exception, SystemExit) as exc:
            (attempt / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
            result = {"status": "failed", "summary": str(exc)}
        finish(attempt, result)
        return {**result, "task": name, "attempt": attempt.name, "reused": False,
                "recovered": recovered}


def status(name):
    history = []
    for attempt in attempt_dirs(task_dir(name)):
        record = {"attempt": attempt.name, "status": "unsealed"}
        try:
            if (attempt / RESERVATION).is_file():
                record["identity"] = read_json(attempt / RESERVATION).get("identity")
            if (attempt / RECEIPT).is_file():
                record.update(read_json(attempt / RECEIPT)["result"])
        except (KeyError, ValueError, OSError, HarnessError) as exc:
            record.update(status="invalid_receipt", summary=str(exc))
        history.append(record)
    return {"task": name, "attempts": history}


def cycle(registry):
    outcomes = []
    for name, task in registry.items():
        try:
            outcomes.append(run_task(name, task))
        except (HarnessError, OSError, ValueError, KeyError) as exc:
            outcomes.append({"task": name, "status": "failed", "summary": str(exc)})
    states = {result["status"] for result in outcomes}
    overall = next((value for value in ("failed", "interrupted", "blocked") if value in states),
                   "passed")
    return {"status": overall, "tasks": outcomes}


def main():
    registry = tasks(PROJECT)
    if any(not IDENTIFIER.fullmatch(name) for name in registry):
        raise HarnessError("Registry contains an invalid task name")
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="List registered tasks")
    subcommands.add_parser("status", help="Inspect the receipt ledger").add_argument(
        "task", choices=registry, nargs="?"
    )
    subcommands.add_parser("run", help="Execute or reuse a verified task").add_argument(
        "task", choices=registry
    )
    subcommands.add_parser("cycle", help="Run all registered checks without stopping at a blocked one")
    verify = subcommands.add_parser("verify", help="Hash-check a completed attempt")
    verify.add_argument("task", choices=registry)
    verify.add_argument("--attempt", help="Attempt name, defaults to newest")
    subcommands.add_parser("recover", help="Seal abandoned attempts as interrupted").add_argument(
        "task", choices=registry
    )
    args = parser.parse_args()
    try:
        if args.command == "list":
            value = [{"task": name, "description": task["description"], "live": task.get("live", False)}
                     for name, task in registry.items()]
        elif args.command == "status":
            value = status(args.task) if args.task else [status(name) for name in registry]
        elif args.command == "run":
            value = run_task(args.task, registry[args.task])
        elif args.command == "cycle":
            value = cycle(registry)
        elif args.command == "recover":
            directory = task_dir(args.task)
            with locked(directory):
                value = {"task": args.task, "recovered": recover_attempts(directory)}
        else:
            directories = attempt_dirs(task_dir(args.task))
            if args.attempt:
                directories = [p for p in directories if p.name == args.attempt]
            if not directories:
                raise HarnessError(f"No matching attempt: {args.task}")
            attempt = directories[-1]
            value = {**verify_receipt(attempt), "task": args.task, "attempt": attempt.name,
                     "verified": True}
    except (HarnessError, OSError, ValueError, KeyError) as exc:
        value = {"status": "failed", "summary": str(exc)}

    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    if isinstance(value, dict):
        code = value.get("status")
        if code == "blocked":
            return 2
        if code in {"failed", "interrupted"}:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

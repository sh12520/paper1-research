"""Transport and same-boot durable state tests, excluded from the paired comparison."""

import argparse
import base64
import json
from pathlib import Path
import secrets
import time

from offload_server import DurableLog
from run_pairs import Authenticator, ROOT, digest, json_save, load_assets, service, wait_until


def arm(rpc, task, cutoff):
    assert rpc.call("/arm", {"task_id": task, "cutoff_ns": cutoff})["status"] == "ARMED"


def payload_task(name, token, payload):
    return {"task_id": name, "token": token, "payload_b64": base64.b64encode(payload).decode()}


def expected_error(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("invalid authenticated envelope accepted")


def auth_checks(rpc):
    aim = {"task_id": "first"}
    wrong = Authenticator(secrets.token_bytes(32))
    _, raw = wrong.pack_request("/status", aim)
    assert rpc.transmit("/status", raw, 1)[0] == 401
    nonce, raw = rpc.auth.pack_request("/status", aim)
    assert rpc.transmit("/grant", raw, 1)[0] == 401
    assert b'"first"' in raw
    assert rpc.transmit("/status", raw.replace(b'"first"', b'"next"', 1), 1)[0] == 401
    status, reply = rpc.transmit("/status", raw, 1)
    assert status == 200
    correct = rpc.auth.unpack_reply("/status", nonce, reply)
    assert correct["task_id"] == "first" and correct["status"] == "ARMED"
    expected_error(lambda: rpc.auth.unpack_reply("/status", secrets.token_hex(16), reply))
    expected_error(lambda: rpc.auth.unpack_reply("/grant", nonce, reply))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    folder = args.out.resolve()
    if not folder.is_relative_to(ROOT) or folder == ROOT:
        raise ValueError("out must be new within this study")
    folder.mkdir(exist_ok=False)
    first, second, _ = load_assets(args.assets)
    key = secrets.token_bytes(32)
    json_save(folder / "config.json", {
        "method": "DIRECT_LEASE", "condition": "persistence_check",
        "inputs": {"first": digest(first[1]), "next": digest(second[1])},
    })
    log = DurableLog(folder / "app_events.jsonl")
    try:
        with service(folder, key, log) as (ready, rpc):
            cutoff = time.monotonic_ns() + 5_000_000_000
            arm(rpc, "first", cutoff)
            auth_checks(rpc)
            original = rpc.call("/grant", {"task_id": "first"})
            assert original["status"] == "GRANTED"
            first_pid = ready["pid"]
        with service(folder, key, log) as (ready, rpc):
            middle_pid = ready["pid"]
            recovered = rpc.call("/status", {"task_id": "first"})
            assert recovered == original, "live grant was not restored"
            wait_until(cutoff + 20_000_000)
            expired = rpc.call("/execute", payload_task("first", original["token"], first[1]))
            assert expired["status"] == "EXPIRED"
            assert rpc.call("/status", {"task_id": "first"})["status"] == "EXPIRED"
            arm(rpc, "next", time.monotonic_ns() + 1_500_000_000)
            second_grant = rpc.call("/grant", {"task_id": "next"})
            assert second_grant["status"] == "GRANTED"
            execute = payload_task("next", second_grant["token"], second[1])
            completed = rpc.call("/execute", execute)
            assert completed["status"] == "RESULT"
            assert completed["result_sha256"] == second[2]["edge"]
        with service(folder, key, log) as (ready, rpc):
            last_pid = ready["pid"]
            replay = rpc.call("/execute", execute)
            assert replay == completed
    finally:
        log.close()
    events = [json.loads(line) for line in (folder / "worker_events.jsonl").read_text(encoding="utf-8").splitlines()]
    starts = [e for e in events if e["event"] == "APP_START"]
    assert len(starts) == 1 and starts[0]["task_id"] == "next"
    assert len({first_pid, middle_pid, last_pid}) == 3
    assert sum(e["event"] == "AUTH_OR_FRAMING_REJECT" for e in events) == 3
    result = {
        "wrong_key_and_body_and_route_rejected": True,
        "wrong_reply_nonce_and_route_rejected": True,
        "live_grant_exact_after_restart": True,
        "expired_first_never_started": True,
        "next_executed_once": True,
        "completed_result_exact_after_restart": True,
        "worker_pids": [first_pid, middle_pid, last_pid],
        "scope": "same-host graceful process restart with no inflight computation",
    }
    json_save(folder / "checks.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()


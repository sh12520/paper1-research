"""Independent edge controls before running the paired study."""

import argparse
from pathlib import Path
import time

from edge_worker import EdgeEndpoint
from run_study import EventLog, call_worker, digest, json_save


def use(case):
    log = EventLog()
    invocations = []
    payload = b"mechanism-control"
    request = {"task_id": case}

    def task(raw):
        invocations.append(raw)
        return raw.upper()

    import base64

    with EdgeEndpoint(case, digest(payload), task, log.emit) as edge:
        now = time.monotonic_ns()
        edge.arm(now + (60_000_000 if case == "expired_activation" else 1_000_000_000))
        grant = call_worker(edge, log, "/grant", request, now + 500_000_000)
        assert grant and grant["status"] == "GRANTED"
        body = {**request, "token": grant["token"], "payload_b64": base64.b64encode(payload).decode()}
        if case == "expired_activation":
            time.sleep(0.085)
            result = call_worker(edge, log, "/execute", body, now + 500_000_000)
            assert result["status"] != "RESULT" and len(invocations) == 0
        elif case == "wrong_token":
            result = call_worker(edge, log, "/execute", {**body, "token": "invalid"}, now + 500_000_000)
            assert result["status"] != "RESULT" and len(invocations) == 0
        else:
            result = call_worker(edge, log, "/execute", body, now + 500_000_000)
            retry = call_worker(edge, log, "/execute", body, now + 500_000_000)
            assert result == retry and result["status"] == "RESULT" and len(invocations) == 1
            assert result["result_sha256"] == digest(payload.upper())
    return {"case": case, "passed": True, "executions": len(invocations), "events": log.events}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    checks = [use(name) for name in ("expired_activation", "wrong_token", "duplicate_activation")]
    json_save(args.out, checks)
    for check in checks:
        print(check["case"], "PASS")


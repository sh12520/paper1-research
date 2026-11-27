"""Independent localhost process for the paired service lifecycle experiment."""

import argparse
import base64
import http.server
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

from signed_rpc import Authenticator
from task_store import TaskStore

ROOT = Path(__file__).resolve().parent
C2 = ROOT.parent / "RDINP_PREFLIGHT_20261127-123820" / "runs" / "source"
DEV1 = ROOT.parent / "SERVICE_WORKER_DEV_01"
sys.path[:0] = [str(C2), str(DEV1)]

from authority import Authority
from contracts import example_contract
from crypto import Identity, Trust
from endpoint import Responder
from events import Clock, Trace
from run_study import compute_edge

MAX_BODY = 2_500_000
KEY_ENV = "RDINP_DEV02_EPHEMERAL_HMAC"


class DurableLog:
    """Single-process append-only clock records. Experiment diagnostics only."""

    def __init__(self, path):
        self.file = path.open("a", encoding="utf-8", buffering=1)
        self.lock = threading.Lock()

    def __call__(self, event, **fields):
        with self.lock:
            self.file.write(json.dumps({
                "event": event, "monotonic_ns": time.monotonic_ns(),
                "pid": os.getpid(), **fields,
            }, ensure_ascii=True) + "\n")
            self.file.flush()

    def close(self):
        with self.lock:
            self.file.close()


class OffloadServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, config, directory, auth):
        super().__init__(("127.0.0.1", 0), Handler)
        self.config = config
        self.auth = auth
        self.armed = {}
        self.log = DurableLog(directory / "worker_events.jsonl")
        self.store = TaskStore(directory / "task_store.sqlite", config["inputs"], compute_edge, self.log)

    def block_first(self, task_id):
        return (
            self.config["condition"] == "first_proof_blackout"
            and task_id == "first"
            and time.monotonic_ns() < self.armed.get("first", 0)
        )

    def dispatch(self, route, payload):
        if route == "/shutdown" and payload == {}:
            return {"status": "STOPPING"}, False
        task = payload.get("task_id")
        if task not in self.config["inputs"]:
            return {"status": "UNKNOWN_TASK"}, False
        if route == "/arm" and set(payload) == {"task_id", "cutoff_ns"}:
            cutoff = payload["cutoff_ns"]
            current = time.monotonic_ns()
            ceiling_ns = 6_000_000_000 if self.config["condition"] == "persistence_check" else 2_000_000_000
            if type(cutoff) is not int or not current < cutoff <= current + ceiling_ns:
                raise ValueError("invalid case cutoff")
            outcome = self.store.arm(task, cutoff)
            self.armed.setdefault(task, cutoff)
            return outcome, False
        if route == "/grant" and set(payload) == {"task_id"}:
            if self.config["method"] != "DIRECT_LEASE":
                return {"status": "FORBIDDEN", "task_id": task}, False
            outcome = self.store.grant(task)
            return outcome, outcome["status"] == "GRANTED" and self.block_first(task)
        if route == "/status" and set(payload) == {"task_id"}:
            if self.block_first(task):
                return {"status": "SUPPRESSED", "task_id": task}, True
            return self.store.status(task), False
        if route == "/execute" and set(payload) == {"task_id", "token", "payload_b64"}:
            data = base64.b64decode(payload["payload_b64"], validate=True)
            return self.store.execute(task, payload["token"], data), False
        return {"status": "INVALID_REQUEST", "task_id": task}, False


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        owner = self.server
        try:
            self.connection.settimeout(2)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("body size")
            nonce, payload = owner.auth.unpack_request(self.path, self.rfile.read(length))
        except (ValueError, OSError):
            owner.log("AUTH_OR_FRAMING_REJECT", route=self.path)
            self.reply(401, b"{}")
            return
        task = payload.get("task_id")
        owner.log("RPC_RECEIVED", task_id=task, route=self.path, body_bytes=length)
        try:
            result, suppressed = owner.dispatch(self.path, payload)
        except (TypeError, ValueError):
            self.reply(400, owner.auth.pack_reply(self.path, nonce, {"status": "INVALID_REQUEST"}))
            return
        if suppressed:
            owner.log("RPC_REPLY_SUPPRESSED", route=self.path, task_id=task)
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return
        body = owner.auth.pack_reply(self.path, nonce, result)
        try:
            self.reply(200, body)
        except OSError:
            owner.log("RPC_REPLY_IO_FAILURE", route=self.path, task_id=task)
        else:
            owner.log("RPC_REPLY", route=self.path, task_id=task, body_bytes=len(body), status=result["status"])
        if self.path == "/shutdown" and result["status"] == "STOPPING":
            threading.Thread(target=owner.shutdown, daemon=True).start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    directory = parser.parse_args().case.resolve()
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    secret = bytes.fromhex(os.environ.pop(KEY_ENV))
    server = OffloadServer(config, directory, Authenticator(secret))
    ready = {"worker_port": server.server_port, "pid": os.getpid()}
    responder = None
    authority = None
    try:
        if config["method"] == "C2_AUTH_QUERY":
            who = Identity("authority", "responder")
            c2_trace = Trace("responder", Clock("DEV02-LOCAL", "c2-authority"), directory / "c2_server.jsonl")
            authority = Authority(directory / "c2_quota.sqlite", example_contract(), c2_trace.clock, c2_trace, capacity=1)
            pinned = Trust([config["initiator_pin"], who.pin()])

            def c2_reply(message, kind, body):
                task = message["negotiationId"]
                if kind == "RECEIPT" and body["status"] == "COMMITTED":
                    result = server.store.grant(task)
                    server.log("C2_COMMITTED_HOOK", task_id=task, permit_status=result["status"])
                    if server.block_first(task):
                        server.log("C2_REPLY_SUPPRESSED", task_id=task, phase=message["phase"])
                        return {"drop": True}
                return {}

            responder = Responder(authority, who, pinned, c2_trace, c2_reply).start()
            ready.update({"c2_port": responder.port, "authority_pin": who.pin()})
        server.log("SERVER_START")
        print(json.dumps(ready), flush=True)
        server.serve_forever(poll_interval=0.02)
    finally:
        if responder is not None:
            responder.close()
        if authority is not None:
            snapshot = authority.snapshot()
            evidence = {
                "negotiations": [{"task_id": n["neg"], "state": n["state"], "units": n["units"]}
                                 for n in snapshot["negotiations"]],
                "effects": [{"task_id": e["neg"], "event": e["event"]} for e in snapshot["effects"]],
            }
            (directory / "c2_quota_final.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        server.store.close()
        server.log("SERVER_END")
        server.server_close()
        server.log.close()


if __name__ == "__main__":
    main()


"""Authenticated loopback RPC and directional application fault windows for G1-A."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import socket
import threading
import time

from signed_rpc import Authenticator

MAX_BODY = 2_500_000
ROUTES = {
    "/grant": {"task_id"},
    "/status": {"task_id"},
    "/execute": {"task_id", "token", "payload_b64"},
    "/cancel": {"task_id"},
}


class Events:
    """Serialize records from endpoint threads in a common host monotonic domain."""

    def __init__(self, path: Path, run_id: str, pair_id: str, method: str):
        self._file = path.open("x", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()
        boot_path = Path("/proc/sys/kernel/random/boot_id")
        boot = boot_path.read_text(encoding="ascii").strip() if boot_path.is_file() else run_id
        self._common = {
            "run_id": run_id,
            "pair_id": pair_id,
            "method": method,
            "host": platform.node(),
            "boot": boot,
            "clock": "host-monotonic",
            "pid": os.getpid(),
        }
        self.count = 0

    def __call__(self, event, **fields):
        task_id = fields.get("task_id")
        with self._lock:
            record = {
                **self._common,
                "index": self.count,
                "event": event,
                "monotonic_ns": time.monotonic_ns(),
                "task_id": task_id,
                "negotiationId": task_id,
                **fields,
            }
            self._file.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            self.count += 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._file.close()


class FaultWindows:
    """Fixed offsets in a shared scenario clock, independent of RPC order."""

    def __init__(self, start_ns, windows):
        self.start_ns = start_ns
        self.windows = windows

    def suppresses(self, direction, route, timestamp_ns):
        offset = timestamp_ns - self.start_ns
        return any(
            window["direction"] == direction
            and route in window["routes"]
            and window["start_ns"] <= offset < window["end_ns"]
            for window in self.windows
        )


class EdgeHTTP(ThreadingHTTPServer):
    def __init__(self, store, auth, fault, log, approval):
        super().__init__(("127.0.0.1", 0), EdgeHandler)
        self.store = store
        self.auth = auth
        self.fault = fault
        self.log = log
        self.approval = approval
        self.errors = []

    def dispatch(self, route, payload):
        task_id = payload["task_id"]
        if route == "/grant":
            if self.approval is not None:
                proof = self.approval.committed(task_id)
                if proof is None:
                    return {"task_id": task_id, "status": "PENDING_AUTHORIZATION"}
                if not proof["c2_commit_before_lease"]:
                    self.log("C2_AUTHORIZATION_LATE", task_id=task_id, approval=proof)
                    return {"task_id": task_id, "status": "EXPIRED"}
                self.log("C2_PROOF_CHECKED_FOR_GRANT", task_id=task_id, approval=proof)
            return self.store.grant(task_id)
        if route == "/status":
            return self.store.status(task_id)
        if route == "/execute":
            data = base64.b64decode(payload["payload_b64"], validate=True)
            return self.store.execute(task_id, payload["token"], data)
        return self.store.cancel(task_id, reason="terminal_cancel")


class EdgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _write(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _drop(self):
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def do_POST(self):
        server = self.server
        self.connection.settimeout(2.0)
        if self.path not in ROUTES:
            self._write(404, b"{}")
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not 0 < int(lengths[0]) <= MAX_BODY:
                raise ValueError("invalid body length")
            raw = self.rfile.read(int(lengths[0]))
            attempt, payload = server.auth.unpack_request(self.path, raw)
            if payload.keys() != ROUTES[self.path] or not isinstance(payload["task_id"], str):
                raise ValueError("invalid request fields")
        except (ValueError, OSError):
            server.log("RPC_REJECT", endpoint="edge", route=self.path)
            self._write(400, b"{}")
            return

        fields = {"task_id": payload["task_id"], "route": self.path, "attempt": attempt}
        server.log("RPC_RX", endpoint="edge", direction="uplink", body_bytes=len(raw), **fields)
        gate_ns = time.monotonic_ns()
        if server.fault.suppresses("uplink", self.path, gate_ns):
            server.log("RPC_DROP", endpoint="edge", direction="uplink", fault_gate_ns=gate_ns, **fields)
            self._drop()
            return

        try:
            result = server.dispatch(self.path, payload)
            reply = server.auth.pack_reply(self.path, attempt, result)
        except Exception as exc:
            server.errors.append(exc)
            server.log("EDGE_ERROR", endpoint="edge", detail=type(exc).__name__, **fields)
            self._drop()
            return
        gate_ns = time.monotonic_ns()
        if server.fault.suppresses("downlink", self.path, gate_ns):
            server.log("RPC_DROP", endpoint="edge", direction="downlink", fault_gate_ns=gate_ns,
                       status=result["status"], body_bytes=len(reply), **fields)
            self._drop()
            return
        try:
            self._write(200, reply)
        except OSError as exc:
            server.log("RPC_IO_FAILURE", endpoint="edge", direction="downlink",
                       detail=type(exc).__name__, **fields)
        else:
            server.log("RPC_TX", endpoint="edge", direction="downlink",
                       status=result["status"], body_bytes=len(reply), **fields)


@contextmanager
def serve(store, key, fault, log, approval=None):
    with EdgeHTTP(store, Authenticator(key), fault, log, approval) as server:
        listener = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        listener.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            listener.join()
    if server.errors:
        raise RuntimeError("edge execution error") from server.errors[0]


class Client:
    def __init__(self, port, key, log, terminal):
        self.port = port
        self.auth = Authenticator(key)
        self.log = log
        self.terminal = terminal

    def call(self, route, task_id, cutoff_ns, **arguments):
        remaining = (cutoff_ns - time.monotonic_ns()) / 1_000_000_000
        if remaining <= 0:
            return None
        attempt, body = self.auth.pack_request(route, {"task_id": task_id, **arguments})
        fields = {
            "endpoint": "terminal",
            "terminal": self.terminal,
            "task_id": task_id,
            "route": route,
            "attempt": attempt,
        }
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=min(remaining, 0.04))
        self.log("RPC_TX", direction="uplink", body_bytes=len(body), **fields)
        try:
            connection.request("POST", route, body=body, headers={"Content-Type": "application/json"})
            reply = connection.getresponse()
            data = reply.read(MAX_BODY + 1)
        except (OSError, http.client.HTTPException) as exc:
            self.log("RPC_IO_FAILURE", direction="downlink", detail=type(exc).__name__, **fields)
            return None
        finally:
            connection.close()
        if reply.status != 200 or not 0 < len(data) <= MAX_BODY:
            raise ValueError("invalid edge reply")
        result = self.auth.unpack_reply(route, attempt, data)
        if result["task_id"] != task_id:
            raise ValueError("mismatched reply task")
        self.log("RPC_RX", direction="downlink", body_bytes=len(data), status=result["status"], **fields)
        return result

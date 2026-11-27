"""Single-task loopback edge worker shared by the service study methods."""

import base64
import binascii
from contextlib import suppress
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import threading
import time
from typing import Callable


MAX_JSON_BODY = 16 * 1024 * 1024


class EdgeEndpoint:
    def __init__(
        self,
        task_id: str,
        input_sha256: str,
        compute: Callable[[bytes], bytes],
        emit: Callable,
        grant_reply_fault: str = "none",
        grant_delay_s: float = 1.1,
    ):
        if grant_reply_fault not in {"none", "drop", "drop_once", "delay"}:
            raise ValueError("Unknown grant reply fault")
        self.task_id = task_id
        self.input_sha256 = input_sha256
        self.compute = compute
        self.emit = emit
        self.grant_reply_fault = grant_reply_fault
        self.grant_delay_s = grant_delay_s
        self._grant_replies = 0
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self._state = "UNARMED"
        self._until = 0
        self._token = None
        self._result = None
        self._timer = None

    def arm(self, admit_until_ns: int):
        """Set the first-activation cutoff in this host's monotonic clock."""
        with self._lock:
            if self._state != "UNARMED":
                raise RuntimeError("The worker cutoff can only be set once")
            self._state = "OPEN"
            self._until = admit_until_ns
            self._timer = threading.Timer(
                max(0, (admit_until_ns - time.monotonic_ns()) / 1e9),
                self._expire,
            )
            self._timer.daemon = True
            self._timer.start()

    def _expire_locked(self, now_ns: int):
        if self._state == "GRANTED" and now_ns >= self._until:
            self._state = "EXPIRED"
            self.emit(
                "EDGE_RELEASE", task_id=self.task_id,
                release_reason="expired_unused", admit_until_ns=self._until,
            )

    def _expire(self):
        with self._lock:
            self._expire_locked(time.monotonic_ns())

    def _reply(self, state: str):
        return {"status": state, "task_id": self.task_id}

    def _reject(self, reason: str):
        self.emit("EDGE_REJECT", task_id=self.task_id, reason=reason)
        return self._reply(reason)

    def _granted_reply(self):
        return {
            **self._reply("GRANTED"), "token": self._token,
            "lease_expiry_ns": self._until,
        }

    def grant(self, task_id: str) -> dict:
        with self._lock:
            if task_id != self.task_id:
                return self._reject("WRONG_TASK")
            if self._state == "UNARMED":
                return self._reject("UNARMED")
            now_ns = time.monotonic_ns()
            self._expire_locked(now_ns)
            if now_ns >= self._until:
                return self._reject("EXPIRED")
            if self._state == "OPEN":
                self._state = "GRANTED"
                self._token = secrets.token_hex(16)
                self.emit(
                    "EDGE_GRANT", task_id=task_id, admit_until_ns=self._until,
                )
            return self._granted_reply()

    def status(self, task_id: str) -> dict:
        with self._lock:
            if task_id != self.task_id:
                return self._reject("WRONG_TASK")
            now_ns = time.monotonic_ns()
            self._expire_locked(now_ns)
            if self._state == "GRANTED":
                return self._granted_reply()
            if self._state == "OPEN":
                return self._reply("EXPIRED" if now_ns >= self._until else "NOT_GRANTED")
            return self._reply(self._state)

    def execute(self, task_id: str, token: str, payload: bytes) -> dict:
        if task_id != self.task_id:
            return self._reject("WRONG_TASK")
        if sha256(payload).hexdigest() != self.input_sha256:
            return self._reject("WRONG_INPUT")
        with self._lock:
            now_ns = time.monotonic_ns()
            self._expire_locked(now_ns)
            if not isinstance(token, str) or not self._token or not secrets.compare_digest(
                token.encode("utf-8"), self._token.encode("ascii")
            ):
                return self._reject("INVALID_TOKEN")
            if self._result is not None:
                self.emit("EDGE_RESULT_REPLAY", task_id=task_id)
                return dict(self._result)
            if self._state == "EXECUTING":
                return self._reply("IN_PROGRESS")
            if now_ns >= self._until:
                return self._reject("EXPIRED")
            if self._state != "GRANTED":
                return self._reject("NOT_GRANTED")
            self._state = "EXECUTING"
            self.emit(
                "EDGE_START", task_id=task_id, admit_until_ns=self._until,
                activation_ns=now_ns, input_bytes=len(payload),
            )

        compute_started_ns = time.monotonic_ns()
        try:
            result = self.compute(payload)
            elapsed_ns = time.monotonic_ns() - compute_started_ns
            reply = {
                **self._reply("RESULT"), "result_sha256": sha256(result).hexdigest(),
                "result_b64": base64.b64encode(result).decode("ascii"),
            }
        except Exception as error:
            elapsed_ns = time.monotonic_ns() - compute_started_ns
            reply = {**self._reply("COMPUTE_FAILED"), "error": type(error).__name__}

        with self._lock:
            self._state = "COMPLETED"
            self._result = reply
            self.emit(
                "EDGE_COMPLETE", task_id=task_id, status=reply["status"],
                compute_elapsed_ns=elapsed_ns, result_sha256=reply.get("result_sha256"),
            )
            self.emit("EDGE_RELEASE", task_id=task_id, release_reason="completed")
        return dict(reply)

    def _grant_reply_action(self, reply: dict):
        if reply["status"] != "GRANTED":
            return "none"
        with self._lock:
            self._grant_replies += 1
            if self.grant_reply_fault == "drop_once":
                return "drop" if self._grant_replies == 1 else "none"
            return self.grant_reply_fault

    def __enter__(self):
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                route = self.path
                self.connection.settimeout(5)
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                    if not 0 <= length <= MAX_JSON_BODY:
                        raise ValueError("Invalid content length")
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError("Incomplete body")
                    endpoint.emit("EDGE_HTTP_REQUEST", route=route, body_bytes=len(raw))
                    body = json.loads(raw)
                    if not isinstance(body, dict):
                        raise ValueError("Expected JSON object")
                    task_id = body["task_id"]
                    if route == "/grant":
                        reply = endpoint.grant(task_id)
                    elif route == "/status":
                        reply = endpoint.status(task_id)
                    elif route == "/execute":
                        payload = base64.b64decode(body["payload_b64"], validate=True)
                        reply = endpoint.execute(task_id, body["token"], payload)
                    else:
                        reply = endpoint._reply("UNKNOWN_ROUTE")
                except (ValueError, TypeError, KeyError, OSError, binascii.Error):
                    reply = endpoint._reject("BAD_REQUEST")

                action = endpoint._grant_reply_action(reply) if route == "/grant" else "none"
                raw = json.dumps(reply, separators=(",", ":")).encode("utf-8")
                if action == "drop":
                    endpoint.emit(
                        "EDGE_HTTP_RESPONSE_SUPPRESSED", route=route, body_bytes=0,
                        intended_body_bytes=len(raw), reason="injected_grant_reply_drop",
                    )
                    self.close_connection = True
                    with suppress(OSError):
                        self.connection.shutdown(socket.SHUT_RDWR)
                    return
                if action == "delay":
                    endpoint.emit(
                        "EDGE_HTTP_RESPONSE_DELAY", route=route,
                        injected_delay_s=endpoint.grant_delay_s,
                    )
                    endpoint._closing.wait(endpoint.grant_delay_s)
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    self.wfile.flush()
                except OSError:
                    endpoint.emit(
                        "EDGE_HTTP_RESPONSE_SUPPRESSED", route=route, body_bytes=0,
                        intended_body_bytes=len(raw), reason="connection_closed",
                    )
                else:
                    endpoint.emit("EDGE_HTTP_RESPONSE", route=route, body_bytes=len(raw))

        class Server(ThreadingHTTPServer):
            daemon_threads = False

        self._server = Server(("127.0.0.1", 0), Handler)
        self.host, self.port = self._server.server_address
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01},
            name="service-study-edge", daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._closing.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        if self._timer is not None:
            self._timer.cancel()
            self._timer.join()
        self._expire()

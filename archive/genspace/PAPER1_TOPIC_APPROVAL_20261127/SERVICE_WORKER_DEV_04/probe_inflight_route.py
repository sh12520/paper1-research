"""Observe a held old request during a real, isolated Caddy upstream replacement."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

from run_proxy_effect import (
    ROOT, backend, caddy_process, compute_edge, dump, header, patch, read_version, sha,
)


class Trace:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []

    def write(self, event, **fields):
        with self.lock:
            self.rows.append({"event": event, "timestamp_ns": time.monotonic_ns(), **fields})


@contextmanager
def held_backend(payload, trace):
    arrived = threading.Event()
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != "/task":
                self.send_error(404)
                return
            hold = self.headers.get("X-DEV04-Hold") == "1"
            if hold:
                trace.write("old_backend_arrived")
                arrived.set()
                if not release.wait(timeout=9):
                    self.send_error(504)
                    return
                trace.write("old_backend_released")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("X-DEV04-Backend", "A")
                self.end_headers()
                self.wfile.write(payload)
                if hold:
                    trace.write("old_backend_body_written", output_sha256=sha(payload))
            except OSError as exc:
                if hold:
                    trace.write("old_backend_write_error", type=type(exc).__name__)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.03}, daemon=True)
    thread.start()
    try:
        yield server.server_port, arrived, release
    finally:
        release.set()
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def data_plane(port, reference, trace, *, hold=False, timeout=0.3):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    headers = {"Connection": "close"}
    if hold:
        headers["X-DEV04-Hold"] = "1"
    sent = time.monotonic_ns()
    label = "old_client_reply" if hold else "fresh_client_reply"
    try:
        connection.request("GET", "/task", headers=headers)
        reply = connection.getresponse()
        body = reply.read(2_000_001)
        stamp = time.monotonic_ns()
        selected = header({"headers": dict(reply.getheaders())}, "X-DEV04-Backend")
        if reply.status == 200 and (selected not in reference or sha(body) != reference[selected]):
            raise AssertionError((reply.status, selected, sha(body)))
        result = {
            "status": reply.status, "backend": selected, "sha256": sha(body),
            "bytes": len(body), "sent_ns": sent, "observed_ns": stamp,
        }
    except (OSError, http.client.HTTPException) as exc:
        result = {
            "status": None, "backend": None, "error": type(exc).__name__,
            "sent_ns": sent, "observed_ns": time.monotonic_ns(),
        }
    finally:
        connection.close()
    trace.write(label, **result)
    return result


def run(directory, binary, assets, trace):
    a = compute_edge((assets / "camera.png").read_bytes())
    b = compute_edge((assets / "coffee.png").read_bytes())
    reference = {"A": sha(a), "B": sha(b)}
    marker = "dev04-held-" + uuid.uuid4().hex
    with held_backend(a, trace) as (a_port, arrived, release):
        with backend("B", b) as b_port:
            with caddy_process(binary, directory, {"dial": f"127.0.0.1:{a_port}"}, marker) as (admin, front, pid):
                trace.write("caddy_bound_loopback", pid=pid, admin_port=admin, data_port=front)
                original = read_version(admin)
                trace.write("read_initial_version", **original)
                initial = data_plane(front, reference, trace, timeout=2)
                assert initial["status"] == 200 and initial["backend"] == "A"
                with ThreadPoolExecutor(max_workers=2) as workers:
                    old = workers.submit(data_plane, front, reference, trace, hold=True, timeout=5)
                    latest = None
                    gate_start = None
                    release_stamp = None
                    try:
                        if not arrived.wait(timeout=2) or old.done():
                            raise RuntimeError("old request was not held at the actual backend")
                        change = workers.submit(patch, admin, {"dial": f"127.0.0.1:{b_port}"}, original["etag"])
                        gate_start = time.monotonic_ns()
                        limit = gate_start + 700_000_000
                        while time.monotonic_ns() < limit:
                            if latest is None:
                                candidate = data_plane(front, reference, trace, timeout=0.15)
                                if candidate["status"] == 200 and candidate["backend"] == "B":
                                    latest = candidate
                            if latest is not None and change.done():
                                break
                            time.sleep(0.02)
                    finally:
                        release_stamp = time.monotonic_ns()
                        trace.write("release_old_backend", release_ns=release_stamp)
                        release.set()
                    admin_response = change.result(timeout=4)
                    trace.write("admin_patch_response", **admin_response)
                    old_response = old.result(timeout=5)
                if admin_response["status"] != 200:
                    raise AssertionError(admin_response)
                fresh_after = data_plane(front, reference, trace, timeout=2)
                assert fresh_after["status"] == 200 and fresh_after["backend"] == "B"
    first_b = latest or fresh_after
    return {
        "scope": "one host, isolated Caddy process and local backend threads, held response control",
        "reference_sha256": reference,
        "old_backend_released_ns": release_stamp,
        "old_frontend_response": old_response,
        "first_new_B_frontend_response": first_b,
        "post_release_probe": fresh_after,
        "admin_patch_response": admin_response,
        "B_observed_while_old_backend_held": latest is not None,
        "admin_ack_observed_while_old_backend_held": admin_response["reply_ns"] < release_stamp,
        "old_A_response_observed_after_B": (
            old_response["status"] == 200 and old_response["backend"] == "A"
            and old_response["observed_ns"] > first_b["observed_ns"]
        ),
        "old_A_response_observed_after_admin_ack": (
            old_response["status"] == 200 and old_response["backend"] == "A"
            and old_response["observed_ns"] > admin_response["reply_ns"]
        ),
        "observed_hold_after_patch_submitted_ms": (release_stamp - gate_start) / 1e6,
        "monitor_pre_release_budget_ms": 700,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caddy", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    binary = args.caddy.resolve(strict=True)
    directory = args.out.resolve()
    if directory == ROOT or not directory.is_relative_to(ROOT):
        raise ValueError("output must be a new directory within DEV04")
    directory.mkdir(exist_ok=False)
    trace = Trace()
    try:
        result = run(directory, binary, args.assets.resolve(strict=True), trace)
        result["binary_sha256"] = sha(binary.read_bytes())
        result["source_sha256"] = sha(Path(__file__).read_bytes())
        dump(directory / "summary.json", result)
        print(json.dumps(result))
    finally:
        (directory / "events.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in trace.rows), encoding="utf-8"
        )


if __name__ == "__main__":
    main()


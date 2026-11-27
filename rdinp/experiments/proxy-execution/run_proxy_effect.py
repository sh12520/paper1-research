"""Observe actual config mutations and fresh HTTP readbacks on a private Caddy instance."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
DEV1 = ROOT.parent / "service-worker"
sys.path.insert(0, str(DEV1))
from run_study import compute_edge

UPSTREAM = "/config/apps/http/servers/dev04/routes/0/handle/0/upstreams/0"
OWNER = "/config/apps/http/servers/dev04/routes/0/handle/0/@id"
ASSETS = {"initial": "camera.png", "A": "astronaut.png", "B": "coffee.png"}
CASES = (
    "stale_unconditional", "stale_if_match", "expired_if_match",
    "aba_if_match", "aba_unique_id_if_match", "expired_dispatch_guard",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, payload):
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def call(port, method, path, payload=None, if_match=None):
    body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
    headers = {"Connection": "close"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if if_match is not None:
        headers["If-Match"] = if_match
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    sent = time.monotonic_ns()
    try:
        connection.request(method, path, body=body, headers=headers)
        reply = connection.getresponse()
        data = reply.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("unexpected large response")
        return {"status": reply.status, "headers": dict(reply.getheaders()), "body": data,
                "sent_ns": sent, "reply_ns": time.monotonic_ns()}
    finally:
        connection.close()


def header(reply, name):
    return next((v for k, v in reply["headers"].items() if k.lower() == name.lower()), None)


@contextmanager
def backend(name, payload):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != "/task":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-DEV04-Backend", name)
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.03}, daemon=True)
    worker.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        worker.join(timeout=3)
        server.server_close()


@contextmanager
def reserve_ports():
    with ExitStack() as stack:
        sockets = [stack.enter_context(socket.socket()) for _ in range(2)]
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        yield [sock.getsockname()[1] for sock in sockets]


@contextmanager
def caddy_process(binary, directory, initial, marker):
    with reserve_ports() as (admin, frontend):
        config = {
            "admin": {"listen": f"127.0.0.1:{admin}", "config": {"persist": False}},
            "storage": {"module": "file_system", "root": str(directory / "storage")},
            "apps": {"http": {"servers": {"dev04": {
                "listen": [f"127.0.0.1:{frontend}"],
                "automatic_https": {"disable": True},
                "routes": [{"handle": [{"handler": "reverse_proxy", "@id": marker,
                                        "upstreams": [initial]}]}],
            }}}},
        }
        dump(directory / "caddy.json", config)
    with (directory / "caddy.log").open("wb") as log:
        process = subprocess.Popen(
            [str(binary), "run", "--config", str(directory / "caddy.json")],
            cwd=directory, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        owned = False
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    ready = call(admin, "GET", OWNER)
                    if ready["status"] == 200 and json.loads(ready["body"]) == marker:
                        owned = True
                        break
                except (OSError, http.client.HTTPException, ValueError):
                    pass
                time.sleep(0.04)
            if not owned:
                raise RuntimeError("owned Caddy listener did not start; see " + str(directory / "caddy.log"))
            yield admin, frontend, process.pid
        finally:
            if process.poll() is None and owned:
                try:
                    identity = call(admin, "GET", OWNER)
                    if identity["status"] == 200 and json.loads(identity["body"]) == marker:
                        call(admin, "POST", "/stop")
                        process.wait(timeout=5)
                except (OSError, http.client.HTTPException, ValueError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def read_version(port):
    response = call(port, "GET", UPSTREAM)
    tag = header(response, "etag")
    if response["status"] != 200 or not tag:
        raise AssertionError((response["status"], response["body"], tag))
    return {
        "etag": tag, "value": json.loads(response["body"]),
        "sent_ns": response["sent_ns"], "observed_ns": response["reply_ns"],
    }


def patch(port, value, tag, deadline_ns=None):
    if deadline_ns is not None and time.monotonic_ns() >= deadline_ns:
        return {"status": None, "manager_rejected": True, "observed_ns": time.monotonic_ns()}
    response = call(port, "PATCH", UPSTREAM, value, if_match=tag)
    return {k: v for k, v in response.items() if k not in ("headers", "body")} | {
        "response_body": response["body"].decode("utf-8", errors="replace"),
        "request_if_match": tag,
    }


def readback(port, reference):
    reply = call(port, "GET", "/task")
    selected = header(reply, "x-dev04-backend")
    actual = sha(reply["body"])
    if reply["status"] != 200 or selected not in reference or reference[selected] != actual:
        raise AssertionError((reply["status"], selected, actual))
    return {"backend": selected, "sha256": actual, "bytes": len(reply["body"]),
            "observed_ns": reply["reply_ns"]}


def run_case(directory, binary, ports, reference, case):
    directory.mkdir()
    log = []

    def record(event, **details):
        log.append({"event": event, "recorded_ns": time.monotonic_ns(), **details})

    use_unique_ids = case == "aba_unique_id_if_match"
    is_aba = case.startswith("aba")
    deadline_case = case.startswith("expired")

    def value(route, generation):
        base = {"dial": f"127.0.0.1:{ports[route]}"}
        return {**base, "@id": f"generation-{generation}"} if use_unique_ids else base

    marker = "dev04-owned-" + uuid.uuid4().hex
    with caddy_process(binary, directory, value("initial", 0), marker) as (admin, public, pid):
        record("ready", pid=pid, admin_port=admin, frontend_port=public)
        before = readback(public, reference)
        record("initial_readback", **before)
        assert before["backend"] == "initial"
        original = read_version(admin)
        record("old_publisher_get", **original)
        tag = None if case == "stale_unconditional" else original["etag"]
        deadline_ns = time.monotonic_ns() + 100_000_000 if deadline_case else None
        gate = threading.Event()
        waiting = threading.Event()
        current = original

        def old_publisher():
            waiting.set()
            if not gate.wait(timeout=10):
                raise TimeoutError("publisher release not observed")
            cap = deadline_ns if case == "expired_dispatch_guard" else None
            return patch(admin, value("A", 3), tag, cap)

        with ThreadPoolExecutor(max_workers=1) as threads:
            outcome = threads.submit(old_publisher)
            try:
                assert waiting.wait(timeout=2) and not outcome.done()
                if deadline_case:
                    time.sleep(max(0, (deadline_ns + 25_000_000 - time.monotonic_ns()) / 1e9))
                    current = read_version(admin)
                    assert current["etag"] == original["etag"]
                    record("before_expired_dispatch", deadline_ns=deadline_ns, **current)
                else:
                    accepted = patch(admin, value("B", 1), original["etag"])
                    record("B_mutation", **accepted)
                    assert accepted["status"] == 200
                    seen = readback(public, reference)
                    assert seen["backend"] == "B"
                    record("B_readback", **seen)
                    current = read_version(admin)
                    if is_aba:
                        restore = patch(admin, value("initial", 2), current["etag"])
                        record("restore_mutation", **restore)
                        assert restore["status"] == 200
                        seen = readback(public, reference)
                        assert seen["backend"] == "initial"
                        record("restore_readback", **seen)
                        current = read_version(admin)
                record("old_publisher_released", same_etag=current["etag"] == original["etag"])
            finally:
                gate.set()
            effect = outcome.result(timeout=5)
        record("A_outcome", **effect)
        final = readback(public, reference)
        record("final_readback", **final)

    evidence = {
        "case": case, "A_status": effect["status"], "before_A_same_etag": current["etag"] == original["etag"],
        "before_A_value": current["value"], "initial_value": original["value"],
        "final_backend": final["backend"], "final_sha256": final["sha256"], "deadline_ns": deadline_ns,
        "A_sent_after_deadline": effect["sent_ns"] >= deadline_ns if deadline_ns and "sent_ns" in effect else None,
        "manager_rejected": effect.get("manager_rejected", False),
    }
    expected = {
        "stale_unconditional": (200, "A"),
        "stale_if_match": (412, "B"),
        "expired_if_match": (200, "A"),
        "expired_dispatch_guard": (None, "initial"),
    }
    if case in expected:
        evidence["matches_expected_control"] = (effect["status"], final["backend"]) == expected[case]
    else:
        evidence["matches_expected_control"] = (effect["status"], final["backend"]) in ((200, "A"), (412, "initial"))
    (directory / "events.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in log), encoding="utf-8"
    )
    dump(directory / "result.json", evidence)
    print(json.dumps(evidence), flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caddy", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    folder = args.out.resolve()
    if folder == ROOT or not folder.is_relative_to(ROOT):
        raise ValueError("output must be an unused directory within DEV04")
    folder.mkdir(exist_ok=False)
    binary = args.caddy.resolve(strict=True)
    raw = {k: (args.assets / path).read_bytes() for k, path in ASSETS.items()}
    png = {k: compute_edge(payload) for k, payload in raw.items()}
    reference = {k: sha(blob) for k, blob in png.items()}
    version = subprocess.check_output(
        [str(binary), "version"], cwd=folder, timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    ).decode().strip()
    with ExitStack() as stack:
        ports = {k: stack.enter_context(backend(k, blob)) for k, blob in png.items()}
        completed = [run_case(folder / name, binary, ports, reference, name)
                     for name in ((args.case,) if args.case else CASES)]
    dump(folder / "summary.json", {
        "scope": "one Windows host, separate Caddy process, real loopback reverse-proxy side effect, controlled publisher wait",
        "version": version, "binary_sha256": sha(binary.read_bytes()),
        "source_sha256": sha(Path(__file__).read_bytes()),
        "input_sha256": {k: sha(data) for k, data in raw.items()},
        "reference_png_sha256": reference, "cases": completed,
    })
    if not all(case["matches_expected_control"] for case in completed):
        raise SystemExit("one or more controls differed; raw evidence kept")


if __name__ == "__main__":
    main()


"""Exercise the sender/actuator deadline boundary using the real Caddy data plane."""

from contextlib import ExitStack, contextmanager
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

from run_proxy_effect import (
    ROOT, backend, caddy_process, call, compute_edge, dump, patch, read_version, readback, sha,
)


@contextmanager
def delivery_gate(admin_port, variant, expected, events):
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            received = time.monotonic_ns()
            if self.path != "/controlled-delivery":
                self.send_error(404)
                return
            length = int(self.headers["Content-Length"])
            command = json.loads(self.rfile.read(length))
            if command != expected:
                self.send_error(400)
                return
            cutoff = command["deadline_ns"]
            events["gateway_received_ns"] = received
            # Deterministically hold the delivery before it reaches the actuator.
            time.sleep(max(0, (cutoff + 25_000_000 - time.monotonic_ns()) / 1e9))
            decision = time.monotonic_ns()
            if variant == "actuator_gate" and decision >= cutoff:
                result = {"status": None, "received_late_and_rejected": True, "decision_ns": decision}
            else:
                result = patch(admin_port, command["new_value"], command["etag"])
            events["gateway_outcome"] = result
            body = json.dumps(result).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    gate = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=gate.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield gate.server_port
    finally:
        gate.shutdown()
        gate.server_close()
        thread.join(2)


def run_case(case, binary, ports, reference, variant):
    case.mkdir()
    trace = {}
    initial = {"dial": f"127.0.0.1:{ports['initial']}"}
    with caddy_process(binary, case, initial, "dev04-delivery-" + uuid.uuid4().hex) as (admin, public, pid):
        assert readback(public, reference)["backend"] == "initial"
        old = read_version(admin)
        command = {"etag": old["etag"], "deadline_ns": time.monotonic_ns() + 250_000_000,
                   "new_value": {"dial": f"127.0.0.1:{ports['A']}"}}
        with delivery_gate(admin, variant, command, trace) as port:
            assert time.monotonic_ns() < command["deadline_ns"]
            sent = call(port, "POST", "/controlled-delivery", command)
        assert sent["status"] == 200
        result = json.loads(sent["body"])
        cutoff = command["deadline_ns"]
        assert sent["sent_ns"] < cutoff and trace["gateway_received_ns"] < cutoff
        read = readback(public, reference)
        if variant == "sender_check_only":
            assert result["status"] == 200 and result["sent_ns"] > cutoff
            assert read["backend"] == "A"
        else:
            assert result["status"] is None and result["received_late_and_rejected"]
            assert read["backend"] == "initial"
        out = {
            "variant": variant, "scope": "controlled local request hold after sender deadline check",
            "caddy_pid": pid, "sender_before_cutoff_ms": (cutoff - sent["sent_ns"]) / 1e6,
            "gateway_before_cutoff_ms": (cutoff - trace["gateway_received_ns"]) / 1e6,
            "actuator_called": "sent_ns" in result, "actuator_http_status": result["status"],
            "final_readback": read, "final_readback_after_cutoff_ms": (read["observed_ns"] - cutoff) / 1e6,
            "deadline_ns": cutoff, "sender_request_ns": sent["sent_ns"], "delivery_trace": trace,
        }
    dump(case / "result.json", out)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caddy", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out == ROOT or not out.is_relative_to(ROOT):
        raise ValueError("output must be an unused directory within DEV04")
    out.mkdir(exist_ok=False)
    blobs = {"initial": compute_edge((args.assets / "camera.png").read_bytes()),
             "A": compute_edge((args.assets / "astronaut.png").read_bytes())}
    reference = {k: sha(raw) for k, raw in blobs.items()}
    with ExitStack() as stack:
        ports = {k: stack.enter_context(backend(k, raw)) for k, raw in blobs.items()}
        rows = [run_case(out / variant, args.caddy.resolve(strict=True), ports, reference, variant)
                for variant in ("sender_check_only", "actuator_gate")]
    dump(out / "summary.json", {
        "cases": rows, "reference": reference,
        "harness_sha256": sha(Path(__file__).read_bytes()),
        "caddy_sha256": sha(args.caddy.read_bytes()),
    })
    for row in rows:
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()


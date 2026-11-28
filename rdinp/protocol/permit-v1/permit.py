"""Loopback client and adoption guard for the reusable RDINP permit."""

from dataclasses import dataclass, field
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import time
from collections import Counter
from threading import Lock

from cryptography.exceptions import InvalidSignature
from jsonschema import ValidationError

from permit_wire import (
    AUTHORITY, HERE, MAX_FRAME, Codec, Identity, Trust, frame, jcs, key_pem,
    load_identity, parse, sha, unframe,
)

PATH = "/rdinp/permit-v1"
DEFAULT_SERVICE_NS = {"main": 18_000_000, "light": 12_000_000}
REQUESTS = frozenset(("ISSUE", "SNAPSHOT", "TASK", "SELECT", "AUDIT"))
RESPONSES = frozenset(("PERMIT", "SNAPSHOT_REPLY", "OFFER", "RESULT", "REJECT", "AUDIT_REPLY"))


def write_config(directory, principals, slots=1, service_estimate_ns=None):
    path = Path(directory).resolve()
    path.mkdir(parents=True, exist_ok=True)
    principals = tuple(principals)
    if not principals or len(set(principals)) != len(principals) or AUTHORITY in principals:
        raise ValueError("distinct client principals required")
    if type(slots) is not int or not 1 <= slots <= 64:
        raise ValueError("slots out of range")
    estimates = DEFAULT_SERVICE_NS if service_estimate_ns is None else service_estimate_ns
    if set(estimates) != {"main", "light"} or any(type(n) is not int or n <= 0 for n in estimates.values()):
        raise ValueError("positive tier service estimates required")
    edge = Identity(AUTHORITY, "responder")
    agents = [Identity(name, "initiator") for name in principals]
    server_path = path / "server-config.json"
    with server_path.open("x", encoding="utf-8") as stream:
        json.dump({"key": key_pem(edge), "edge_pin": edge.pin(),
                   "client_pins": {agent.principal: agent.pin() for agent in agents},
                   "slots": slots, "service_estimate_ns": estimates}, stream)
    for agent in agents:
        # Key file names are derived from the digest, never caller-controlled paths.
        client_path = path / ("client-" + sha(agent.principal.encode("utf-8")) + ".json")
        with client_path.open("x", encoding="utf-8") as stream:
            json.dump({"key": key_pem(agent), "pin": agent.pin(), "edge_pin": edge.pin()}, stream)
    return server_path


def start_server(config_path, port_path):
    config, port = Path(config_path).resolve(), Path(port_path).resolve()
    if port.exists():
        raise FileExistsError(port)
    logfile = port.with_suffix(".server.log")
    interpreter = [sys.executable]
    env = os.environ.copy()
    if os.name == "nt" and sys.prefix != sys.base_prefix:
        # Target the real process instead of the Windows venv redirector.
        # Use its interpreter but keep imports confined to the active venv.
        interpreter = [sys._base_executable, "-S"]
        libraries = dict.fromkeys(sysconfig.get_path(kind) for kind in ("purelib", "platlib"))
        env["PYTHONPATH"] = os.pathsep.join(libraries)
    with logfile.open("x", encoding="utf-8") as logs:
        return subprocess.Popen(
            [*interpreter, "-B", str(HERE / "permit_server.py"), str(config), str(port)],
            stdout=logs, stderr=subprocess.STDOUT, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


@dataclass
class Reply:
    body: dict = field(default_factory=dict)
    payload: bytes = b""
    verified: bool = False
    signature_ns: int = 0
    verify_ns: int = 0
    request_control_bytes: int = 0
    response_control_bytes: int = 0
    request_data_bytes: int = 0
    response_data_bytes: int = 0
    elapsed_ns: int = 0
    request_sent: bool = False

    @property
    def status(self):
        return self.body.get("status", "TRANSPORT_ERROR")


class TransportError(Exception):
    def __init__(self, reason, reply):
        super().__init__(reason)
        self.reply = reply


class Client:
    def __init__(self, config_path, port, principal, before_send=None, after_receive=None):
        directory = Path(config_path).resolve().parent
        client_path = directory / ("client-" + sha(principal.encode("utf-8")) + ".json")
        config = json.loads(client_path.read_text(encoding="utf-8"))
        self.principal = principal
        self.port = int(port)
        self.codec = Codec(load_identity(principal, config["key"]), Trust([config["pin"], config["edge_pin"]]))
        self.before_send = before_send
        self.after_receive = after_receive

    def call(self, kind, body, payload=b"", timeout_s=.6, *, before_send=None, after_receive=None):
        if kind not in REQUESTS:
            raise ValueError("wrong request kind")
        before_send = self.before_send if before_send is None else before_send
        after_receive = self.after_receive if after_receive is None else after_receive
        result = Reply()
        started = time.perf_counter_ns()
        connection = None
        try:
            sign_start = time.perf_counter_ns()
            signed = self.codec.sign(kind, body, AUTHORITY, payload=payload)
            result.signature_ns = time.perf_counter_ns() - sign_start
            wire = frame(signed, payload)
            result.request_control_bytes = len(signed) + 4
            result.request_data_bytes = len(payload)
            if before_send is not None and before_send(
                kind, result.request_control_bytes, result.request_data_bytes
            ) is False:
                raise TimeoutError("injected uplink drop")
            remaining_s = timeout_s - (time.perf_counter_ns() - started) / 1e9
            if remaining_s <= 0:
                raise TimeoutError("deadline elapsed before send")
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=remaining_s)
            connection.request("POST", PATH, wire, {"Content-Type": "application/octet-stream"})
            result.request_sent = True
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            header, data = unframe(response.read(MAX_FRAME + 1))
            result.response_control_bytes = len(header) + 4
            result.response_data_bytes = len(data)
            if after_receive is not None and after_receive(
                kind, result.response_control_bytes, result.response_data_bytes
            ) is False:
                raise TimeoutError("injected downlink drop")
            verify_start = time.perf_counter_ns()
            obj = self.codec.verify(header, AUTHORITY, self.principal, data)
            if obj["kind"] not in RESPONSES or obj["correlation"] != sha(signed):
                raise ValueError("uncorrelated response")
            if obj["kind"] == "PERMIT":
                token = self.codec.verify(jcs(obj["body"]["permit"]), AUTHORITY, self.principal)
                if token["kind"] != "PERMIT_TOKEN" or token["correlation"]:
                    raise ValueError("not a reusable permit")
            result.verify_ns = time.perf_counter_ns() - verify_start
            result.body = obj["body"]
            result.payload = data
            result.verified = True
            return result
        except (OSError, ValueError, KeyError, InvalidSignature, ValidationError, http.client.HTTPException) as exc:
            raise TransportError(str(exc), result) from exc
        finally:
            if connection is not None:
                connection.close()
            result.elapsed_ns = time.perf_counter_ns() - started


class AdoptionGuard:
    """The caller verifies the correlated signed reply before publishing locally."""

    def __init__(self):
        self.adopted = set()
        self.counts = Counter()
        self._lock = Lock()

    def adopt(self, reply, *, task_id, input_sha256, permit, cutoff_ns, allowed_tiers, now_ns=None):
        now = time.perf_counter_ns() if now_ns is None else now_ns
        claim = permit["body"]
        body = reply.body
        if not reply.verified or reply.status != "RESULT":
            self.counts["unverified"] += 1
        elif now >= cutoff_ns or now >= claim["expires_ns"]:
            self.counts["late"] += 1
        elif any(body.get(k) != claim.get(k) for k in ("session", "generation", "authority_epoch")):
            self.counts["old_generation"] += 1
        elif (
            body.get("task_id") != task_id or body.get("input_sha256") != input_sha256
            or body.get("tier") not in allowed_tiers or body.get("result_sha256") != sha(reply.payload)
            or body.get("edge_cutoff_ns") != cutoff_ns or body.get("complete_ns", cutoff_ns) >= cutoff_ns
        ):
            self.counts["binding"] += 1
        else:
            with self._lock:
                finish = time.perf_counter_ns() if now_ns is None else now_ns
                if finish >= min(cutoff_ns, claim["expires_ns"]):
                    self.counts["late"] += 1
                elif task_id in self.adopted:
                    self.counts["duplicate"] += 1
                else:
                    self.adopted.add(task_id)
                    self.counts["adopted"] += 1
                    return True
        return False

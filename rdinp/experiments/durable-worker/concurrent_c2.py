"""G1-A bridge from frozen bilateral C2 tickets to concurrent application grants."""

from __future__ import annotations

from collections import defaultdict
from contextlib import ExitStack, closing
from dataclasses import dataclass
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import sqlite3
import sys
import threading
import time
import uuid


C2_ROOT = Path(__file__).resolve().parent.parent.parent / "protocol" / "c2"
if str(C2_ROOT) not in sys.path:
    sys.path.insert(0, str(C2_ROOT))

from authority import Authority
from contracts import example_contract, jcs
from crypto import Identity, Trust, outcome_digest
from endpoint import Responder
from events import Clock, Trace
from initiator import Initiator


ROUTES = {"/rdinp/intent", "/rdinp/commit"}
BODY_LIMIT = 65_536
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z", re.ASCII)


@dataclass(frozen=True)
class Ticket:
    task_id: str
    terminal: int
    intent_id: str
    input_sha256: str


@dataclass(frozen=True)
class Lane:
    identity: Identity
    authority: Authority
    trace: Trace
    relay_port: int
    directory: Path


class RelayHandler(BaseHTTPRequestHandler):
    """Forward unchanged signed bodies over a second local TCP connection."""

    def log_message(self, *_):
        pass

    def _drop(self):
        self.close_connection = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_POST(self):
        lane = self.server
        self.connection.settimeout(2)
        try:
            lengths = self.headers.get_all("Content-Length") or []
            if (self.path not in ROUTES or len(lengths) != 1
                    or not lengths[0].isascii() or not lengths[0].isdigit()
                    or not 0 < int(lengths[0]) <= BODY_LIMIT
                    or self.headers.get("Transfer-Encoding")
                    or self.headers.get_content_type() != "application/json"):
                raise ValueError("invalid C2 relay framing")
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                raise ValueError("truncated C2 body")
            message = json.loads(raw)
            if not isinstance(message, dict) or not isinstance(message.get("negotiationId"), str):
                raise ValueError("invalid C2 relay identity")
        except (OSError, ValueError):
            self._drop()
            return

        placement = {
            "task_id": message["negotiationId"], "route": self.path,
            "terminal": lane.terminal, "phase": message.get("phase"), "attempt": message.get("attempt"),
            "request_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        lane.manager.log("C2_RELAY_RX", **placement, direction="uplink", body_bytes=len(raw))
        gate_ns = time.monotonic_ns()
        if lane.manager.suppresses("uplink", self.path, gate_ns):
            lane.manager.log("C2_RELAY_DROP", **placement, direction="uplink",
                             body_bytes=len(raw), fault_gate_ns=gate_ns)
            self._drop()
            return

        connection = http.client.HTTPConnection("127.0.0.1", lane.authority_port, timeout=2)
        try:
            connection.request("POST", self.path, body=raw, headers={
                "Content-Type": "application/json", "Connection": "close",
            })
            reply = connection.getresponse()
            status, answer = reply.status, reply.read(BODY_LIMIT + 1)
            if len(answer) > BODY_LIMIT:
                raise ValueError("C2 reply exceeded cap")
        except (OSError, http.client.HTTPException, ValueError) as error:
            lane.manager.log("C2_RELAY_FAILURE", **placement, detail=type(error).__name__)
            self._drop()
            return
        finally:
            connection.close()

        received = {
            **placement, "direction": "downlink", "body_bytes": len(answer), "http_status": status,
            "response_raw_sha256": hashlib.sha256(answer).hexdigest(),
        }
        lane.manager.log("C2_RELAY_RX", **received)
        gate_ns = time.monotonic_ns()
        if lane.manager.suppresses("downlink", self.path, gate_ns):
            lane.manager.log("C2_RELAY_DROP", **received, fault_gate_ns=gate_ns)
            self._drop()
            return
        try:
            self._send(status, answer)
        except OSError as error:
            lane.manager.log("C2_RELAY_FAILURE", **received, detail=type(error).__name__)
            self._drop()
            return
        lane.manager.log("C2_RELAY_TX", **received)


class Relay(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, manager, terminal, authority_port):
        super().__init__(("127.0.0.1", 0), RelayHandler)
        self.manager = manager
        self.terminal = terminal
        self.authority_port = authority_port
        self.listener = threading.Thread(
            target=lambda: self.serve_forever(poll_interval=0.02), daemon=True,
        )

    def __enter__(self):
        self.listener.start()
        return self

    def __exit__(self, *_):
        self.shutdown()
        self.server_close()
        self.listener.join()


class C2Authorization:
    """One bilateral frozen C2 authority lane per participating terminal.

    The shared concurrent store remains the sole owner of physical capacity.
    These durable C2 commitments authorize logical tasks without reserving a
    CPU slot. Committed tickets retain their original C2 history on application
    lease expiry or release.
    """

    def __init__(self, path: Path, pair: dict, fault, log):
        self.path = path
        self.pair_id = pair["pair_id"]
        self.terminals = pair["terminals"]
        self.fault = fault
        self.log = log
        self.contract = example_contract()
        self.epoch_origin_ns = time.monotonic_ns()
        boot_file = Path("/proc/sys/kernel/random/boot_id")
        self.boot = boot_file.read_text(encoding="ascii").strip() if boot_file.is_file() else uuid.uuid4().hex
        self.auth_identity = Identity("authority", "responder")
        self.bindings = {}
        self.by_terminal = defaultdict(list)
        self.tickets = {}
        self.lanes = {}
        self._stack = None
        self._proofs = {}
        self._proof_lock = threading.Lock()
        for task in pair["tasks"]:
            task_id = task["task_id"]
            terminal = task["terminal"]
            if (not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id)
                    or task_id in self.tickets or type(terminal) is not int
                    or not 0 <= terminal < self.terminals):
                raise ValueError("invalid C2 task or terminal identity")
            binding = self._binding(task)
            if re.fullmatch(r"[0-9a-f]{64}", binding["input_sha256"]) is None:
                raise ValueError("invalid C2 input binding")
            intent = hashlib.sha256(b"GENSPACE-RDINP-G1A-INTENT-1\0" + jcs(binding)).hexdigest()
            ticket = Ticket(task_id, terminal, intent, task["input_sha256"])
            self.tickets[task_id] = ticket
            self.bindings[task_id] = binding
            self.by_terminal[terminal].append(ticket)

    def _binding(self, task):
        context = {key: task[key] for key in (
            "task_id", "terminal", "input_sha256", "release_offset_ns", "fallback_ns", "deadline_ns",
        )}
        if "expected_output_sha256" in task:
            context["expected_output_sha256"] = task["expected_output_sha256"]
        return {
            **context, "pair_id": self.pair_id, "timing_contract_digest": self.contract.digest,
            "authority": self.auth_identity.principal, "initiator": f"terminal-{task['terminal']}",
        }

    def _clock(self, name):
        return Clock(self.boot, name, lambda: time.monotonic_ns() - self.epoch_origin_ns)

    def set_fault(self, fault):
        self.fault = fault

    def suppresses(self, direction, route, gate_ns):
        fault = self.fault
        return fault is not None and fault.suppresses(direction, route, gate_ns)

    def __enter__(self):
        self.path.mkdir(parents=True, exist_ok=False)
        self.log("C2_CLOCK_BIND", origin_ns=self.epoch_origin_ns, c2_boot=self.boot,
                 c2_contract_digest=self.contract.digest)
        with ExitStack() as stack:
            for terminal, tickets in sorted(self.by_terminal.items()):
                directory = self.path / f"terminal-{terminal}"
                directory.mkdir()
                identity = Identity(f"terminal-{terminal}", "initiator")
                trust = Trust([identity.pin(), self.auth_identity.pin()])
                clock = self._clock(f"c2-authority-{terminal}")
                trace = Trace("responder", clock, directory / "authority_events.jsonl")
                authority = Authority(
                    directory / "authority.sqlite", self.contract, clock, trace,
                    capacity=len(tickets), initiator_id=identity.principal,
                )
                responder = stack.enter_context(Responder(authority, self.auth_identity, trust, trace))
                # Drain in-flight authorities and relays before the final
                # authoritative snapshot, including after lost replies.
                responder.http.daemon_threads = False
                relay = stack.enter_context(Relay(self, terminal, responder.port))
                self.lanes[terminal] = Lane(identity, authority, trace, relay.server_port, directory)
                self.log("C2_LANE_READY", terminal=terminal, initiator=identity.principal,
                         authority=self.auth_identity.principal, trust_digest=trust.digest,
                         logical_ticket_count=len(tickets), physical_slots_reserved=0)
                for ticket in tickets:
                    self.log("C2_TASK_BIND", task_id=ticket.task_id, terminal=terminal,
                             negotiationId=ticket.task_id, intentId=ticket.intent_id,
                             input_sha256=ticket.input_sha256, binding=self.bindings[ticket.task_id])
            self._stack = stack.pop_all()
        return self

    def __exit__(self, *_):
        if self._stack is not None:
            self._stack.close()
            self._stack = None

    def finish(self):
        self.__exit__(None, None, None)
        for task_id in self.tickets:
            self.log("C2_FINAL_AUTHORIZATION", task_id=task_id, approval=self.committed(task_id))

    def negotiate(self, task):
        task_id = task["task_id"]
        ticket = self.tickets[task_id]
        if task.get("pair_id", self.pair_id) != self.pair_id or self._binding(task) != self.bindings[task_id]:
            raise ValueError("immutable C2 task binding changed")
        lane = self.lanes[ticket.terminal]
        trust = Trust([lane.identity.pin(), self.auth_identity.pin()])
        index = self.by_terminal[ticket.terminal].index(ticket)
        trace = Trace(
            "initiator", self._clock(f"c2-client-{ticket.terminal}-{index}"),
            lane.directory / f"task-{index}-events.jsonl",
        )
        client = Initiator(lane.directory / f"task-{index}.sqlite", self.contract, lane.identity, trust,
                           trace.clock, trace, authority=self.auth_identity.principal)
        try:
            terminal = client.run("127.0.0.1", lane.relay_port, ticket.task_id, ticket.intent_id, 1)
        finally:
            client.close()
        self.log("C2_CLIENT_TERMINAL", task_id=task_id, negotiationId=task_id, intentId=ticket.intent_id,
                 terminal=ticket.terminal, c2_result=terminal,
                 c2_clock_id=trace.clock.clock_id)
        return terminal

    @staticmethod
    def _read_commit(lane, task_id):
        with closing(sqlite3.connect(Path(lane.authority.path).resolve().as_uri() + "?mode=ro",
                                     uri=True, timeout=1.0)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT n.intent, n.principal, n.units, n.epoch, n.state, n.receipt, n.decision,
                       e.tx AS effect_tx, e.transaction_id AS auth_tx, e.boot AS effect_boot,
                       t.phase, t.reply_kind, t.body_jcs, t.request_raw, m.config
                FROM negotiations AS n
                JOIN effects AS e ON e.neg=n.neg AND e.event='COMMIT'
                JOIN transactions AS t ON t.id=e.transaction_id AND t.neg=n.neg
                CROSS JOIN metadata AS m
                WHERE n.neg=?
            """, (task_id,)).fetchall()
        if len(rows) > 1:
            raise RuntimeError("more than one durable C2 commit for one task")
        return rows[0] if rows else None

    def committed(self, task_id):
        """Read the authority, independent of whether the terminal received a reply."""

        ticket = self.tickets.get(task_id)
        if ticket is None:
            return None
        with self._proof_lock:
            known = self._proofs.get(task_id)
            if known is not None:
                return dict(known)
            lane = self.lanes[ticket.terminal]
            row = self._read_commit(lane, task_id)
            if row is None:
                return None

            receipt = json.loads(row["receipt"])
            decision = json.loads(row["decision"])
            principal = lane.identity.principal
            context = {
                "negotiationId": task_id, "intentId": ticket.intent_id, "sender": principal,
                "recipient": self.auth_identity.principal, "timingContractDigest": self.contract.digest,
            }
            if (
                (row["state"], row["intent"], row["principal"], row["units"], row["config"])
                != ("CONFIRMED", ticket.intent_id, principal, 1, self.contract.digest)
                or row["phase"] != "COMMIT_INITIAL" or row["reply_kind"] != "RECEIPT"
                or row["receipt"] != row["body_jcs"] or receipt["status"] != "COMMITTED"
                or any(receipt[key] != decision[key] for key in (
                    "decisionDigest", "decisionId", "epoch", "token", "units", "leaseUntilNs"
                ))
                or receipt["epoch"] != row["epoch"]
                or outcome_digest("DECISION", context, decision) != receipt["decisionDigest"]
                or outcome_digest("RECEIPT", context, receipt) != receipt["receiptDigest"]
            ):
                raise RuntimeError("durable C2 ticket binding mismatch")

            with lane.trace.lock:
                seen = next((
                    item for item in reversed(lane.trace.events)
                    if item["event"] == "DURABLE_COMMIT_RETURN" and item.get("effectTx") == row["effect_tx"]
                ), None)
                if seen is None:
                    # SQLite may be readable before the authority clock sample is recorded.
                    return None
            if ((seen["transactionId"], seen["boot"], seen["negotiationId"], seen["rawSha256"])
                    != (row["auth_tx"], row["effect_boot"], task_id, row["request_raw"])):
                raise RuntimeError("C2 receipt and commit-return observation disagree")
            measured = seen["observedNs"]
            if measured is None:
                raise RuntimeError("C2 commit-return sample unavailable")
            proof = {
                "c2_intent_id": ticket.intent_id,
                "c2_receipt_digest": receipt["receiptDigest"],
                "c2_decision_digest": receipt["decisionDigest"],
                "c2_commit_effect_tx": row["effect_tx"],
                "c2_commit_transaction_id": row["auth_tx"],
                "c2_commit_return_ns": self.epoch_origin_ns + measured,
                "c2_request_raw_sha256": row["request_raw"],
                "c2_epoch": row["epoch"],
                "c2_commit_before_lease": measured < receipt["leaseUntilNs"],
                "c2_terminal": ticket.terminal, "c2_authority_state": row["state"],
            }
            self._proofs[task_id] = proof
            self.log("C2_DURABLE_AUTHORIZED", task_id=task_id, negotiationId=task_id, **proof)
            return dict(proof)

"""Reusable permit authority and real concurrent loopback worker."""

from collections import Counter
import heapq
from io import BytesIO
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import sys
from threading import Condition
import time
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from jsonschema import ValidationError
from PIL import Image

from permit import PATH, REQUESTS
from permit_wire import AUTHORITY, HERE, MAX_FRAME, Codec, Trust, frame, jcs, load_identity, parse, sha, unframe

sys.path.insert(0, str(HERE.parents[1] / "experiments" / "service-worker"))
from image_workload import detect_edges
sys.path.pop(0)

SIDE = {"main": 512, "light": 384}


class Rejection(Exception):
    pass


def reject(reason):
    raise Rejection(reason)


class Authority:
    def __init__(self, config, ledger_path):
        self.slots = config["slots"]
        self.service_estimate = config["service_estimate_ns"]
        self.epoch = uuid4().hex
        self.condition = Condition()
        self.active = {}
        self.waiting = []
        self.tickets = {}
        self.generations = {}
        self.issued = {}
        self.uses = Counter()
        identity = load_identity(AUTHORITY, config["key"])
        self.codecs = {
            principal: Codec(identity, Trust([config["edge_pin"], client_pin]))
            for principal, client_pin in config["client_pins"].items()
        }
        # A short transaction records one execution claim and at most one output
        # per logical task, including across permit renewal and local restart.
        self.db = sqlite3.connect(ledger_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            principal TEXT NOT NULL, task_id TEXT NOT NULL,
            input_sha256 TEXT NOT NULL, session TEXT NOT NULL, generation INTEGER NOT NULL,
            state TEXT NOT NULL, starts INTEGER NOT NULL DEFAULT 0 CHECK(starts BETWEEN 0 AND 1),
            effects INTEGER NOT NULL DEFAULT 0 CHECK(effects BETWEEN 0 AND starts),
            result_sha256 TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(principal, task_id)
        )""")
        self.db.commit()

    def _row(self, key):
        return self.db.execute("SELECT * FROM tasks WHERE principal=? AND task_id=?", key).fetchone()

    def _state(self, key, state, *, start=False, result=None):
        with self.db:
            if start:
                cursor = self.db.execute(
                    """UPDATE tasks SET state = ?, starts = 1
                       WHERE principal = ? AND task_id = ? AND starts = 0""",
                    (state, *key),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("second worker claim")
            elif result is not None:
                cursor = self.db.execute(
                    """UPDATE tasks SET state = ?, effects = 1, result_sha256 = ?
                       WHERE principal = ? AND task_id = ? AND starts = 1 AND effects = 0""",
                    (state, result, *key),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("second result commit")
            else:
                self.db.execute(
                    "UPDATE tasks SET state = ? WHERE principal = ? AND task_id = ?",
                    (state, *key),
                )

    def _wait_ns(self, now):
        ready = [max(now, until) for _, until in self.active.values()]
        ready += [now] * (self.slots - len(ready))
        heapq.heapify(ready)
        for ticket in self.waiting:
            when = heapq.heappop(ready)
            heapq.heappush(ready, when + self.service_estimate[ticket["tier"]])
        return ready[0] - now

    def _sweep_cache(self, now):
        expired = [
            key for key, ticket in self.tickets.items()
            if ticket["status"] == "offered" and self._ineligible(ticket, now)
        ]
        for key in expired:
            self.tickets.pop(key)
            self._state(key, "failed")

    def _issue(self, principal, codec, message, req_hash, now):
        body = message["body"]
        previous = self.issued.get((principal, message["nonce"]))
        if previous is not None:
            previous_hash, token = previous
            if previous_hash != req_hash:
                reject("NONCE_CONFLICT")
            return "PERMIT", {"permit": token}, b""
        if body["max_slots"] > self.slots:
            reject("SLOTS")
        scope = (principal, body["session"])
        generation = self.generations.get(scope, 0) + 1
        self.generations[scope] = generation
        claim = {k: v for k, v in body.items() if k != "ttl_ms"}
        claim.update({
            "generation": generation, "authority_epoch": self.epoch,
            "issued_ns": now, "expires_ns": now + body["ttl_ms"] * 1_000_000,
            "tiers": ["main", "light", "local"],
        })
        token = parse(codec.sign("PERMIT_TOKEN", claim, principal))
        self.issued[principal, message["nonce"]] = req_hash, token
        self.condition.notify_all()
        return "PERMIT", {"permit": token}, b""

    def _permit(self, codec, principal, body):
        token = codec.verify(jcs(body["permit"]), AUTHORITY, principal)
        if token["kind"] != "PERMIT_TOKEN" or token["correlation"]:
            reject("PERMIT_TYPE")
        return token["body"]

    def _ineligible(self, ticket, now):
        claim = ticket["claim"]
        if claim["authority_epoch"] != self.epoch or self.generations.get(ticket["scope"]) != claim["generation"]:
            return "STALE_PERMIT"
        if now >= claim["expires_ns"]:
            return "EXPIRED_PERMIT"
        if now >= ticket["edge_cutoff_ns"]:
            return "EDGE_DEADLINE"
        return None

    def _register(self, principal, body, claim, payload):
        now = time.perf_counter_ns()
        key = (principal, body["task_id"])
        scope = (principal, claim["session"])
        ticket = {k: v for k, v in body.items() if k != "permit"}
        ticket.update({
            "key": key, "scope": scope, "claim": claim, "ready_ns": now,
            "payload": payload, "tier": body["accepted_tier"],
        })
        denied = self._ineligible(ticket, now)
        if denied:
            reject(denied)
        previous = self._row(key)
        if previous is not None:
            reason = "DUPLICATE_TASK" if previous["input_sha256"] == body["input_sha256"] else "TASK_CONFLICT"
            reject(reason)
        if not 0 < len(payload) <= claim["max_input_bytes"] or sha(payload) != body["input_sha256"]:
            reject("BAD_INPUT")
        if body["input_tier"] == "light" and ticket["tier"] == "main":
            reject("INVALID_TIER_SWITCH")
        release, cutoff, deadline = (body[name] for name in ("release_ns", "edge_cutoff_ns", "deadline_ns"))
        if (
            not release <= now < cutoff <= deadline
            or deadline - release > claim["max_budget_ms"] * 1_000_000
            or any(value > deadline - release for value in ticket["tail_budget_ns"].values())
        ):
            reject("TASK_BUDGET")
        quota_key = (*scope, claim["generation"])
        if self.uses[quota_key] >= claim["max_tasks"]:
            reject("TASK_QUOTA")

        def fits(tier):
            elapsed = self._wait_ns(now) + self.service_estimate[tier] + ticket["tail_budget_ns"][tier]
            return now + elapsed < min(cutoff, claim["expires_ns"])

        offer = (
            ticket["tier"] == "main" and body["post_upload"] in ("auto", "offer")
            and not fits("main") and fits("light")
        )
        if offer:
            ticket["tier"] = "light"
        if not fits(ticket["tier"]):
            reject("PREDICTED_DEADLINE")
        status = "offered" if offer and body["post_upload"] == "offer" else "queued"
        ticket["status"] = status
        with self.db:
            self.db.execute(
                """INSERT INTO tasks(principal,task_id,input_sha256,session,generation,state)
                   VALUES(?,?,?,?,?,?)""",
                (*key, body["input_sha256"], claim["session"], claim["generation"], status),
            )
        self.uses[quota_key] += 1
        self.tickets[key] = ticket
        return ticket

    def _select(self, principal, body, claim):
        key = (principal, body["task_id"])
        ticket = self.tickets.get(key)
        if ticket is None or ticket["status"] != "offered":
            reject("NO_ACTIVE_OFFER")
        if (
            ticket["claim"] != claim or ticket["input_sha256"] != body["input_sha256"]
            or ticket["tier"] != body["tier"]
        ):
            reject("OFFER_BINDING")
        denied = self._ineligible(ticket, time.perf_counter_ns())
        if denied:
            reject(denied)
        ticket["status"] = "queued"
        self._state(key, "queued")
        return ticket

    def _binding(self, ticket):
        return {
            "task_id": ticket["task_id"], "input_sha256": ticket["input_sha256"],
            "session": ticket["claim"]["session"], "generation": ticket["claim"]["generation"],
            "authority_epoch": self.epoch, "tier": ticket["tier"],
            "ready_ns": ticket["ready_ns"], "edge_cutoff_ns": ticket["edge_cutoff_ns"],
        }

    def _work(self, ticket):
        key = ticket["key"]
        tier = ticket["tier"]
        limit = min(ticket["edge_cutoff_ns"], ticket["claim"]["expires_ns"])
        with self.condition:
            while True:
                now = time.perf_counter_ns()
                denied = self._ineligible(ticket, now)
                per_session = sum(scope == ticket["scope"] for scope, _ in self.active.values())
                at_head = self.waiting[0] is ticket
                if denied:
                    self.waiting.remove(ticket)
                    self.tickets.pop(key)
                    self._state(key, "failed")
                    self.condition.notify_all()
                    reject(denied)
                if at_head and len(self.active) < self.slots and per_session < ticket["claim"]["max_slots"]:
                    self.waiting.pop(0)
                    expect = self.service_estimate[tier]
                    if now + expect + ticket["tail_budget_ns"][tier] >= limit:
                        self.tickets.pop(key)
                        self._state(key, "failed")
                        self.condition.notify_all()
                        reject("START_BUDGET")
                    self._state(key, "running", start=True)
                    start_ns = time.perf_counter_ns()
                    reason = self._ineligible(ticket, start_ns)
                    if reason:
                        self.tickets.pop(key)
                        self._state(key, "failed")
                        self.condition.notify_all()
                        reject(reason)
                    self.active[key] = ticket["scope"], start_ns + expect
                    break
                self.condition.wait(timeout=max(0, (limit - now) / 1e9))
        try:
            data = detect_edges(ticket["payload"], SIDE[tier])
            result_hash = sha(data)
            service_done = time.perf_counter_ns()
            with self.condition:
                denied = self._ineligible(ticket, time.perf_counter_ns())
                if denied:
                    reject(denied)
                self._state(key, "complete", result=result_hash)
                complete_ns = time.perf_counter_ns()
                if complete_ns >= limit:
                    reject("LATE_RESULT")
                return "RESULT", {
                    **self._binding(ticket), "result_sha256": result_hash,
                    "queue_ns": start_ns - ticket["ready_ns"], "service_ns": service_done - start_ns,
                    "complete_ns": complete_ns,
                }, data
        except (OSError, ValueError):
            reject("WORKLOAD_ERROR")
        finally:
            with self.condition:
                if not self._row(key)["effects"]:
                    self._state(key, "failed")
                self.active.pop(key)
                self.tickets.pop(key)
                self.condition.notify_all()

    def _audit(self, body):
        offset, limit = body.get("offset", 0), body.get("limit", 30)
        n, starts, effects = self.db.execute(
            "SELECT count(*), coalesce(sum(starts),0), coalesce(sum(effects),0) FROM tasks"
        ).fetchone()
        rows = self.db.execute(
            """SELECT principal,task_id,input_sha256,session,generation,state,starts,effects,result_sha256
               FROM tasks ORDER BY principal,task_id LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        return "AUDIT_REPLY", {"task_count": n, "starts": starts, "effects": effects,
                               "tasks": [dict(row) for row in rows],
                               "next_offset": offset + limit if offset + limit < n else None}, b""

    def handle(self, principal, codec, message, req_hash, payload):
        body, kind = message["body"], message["kind"]
        if kind != "TASK" and payload:
            reject("UNEXPECTED_PAYLOAD")
        claim = self._permit(codec, principal, body) if kind in ("TASK", "SELECT") else None
        with self.condition:
            now = time.perf_counter_ns()
            self._sweep_cache(now)
            if kind == "ISSUE":
                return self._issue(principal, codec, message, req_hash, now)
            if kind == "AUDIT":
                return self._audit(body)
            if kind == "SNAPSHOT":
                return "SNAPSHOT_REPLY", {
                    "observed_ns": now, "busy_slots": len(self.active),
                    "queued_tasks": len(self.waiting), "slots": self.slots,
                    "wait_ns": self._wait_ns(now), "authority_epoch": self.epoch,
                    "service_estimate_ns": self.service_estimate,
                }, b""
            if kind == "TASK":
                ticket = self._register(principal, body, claim, payload)
                if ticket["status"] == "offered":
                    return "OFFER", self._binding(ticket), b""
            else:
                ticket = self._select(principal, body, claim)
            self.waiting.append(ticket)
        return self._work(ticket)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        authority = self.server.authority
        try:
            if self.path != PATH:
                raise ValueError("route")
            length = int(self.headers["Content-Length"])
            if not 4 < length <= MAX_FRAME or self.headers.get("Transfer-Encoding"):
                raise ValueError("HTTP length")
            self.connection.settimeout(2)
            contents = self.rfile.read(length)
            if len(contents) != length:
                raise ValueError("short input")
            header, payload = unframe(contents)
            principal = parse(header)["sender"]
            codec = authority.codecs[principal]
            message = codec.verify(header, principal, AUTHORITY, payload)
            if message["kind"] not in REQUESTS or message["correlation"]:
                raise ValueError("request scope")
        except (TypeError, OSError, KeyError, ValueError, InvalidSignature, ValidationError):
            self.send_error(400, "invalid signed request")
            return
        req_hash = sha(header)
        try:
            response, body, data = authority.handle(principal, codec, message, req_hash, payload)
        except Rejection as exc:
            response, body, data = "REJECT", {"reason": str(exc)}, b""
        except (TypeError, KeyError, ValueError, InvalidSignature, ValidationError):
            response, body, data = "REJECT", {"reason": "INVALID_PERMIT"}, b""
        body["status"] = {"SNAPSHOT_REPLY": "SNAPSHOT", "AUDIT_REPLY": "AUDIT"}.get(response, response)
        content = frame(codec.sign(response, body, principal, req_hash, data), data)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            # The signed result can become unusable due to a dropped or late
            # transport. The ledger retains its single-effect fencing.
            return


def serve(config_path, port_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    authority = Authority(config, config_path.parent / "guard.sqlite3")
    # Start each measured session with the same resident image service.
    # Cold permit issuance and renewal are still real timed operations.
    bootstrap = BytesIO()
    Image.linear_gradient("L").save(bootstrap, format="PNG")
    for side in SIDE.values():
        detect_edges(bootstrap.getvalue(), side)
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.daemon_threads = True
        server.authority = authority
        staging = port_path.with_suffix(".starting")
        with staging.open("x", encoding="ascii") as stream:
            stream.write(str(server.server_port))
        staging.replace(port_path)
        server.serve_forever()


if __name__ == "__main__":
    serve(Path(sys.argv[1]), Path(sys.argv[2]))

"""Discrete-event comparison of four RDINP policies on immutable paired inputs."""
from __future__ import annotations

import csv
import hashlib
import heapq
import itertools
import json
import math
import random
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

METHODS = ("Fixed-Intent", "Reactive-ReNeg", "Static-Fallback", "Structured-RDINP")
MAIN, LIGHT, LOCAL, MISSED = "high", "light", "local", "missed"
AIR_RATES = {"up": 24.0, "down": 36.0}
BIN_MS = 4.0
TRACE_PERIOD_MS = 5000.0
FRAME_BYTES = 8192
FRAME_HEADER_BYTES = 32
RTT_RETRY_MS = 24.0
FRAME_ATTEMPTS = 3
BASE_TRANSIT_MS = 4.0
CONTROL_SERVICE_MS = 1.0
NOMINAL_EDGE_MS = 145.0
LOCAL_RESERVE_MS = 55.0


@dataclass(frozen=True)
class Scenario:
    load: float
    loss: float
    dip: float
    deadline_ms: float

    @property
    def name(self) -> str:
        return f"L{self.load:g}-P{self.loss:g}-A{self.dip:g}-D{self.deadline_ms:g}"


@dataclass(frozen=True)
class Release:
    task_id: int
    terminal: int
    at: float
    image: str


@dataclass(frozen=True)
class Tier:
    upload: int
    download: int
    service: float
    prepare: float
    utility: float


def identity(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_capacity(path: Path) -> tuple[tuple[float, float], ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = tuple(
            (int(row["application_relative_time_ns"]) / 1e6, float(row["new_capacity_mbps"]))
            for row in csv.DictReader(handle)
        )
    if (
        not rows
        or rows[0][0] != 0
        or any(not math.isfinite(rate) or rate <= 0 for _, rate in rows)
        or any(not a[0] < b[0] for a, b in zip(rows, rows[1:]))
        or rows[-1][0] >= TRACE_PERIOD_MS
    ):
        raise ValueError("invalid 5G-LENA capacity trace")
    return rows


@dataclass(frozen=True)
class Inputs:
    scenario: Scenario
    releases: tuple[Release, ...]
    capacity: tuple[tuple[float, float], ...]
    channel: dict[str, tuple[tuple[bool, float], ...]]
    slots: int
    input_hash: str


def paired_inputs(scenario, seed, capacity, names, duration_ms, terminals, slots):
    arrival_rng = random.Random(f"rdinp-step1-arrivals:{seed}")
    releases = []
    at = 0.0
    arrival_rate = scenario.load * slots / NOMINAL_EDGE_MS
    while True:
        at += arrival_rng.expovariate(arrival_rate)
        if at >= duration_ms:
            break
        releases.append(Release(len(releases), arrival_rng.randrange(terminals), at, arrival_rng.choice(names)))

    channel = {}
    leave_bad = BIN_MS / 36.0
    enter_bad = scenario.loss * leave_bad / (1 - scenario.loss)
    for direction in AIR_RATES:
        rng = random.Random(f"rdinp-step1-channel:{seed}:{direction}")
        bad = rng.random() < scenario.loss
        states = []
        for _ in range(math.ceil((duration_ms + scenario.deadline_ms + 500) / BIN_MS)):
            draw = rng.random()
            states.append((bad, rng.uniform(0, 3)))
            bad = draw >= leave_bad if bad else draw < enter_bad
        channel[direction] = tuple(states)

    fingerprint = identity({
        "scenario": asdict(scenario), "releases": [asdict(row) for row in releases],
        "capacity": capacity, "channel": channel, "slots": slots, "seed": seed,
    })
    return Inputs(scenario, tuple(releases), capacity, channel, slots, fingerprint)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.events = []
        self.serial = itertools.count()

    def schedule(self, at, callback, *args):
        if at < self.now:
            raise AssertionError("event scheduled in the past")
        heapq.heappush(self.events, (at, next(self.serial), callback, args))

    def run(self):
        while self.events:
            self.now, _, callback, args = heapq.heappop(self.events)
            callback(*args)


@dataclass
class Task:
    release: Release
    deadline: float
    fallback: float
    tiers: dict[str, Tier]
    grade: str = MISSED
    adopted: float | None = None
    edge_epoch: int = 0
    edge_started_epoch: int = 0
    client_epoch: int = 0
    local_started: bool = False
    rounds: int = 0
    negotiation_ms: float = 0
    negotiation_open: float | None = None
    control_bytes: int = 0
    data_bytes: int = 0
    air_attempts: int = 0
    lost_frames: int = 0
    busy: int = 0
    grant_light: int = 0
    switch_upload: int = 0
    switch_edge: int = 0
    stale_results: int = 0
    grants: int = 0
    requests: int = 0
    reason: str = "deadline"
    local_finished: bool = False


@dataclass
class Tx:
    task: Task
    direction: str
    control: bool
    cutoff: float
    remaining: int
    callback: object
    done: bool = False

    def finish_frame(self, ok):
        if self.done:
            return
        self.remaining -= 1
        if not ok or not self.remaining:
            self.done = True
            self.callback(ok)


class Network:
    """Shared FIFO uplink/downlink air, with an additional native downlink FH server."""
    def __init__(self, clock, inputs):
        self.clock = clock
        self.inputs = inputs
        self.waiting = {key: deque() for key in ("up", "down", "fh")}
        self.active_until = dict.fromkeys(self.waiting, 0.0)
        self.queued_bytes = dict.fromkeys(self.waiting, 0)
        self.fh_bytes = 0
        self.fh_max_wait_ms = 0.0
        self.fh_busy_ms = 0.0

    def observed(self, direction):
        # Both methods see the same public rate sampler, with ten ms of lag.
        t = max(0.0, math.floor(self.clock.now / 10) * 10 - 10)
        return self.rate(direction, t)[0]

    def rate(self, stage, now):
        trace = self.inputs.capacity
        offset = now % TRACE_PERIOD_MS
        i = next((i for i in range(len(trace) - 1, -1, -1) if trace[i][0] <= offset), 0)
        boundary = now - offset + (trace[i + 1][0] if i + 1 < len(trace) else TRACE_PERIOD_MS)
        if boundary <= now:
            boundary = now + TRACE_PERIOD_MS
        if stage == "fh":
            return trace[i][1], boundary
        lowest = min(x[1] for x in trace)
        scale = 1 - self.inputs.scenario.dip if trace[i][1] == lowest and len(trace) > 1 else 1
        return AIR_RATES[stage] * scale, boundary

    def end_of_frame(self, stage, now, size):
        bits_ms = size * 0.008
        while bits_ms > 0:
            rate, boundary = self.rate(stage, now)
            available = (boundary - now) * rate
            if bits_ms <= available:
                return now + bits_ms / rate
            bits_ms -= available
            now = boundary
        return now

    def air_state(self, direction, t):
        timeline = self.inputs.channel[direction]
        return timeline[min(len(timeline) - 1, int(t / BIN_MS))]

    def send(self, task, direction, nbytes, control, cutoff, callback):
        if self.clock.now >= cutoff:
            callback(False)
            return
        tx = Tx(task, direction, control, cutoff, math.ceil(nbytes / FRAME_BYTES), callback)
        while nbytes:
            payload = min(nbytes, FRAME_BYTES)
            stage = "fh" if direction == "down" else direction
            self.enqueue(stage, tx, payload + FRAME_HEADER_BYTES, 1)
            nbytes -= payload

    def enqueue(self, stage, tx, size, attempt):
        if tx.done or self.clock.now >= tx.cutoff:
            tx.finish_frame(False)
            return
        self.waiting[stage].append((tx, size, attempt, self.clock.now))
        self.queued_bytes[stage] += size
        self.kick(stage)

    def kick(self, stage):
        now = self.clock.now
        if self.active_until[stage] > now:
            return
        queue = self.waiting[stage]
        while queue:
            tx, size, attempt, enqueued = queue.popleft()
            self.queued_bytes[stage] -= size
            if tx.done:
                continue
            if now >= tx.cutoff:
                tx.finish_frame(False)
                # Expiry can invoke a client callback that re-enters the link.
                if self.active_until[stage] > now:
                    return
                continue
            end = self.end_of_frame(stage, now, size)
            self.active_until[stage] = end
            if stage == "fh":
                self.fh_bytes += size
                self.fh_max_wait_ms = max(self.fh_max_wait_ms, now - enqueued)
                self.fh_busy_ms += end - now
                self.clock.schedule(end, self.enqueue, "down", tx, size, attempt)
            else:
                if tx.control:
                    tx.task.control_bytes += size
                else:
                    tx.task.data_bytes += size
                tx.task.air_attempts += 1
                # A block crossing a bad bin is corrupted. Jitter is time-indexed.
                first_bin = int(now / BIN_MS)
                last_bin = int(math.nextafter(end, -math.inf) / BIN_MS)
                bad = any(
                    self.air_state(stage, bin_index * BIN_MS)[0]
                    for bin_index in range(first_bin, last_bin + 1)
                )
                jitter = self.air_state(stage, end)[1]
                if bad:
                    tx.task.lost_frames += 1
                    retry_at = end + RTT_RETRY_MS
                    if attempt < FRAME_ATTEMPTS and retry_at < tx.cutoff:
                        retry_stage = "fh" if stage == "down" else stage
                        self.clock.schedule(retry_at, self.enqueue, retry_stage, tx, size, attempt + 1)
                    else:
                        self.clock.schedule(min(retry_at, tx.cutoff), tx.finish_frame, False)
                else:
                    self.clock.schedule(end + BASE_TRANSIT_MS + jitter, self.arrive, tx)
            self.clock.schedule(end, self.kick, stage)
            return

    def arrive(self, tx):
        tx.finish_frame(self.clock.now < tx.cutoff)


class Simulation:
    def __init__(self, inputs, method, profiles):
        if method not in METHODS:
            raise ValueError(method)
        self.clock = Clock()
        self.network = Network(self.clock, inputs)
        self.inputs = inputs
        self.method = method
        self.menu = method == "Structured-RDINP"
        self.reactive = method == "Reactive-ReNeg"
        self.allow_local = method != "Fixed-Intent"
        self.free_at = [0.0] * inputs.slots
        self.pending = deque()
        self.local_free_at = {}
        self.tasks = [
            Task(release, release.at + inputs.scenario.deadline_ms,
                 release.at + max(0, inputs.scenario.deadline_ms - LOCAL_RESERVE_MS),
                 profiles[release.image])
            for release in inputs.releases
        ]
        self.edge_busy_ms = 0.0
        self.max_queue = 0

    def cutoff(self, task):
        return task.fallback if self.allow_local else task.deadline

    def alive(self, task, epoch):
        return (
            epoch == task.client_epoch and task.adopted is None and
            not task.local_started and self.clock.now < self.cutoff(task)
        )

    def predicted_wait(self, task):
        now = self.clock.now
        availability = [max(now, free) for free in self.free_at]
        heapq.heapify(availability)
        for waiting, epoch, grade in self.pending:
            if self.clock.now >= self.cutoff(waiting) or waiting.edge_epoch != epoch or waiting is task:
                continue
            start = heapq.heappop(availability)
            heapq.heappush(availability, start + waiting.tiers[grade].service)
        return availability[0] - now

    def fits(self, task, grade, input_needed=True, control_ms=0):
        tier = task.tiers[grade]
        packet_ms = 0
        for direction, size in (("up", tier.upload if input_needed else 0), ("down", tier.download)):
            if size:
                queued = self.network.queued_bytes[direction]
                rate = self.network.observed(direction)
                if direction == "down":
                    queued += self.network.queued_bytes["fh"]
                    fh_rate = self.network.rate("fh", max(0.0, self.clock.now - 10))[0]
                    packet_ms += (size + self.network.queued_bytes["fh"]) * 0.008 / fh_rate
                packet_ms += (queued + size) * 0.008 / rate + BASE_TRANSIT_MS + 1.5
        return (
            self.clock.now + control_ms + packet_ms + tier.service + self.predicted_wait(task)
            + (tier.prepare if input_needed else 0) < self.cutoff(task)
        )

    def close_negotiation(self, task):
        if task.negotiation_open is not None:
            task.negotiation_ms += self.clock.now - task.negotiation_open
            task.negotiation_open = None

    def release(self, task):
        self.start_negotiation(task, MAIN)
        if self.allow_local:
            self.clock.schedule(task.fallback, self.fallback, task)
        self.clock.schedule(task.deadline, self.close_negotiation, task)

    def fallback(self, task):
        self.close_negotiation(task)
        if task.adopted is not None:
            return
        task.local_started = True  # locks edge adoption at the predeclared instant
        terminal = task.release.terminal
        start = max(self.clock.now, self.local_free_at.get(terminal, 0.0))
        if start >= task.deadline:
            task.reason = "local_queue"
            return
        end = start + task.tiers[LOCAL].service
        self.local_free_at[terminal] = end
        self.clock.schedule(end, self.adopt_local, task)

    def adopt_local(self, task):
        task.local_finished = True
        if self.clock.now < task.deadline:
            task.grade, task.adopted, task.reason = LOCAL, self.clock.now, "timely"
        else:
            task.reason = "local_late"

    def control(self, task, direction, size, callback):
        self.network.send(task, direction, size, True, self.cutoff(task), callback)

    def start_negotiation(self, task, offered):
        if task.adopted is not None or task.local_started or self.clock.now >= self.cutoff(task):
            return
        task.client_epoch += 1
        epoch = task.client_epoch
        task.requests += 1
        task.negotiation_open = self.clock.now
        task.rounds += 1
        self.control(task, "up", 720 if self.menu else 512,
                     lambda ok: self.on_intent(task, epoch, offered, ok))

    def on_intent(self, task, epoch, offered, ok):
        if not ok:
            self.on_decision(task, epoch, None, False)
            return
        # This grant check runs at the edge after request delivery.
        accepted = offered if self.fits(task, offered, control_ms=3 * BASE_TRANSIT_MS) else None
        if not accepted and self.menu and self.fits(task, LIGHT, control_ms=3 * BASE_TRANSIT_MS):
            accepted = LIGHT
        self.clock.schedule(
            self.clock.now + CONTROL_SERVICE_MS, self.control, task, "down",
            (448 if self.menu else 320) if accepted else 240,
            lambda delivered: self.on_decision(task, epoch, accepted, delivered),
        )

    def on_decision(self, task, epoch, grade, ok):
        if not self.alive(task, epoch):
            return
        if not ok or grade is None:
            self.close_negotiation(task)
            task.reason = "control_loss" if not ok else "admission"
            if ok and self.reactive and epoch == 1:
                self.start_negotiation(task, LIGHT)
            return
        task.rounds += 1
        self.control(task, "up", 320, lambda delivered: self.on_commit(task, epoch, grade, delivered))

    def on_commit(self, task, epoch, grade, ok):
        if not ok:
            self.on_receipt(task, epoch, grade, False)
            return
        if epoch <= task.edge_epoch:
            raise AssertionError("commit delivered twice or out of order")
        task.edge_epoch = epoch
        self.clock.schedule(
            self.clock.now + CONTROL_SERVICE_MS, self.control, task, "down", 384,
            lambda delivered: self.on_receipt(task, epoch, grade, delivered),
        )

    def on_receipt(self, task, epoch, grade, ok):
        if not self.alive(task, epoch):
            return
        self.close_negotiation(task)
        if not ok:
            task.reason = "control_loss"
            return
        task.grants += 1
        if grade == LIGHT:
            task.grant_light += 1
        if grade == MAIN and not self.fits(task, MAIN):
            if self.reactive and epoch == 1:
                self.start_negotiation(task, LIGHT)
                return
            if self.menu and self.fits(task, LIGHT):
                grade = LIGHT
                task.switch_upload += 1
        self.clock.schedule(
            self.clock.now + task.tiers[grade].prepare, self.send_input, task, epoch, grade,
        )

    def send_input(self, task, epoch, grade):
        if not self.alive(task, epoch):
            return
        self.network.send(task, "up", task.tiers[grade].upload + 64, False, self.cutoff(task),
                          lambda ok: self.receive_input(task, epoch, grade, ok))

    def receive_input(self, task, epoch, grade, ok):
        if not ok:
            if task.adopted is None and not task.local_started:
                task.reason = "uplink"
            return
        if task.edge_epoch != epoch or self.clock.now >= self.cutoff(task):
            return
        if all(free > self.clock.now for free in self.free_at):
            task.busy += 1
        self.pending.append((task, epoch, grade))
        self.max_queue = max(self.max_queue, len(self.pending))
        self.dispatch()

    def dispatch(self):
        now = self.clock.now
        while self.pending:
            slot = min(range(len(self.free_at)), key=self.free_at.__getitem__)
            if self.free_at[slot] > now:
                return
            task, epoch, grade = self.pending.popleft()
            if task.edge_epoch != epoch or self.cutoff(task) <= now:
                continue
            if grade == MAIN and not self.fits(task, MAIN, input_needed=False):
                if self.reactive and epoch == 1:
                    self.control(task, "down", 224,
                                 lambda ok, task=task, epoch=epoch: self.on_revision_needed(task, epoch, ok))
                    continue
                if self.menu and self.fits(task, LIGHT, input_needed=False):
                    grade = LIGHT
                    task.switch_edge += 1
            if task.edge_started_epoch >= epoch:
                raise AssertionError("duplicate edge execution")
            task.edge_started_epoch = epoch
            end = now + task.tiers[grade].service
            self.free_at[slot] = end
            self.edge_busy_ms += end - now
            self.clock.schedule(end, self.edge_result, task, epoch, grade)

    def on_revision_needed(self, task, epoch, ok):
        if ok and self.alive(task, epoch):
            self.start_negotiation(task, LIGHT)

    def edge_result(self, task, epoch, grade):
        if task.edge_epoch == epoch and self.clock.now < self.cutoff(task):
            self.network.send(
                task, "down", task.tiers[grade].download + 64, False, self.cutoff(task),
                lambda ok: self.receive_result(task, epoch, grade, ok),
            )
        self.dispatch()

    def receive_result(self, task, epoch, grade, ok):
        if ok and self.alive(task, epoch):
            task.grade, task.adopted, task.reason = grade, self.clock.now, "timely"
        elif ok:
            task.stale_results += 1
        elif task.adopted is None and not task.local_started:
            task.reason = "downlink"

    def run(self):
        for task in self.tasks:
            self.clock.schedule(task.release.at, self.release, task)
        self.clock.run()
        for task in self.tasks:
            if (task.grade == MISSED) != (task.adopted is None):
                raise AssertionError("unaccounted outcome")
            if task.adopted is not None and not task.release.at <= task.adopted < task.deadline:
                raise AssertionError("adoption outside deadline")
            if task.grade in (MAIN, LIGHT) and task.adopted >= self.cutoff(task):
                raise AssertionError("late edge adoption")
            if task.negotiation_open is not None:
                raise AssertionError("negotiation missing terminal accounting")
        return self.tasks


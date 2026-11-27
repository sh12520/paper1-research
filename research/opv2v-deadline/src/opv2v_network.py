"""Deterministic message and detection timing for the frozen OPV2V comparison."""

from collections import deque
from collections.abc import Mapping
from fractions import Fraction
from numbers import Integral


OBSERVATION_MS = Fraction(5)
SELECTION_MS = 2
REQUEST_PROCESS_MS = 1
FUSION_MS = 3
LOCAL_READY_MS = OBSERVATION_MS + FUSION_MS

PROACTIVE_MODES = {"blindmap", "dense", "observation", "oracle"}
REQUEST_MODES = {"feedback", "parallel", "followup"}
TWO_PACKET_MODES = {"parallel", "followup"}


def _quantity(value, name, *, allow_zero=False):
    try:
        amount = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if amount < 0 or (amount == 0 and not allow_zero):
        bound = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {bound}")
    return amount


def _check_messages(mode, messages):
    for sender, message in enumerate(messages, 1):
        index = message["sender"]
        if isinstance(index, bool) or not isinstance(index, Integral) or index != sender:
            raise ValueError("senders must be in native order, numbered from 1")
        for field in ("first_bytes", "extra_bytes", "request_bytes"):
            size = message[field]
            if isinstance(size, bool) or not isinstance(size, Integral) or size < 0:
                raise ValueError(f"sender {sender}: {field} must be a nonnegative integer")
        if mode in PROACTIVE_MODES and message["request_bytes"]:
            raise ValueError(f"sender {sender}: {mode} does not send requests")
        if mode not in TWO_PACKET_MODES and message["extra_bytes"]:
            raise ValueError(f"sender {sender}: {mode} does not send a second packet")
        dependent_field = "first_bytes" if mode == "feedback" else "extra_bytes"
        if mode in REQUEST_MODES and message[dependent_field] and not message["request_bytes"]:
            raise ValueError(f"sender {sender}: nonempty {dependent_field} requires a request")


def _message(sender, kind, size, ready, select_start=None):
    return {
        "sender": int(sender),
        "kind": kind,
        "direction": "downlink" if kind == "request" else "uplink",
        "bytes": int(size),
        "empty": not size,
        "select_start_ms": select_start,
        "ready_ms": ready,
        "start_ms": None,
        "finish_ms": None,
        "arrival_ms": None,
        "fusion_start_ms": None,
        "fusion_complete_ms": None,
    }


def _feature_message(sender, kind, size, select_start):
    ready = None if select_start is None else select_start + SELECTION_MS
    return _message(sender, kind, size, ready, select_start)


def _transmit(records, rate, propagation, available=0):
    nonempty = (record for record in records if not record["empty"])
    for record in sorted(nonempty, key=lambda item: (item["ready_ms"], item["sender"])):
        start = max(available, record["ready_ms"])
        available = start + 8 * record["bytes"] / (1000 * rate)
        record["start_ms"] = start
        record["finish_ms"] = available
        record["arrival_ms"] = available + propagation
    return available


def _add_detection_stages(stages, records):
    pending = deque(sorted(
        (record for record in records if not record["empty"]),
        key=lambda item: (item["arrival_ms"], item["sender"]),
    ))
    while pending:
        previous = stages[-1]
        start = max(previous["ready_ms"], pending[0]["arrival_ms"])
        ready = start + FUSION_MS
        packets = list(previous["packets"])
        while pending and pending[0]["arrival_ms"] <= start:
            record = pending.popleft()
            record["fusion_start_ms"] = start
            record["fusion_complete_ms"] = ready
            packets.append((record["sender"], record["kind"]))
        stages.append({"start_ms": start, "ready_ms": ready, "packets": packets})


def _public_record(record):
    # Exact internal timestamps preserve queue ties and fusion batching.
    return {key: float(value) if isinstance(value, Fraction) else value for key, value in record.items()}


def _record_order(record):
    time = record["start_ms"] if not record["empty"] else record["ready_ms"]
    return (float("inf") if time is None else time, record["direction"], record["sender"])


def schedule(mode, rates_mbps, rtt_ms, messages):
    """Return modeled transmissions and all completed detection stages.

    ``rates_mbps`` is either a symmetric rate or a mapping with ``uplink``
    (collaborators to ego) and ``downlink`` (ego to collaborators) rates. Each
    message descriptor gives a native ``sender`` index and ``first_bytes``,
    ``extra_bytes`` and ``request_bytes`` including any application header.
    In feedback mode, ``first_bytes`` is the response. A zero-byte record
    takes no network time and cannot enter fusion. For a deadline, use the
    last stage with ``ready_ms`` at or below the deadline. Transmissions and
    ``total_bytes`` include messages regardless of the deadline.
    """
    if mode not in PROACTIVE_MODES | REQUEST_MODES:
        raise ValueError(f"unknown OPV2V network mode: {mode!r}")
    messages = list(messages)
    _check_messages(mode, messages)

    if isinstance(rates_mbps, Mapping):
        uplink = _quantity(rates_mbps["uplink"], "uplink rate")
        downlink = _quantity(rates_mbps["downlink"], "downlink rate")
    else:
        uplink = downlink = _quantity(rates_mbps, "link rate")
    propagation = _quantity(rtt_ms, "RTT", allow_zero=True) / 2

    stages = [{"start_ms": OBSERVATION_MS, "ready_ms": LOCAL_READY_MS, "packets": []}]
    autonomous = []
    if mode != "feedback":
        autonomous = [
            _feature_message(message["sender"], "first", message["first_bytes"], OBSERVATION_MS)
            for message in messages
        ]
    uplink_available = 0
    if mode == "followup":
        uplink_available = _transmit(autonomous, uplink, propagation)
        _add_detection_stages(stages, autonomous)

    requests = []
    responses = []
    if mode in REQUEST_MODES:
        request_ready = stages[-1]["ready_ms"] if mode == "followup" else OBSERVATION_MS
        requests = [
            _message(message["sender"], "request", message["request_bytes"], request_ready)
            for message in messages
        ]
        _transmit(requests, downlink, propagation)
        kind = "first" if mode == "feedback" else "extra"
        for message, request in zip(messages, requests):
            arrival = request["arrival_ms"]
            selection_start = None if arrival is None else arrival + REQUEST_PROCESS_MS
            responses.append(_feature_message(message["sender"], kind, message[f"{kind}_bytes"], selection_start))

    remaining_data = responses if mode == "followup" else [*autonomous, *responses]
    _transmit(remaining_data, uplink, propagation, available=uplink_available)
    _add_detection_stages(stages, remaining_data)
    transmissions = sorted([*requests, *autonomous, *responses], key=_record_order)
    return {
        "transmissions": [_public_record(record) for record in transmissions],
        "detection_stages": [_public_record(stage) for stage in stages],
        "total_bytes": sum(record["bytes"] for record in transmissions),
    }

"""Real loopback acceptance checks for signed session permits.

The client runs in this process and the authority in its own process.
Each fault acts on delivered application messages, never on host networking.
"""
import argparse
import concurrent.futures
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw

RDINP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RDINP / "protocol" / "permit-v1"))
from permit import AdoptionGuard, Client, TransportError, start_server, write_config
from adoption import fallback


NS_MS = 1_000_000
TASK_MS = 400
LOCAL_MS = 55
PRINCIPAL = "matrix-terminal"
MAIN = "main"
ISSUE = {
    "ttl_ms": 2_000,
    "max_tasks": 8,
    "max_slots": 1,
    "max_input_bytes": 1048576,
    "max_budget_ms": TASK_MS,
}


def need(condition, detail):
    if not condition:
        raise AssertionError(detail)


def png_fixture():
    image = Image.new("RGB", (192, 192), "#1b355a")
    drawing = ImageDraw.Draw(image)
    for size in range(8, 93, 8):
        drawing.rectangle((96 - size, 96 - size, 96 + size, 96 + size), outline="#f5aa35", width=2)
    drawing.line((16, 174, 170, 16), fill="#eefafa", width=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def client_factory(config_path, port):
    def build(after_receive=None):
        return Client(config_path, port, PRINCIPAL, after_receive=after_receive)
    return build


def start_lab(path):
    config = write_config(path / "config", [PRINCIPAL], slots=1)
    port_file = path / "port"
    process = start_server(config, port_file)
    try:
        start_limit = time.monotonic() + 20
        while not port_file.is_file() or not port_file.stat().st_size:
            if process.poll() is not None:
                raise RuntimeError(f"authority exited before binding with exit {process.returncode}")
            if time.monotonic() >= start_limit:
                raise TimeoutError("authority did not report a port")
            time.sleep(.01)
        return process, client_factory(config, int(port_file.read_text(encoding="utf-8")))
    except BaseException:
        stop_lab(process)
        raise


def stop_lab(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)



@contextmanager
def lab_directory():
    workspace = tempfile.TemporaryDirectory(prefix="rdinp-permit-check-")
    path = Path(workspace.name).resolve()
    need(path.parent == Path(tempfile.gettempdir()).resolve(), "unexpected temporary directory")
    try:
        yield path
    finally:
        # Windows can briefly retain an SQLite handle after the child has exited.
        # Retry only this owned test directory, never a shared run or fixture.
        for delay in (0, .05, .1, .25, .5):
            time.sleep(delay)
            try:
                workspace.cleanup()
                break
            except OSError as error:
                if getattr(error, "winerror", None) not in {32, 267} or delay == .5:
                    raise


def issue(client, session):
    reply = client.call("ISSUE", {"session": session, **ISSUE}, timeout_s=1.0)
    need(reply.verified and reply.status == "PERMIT", f"expected verified permit, got {reply.status}")
    permit = reply.body["permit"]
    need(permit["body"]["session"] == session, "permit session mismatch")
    return permit


def task_body(permit, task_id, payload):
    release = time.perf_counter_ns()
    return {
        "permit": permit,
        "task_id": task_id,
        "input_sha256": hashlib.sha256(payload).hexdigest(),
        "input_tier": MAIN,
        "accepted_tier": MAIN,
        "release_ns": release,
        "edge_cutoff_ns": release + (TASK_MS - LOCAL_MS) * NS_MS,
        "deadline_ns": release + TASK_MS * NS_MS,
        "post_upload": "none",
        "tail_budget_ns": {"main": 80 * NS_MS, "light": 40 * NS_MS},
    }


def valid_result(reply, body):
    need(reply.verified and reply.status == "RESULT", f"expected verified result, got {reply.status}: {reply.body}")
    need(reply.body["task_id"] == body["task_id"], "result task mismatch")
    need(reply.body["input_sha256"] == body["input_sha256"], "result input mismatch")
    need(reply.body["result_sha256"] == hashlib.sha256(reply.payload).hexdigest(), "result digest mismatch")


def observe(guard, reply, body, permit=None):
    return guard.adopt(
        reply, task_id=body["task_id"], input_sha256=body["input_sha256"],
        permit=body["permit"] if permit is None else permit,
        cutoff_ns=body["edge_cutoff_ns"], allowed_tiers={MAIN},
    )


def audit(client):
    reply = client.call("AUDIT", {}, timeout_s=1.0)
    need(reply.verified and reply.status == "AUDIT", "unverified audit snapshot")
    return reply.body


def task_audit(client, task_id, *, expected_effects=1, expected_starts=1):
    matches = [row for row in audit(client)["tasks"] if row["task_id"] == task_id]
    need(len(matches) == 1, f"expected one persistent task identity, got {len(matches)}")
    row = matches[0]
    need(row["starts"] == expected_starts, f"unexpected worker starts: {row}")
    need(row["effects"] == expected_effects, f"unexpected final effects: {row}")
    return row


def has_local_adoption(source, deadline, cutoff):
    result, observed, timely = fallback(source, deadline, cutoff)
    need(timely and cutoff <= observed < deadline, "local fallback outside adoption interval")
    with Image.open(io.BytesIO(result)) as image:
        need(image.size == (256, 256), f"fallback emitted unexpected tier {image.size}")
    return observed


def ms(later, earlier):
    return (later - earlier) / NS_MS


def clean_path(build, source):
    client = build()
    permit = issue(client, "control")
    body = task_body(permit, "clean-task", source)
    reply = client.call("TASK", body, source, timeout_s=1.0)
    valid_result(reply, body)
    need(observe(AdoptionGuard(), reply, body), "clean timely result unexpectedly rejected")
    row = task_audit(client, body["task_id"])
    need(row["result_sha256"] == reply.body["result_sha256"], "persistent result disagrees with response")
    return {"accepted": True, "worker_starts": row["starts"], "effects": row["effects"]}


def receipt_fault(build, source, mode):
    authority = build()
    before = audit(authority)
    reached = []
    def intercept(kind, control_bytes, _payload_bytes):
        if kind != "ISSUE":
            return None
        reached.append((time.perf_counter_ns(), control_bytes))
        if mode == "lost":
            return False
        time.sleep(.46)
        return None

    client = build(intercept)
    release = time.perf_counter_ns()
    cutoff = release + (TASK_MS - LOCAL_MS) * NS_MS
    deadline = release + TASK_MS * NS_MS
    observed_tokens = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
        f = workers.submit(issue, client, f"receipt-{mode}")
        try:
            f.result(timeout=max(0, (cutoff - time.perf_counter_ns()) / 1e9))
        except TransportError as error:
            need(mode == "lost" and str(error) == "injected downlink drop",
                 "receipt was not rejected by the intentional loss")
            need(error.reply.response_control_bytes > 0 and not error.reply.verified,
                 "loss fixture delivered a verified permit")
        except concurrent.futures.TimeoutError:
            need(mode == "delayed", "lost reply injection did not reach the receiver")
        else:
            raise AssertionError("faulted receipt became usable before fallback")
        when = has_local_adoption(source, deadline, cutoff)
        if mode == "delayed":
            signed_token = f.result(timeout=2)
            need(time.perf_counter_ns() >= cutoff, "delayed permit unexpectedly within cutoff")
            need(signed_token["body"]["generation"] > 0, "expected a valid delayed permit")
            observed_tokens = 1
    need(len(reached) == 1 and reached[0][1] > 0, "no real receipt was faulted")
    after = audit(authority)
    need((before["starts"], before["effects"]) == (after["starts"], after["effects"]),
         "receipt fault triggered edge execution")
    # A clean follow-up verifies the initial issue applied at the authority.
    next_token = issue(authority, f"receipt-{mode}")
    need(next_token["body"]["generation"] == 2, "first issue did not advance the authority generation")
    return {
        "faulted_receipt_bytes": reached[0][1],
        "late_valid_tokens_observed": observed_tokens,
        "generation_after_follow_up_issue": next_token["body"]["generation"],
        "fallback_adopted_ms": ms(when, release),
        "edge_worker_starts": after["starts"] - before["starts"],
        "edge_effects": after["effects"] - before["effects"],
    }


def late_result(build, source):
    direct = build()
    token = issue(direct, "late-result")
    captured = []
    def delay(kind, control_bytes, payload_bytes):
        if kind == "TASK":
            captured.append((control_bytes, payload_bytes))
            time.sleep(.46)
        return None

    client = build(delay)
    body = task_body(token, "late-edge-result", source)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
        f = workers.submit(client.call, "TASK", body, source, timeout_s=1.2)
        adopted = has_local_adoption(source, body["deadline_ns"], body["edge_cutoff_ns"])
        reply = f.result(timeout=2)
        arrived = time.perf_counter_ns()
    valid_result(reply, body)
    need(arrived >= body["deadline_ns"], "did not actually deliver after hard deadline")
    guard = AdoptionGuard()
    need(not observe(guard, reply, body), "late signed result polluted local adoption")
    need(guard.counts["late"] == 1, "late result rejected for another reason")
    need(len(captured) == 1 and min(captured[0]) > 0, "did not delay signed data response")
    row = task_audit(direct, body["task_id"])
    return {
        "signed_result_delivered_ms": ms(arrived, body["release_ns"]),
        "fallback_adopted_ms": ms(adopted, body["release_ns"]),
        "late_rejections": 1, "effect_count": row["effects"], "guard": dict(guard.counts),
    }


def stale_result(build, source):
    client = build()
    first = issue(client, "rollover")
    body = task_body(first, "prior-generation-result", source)
    reply = client.call("TASK", body, source, timeout_s=1.0)
    valid_result(reply, body)
    renewed = issue(client, "rollover")
    need(renewed["body"]["generation"] > first["body"]["generation"], "renewal did not advance generation")
    seen = time.perf_counter_ns()
    need(seen < body["edge_cutoff_ns"], "stale generation case accidentally missed cutoff")
    need(observe(AdoptionGuard(), reply, body), "old result was invalid under its own generation")
    guard = AdoptionGuard()
    need(not observe(guard, reply, body, renewed), "old-generation result accepted under renewed permit")
    need(guard.counts["old_generation"] == 1, "old result rejected for another reason")
    row = task_audit(client, body["task_id"])
    return {
        "prior_generation": first["body"]["generation"], "current_generation": renewed["body"]["generation"],
        "signed_result_presentation_ms": ms(seen, body["release_ns"]),
        "stale_generation_rejections": 1, "effect_count": row["effects"], "guard": dict(guard.counts),
    }


def duplicate_commit(build, source):
    client = build()
    first = issue(client, "duplicates")
    body = task_body(first, "same-stable-task", source)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
        sends = [workers.submit(build().call, "TASK", body, source, timeout_s=1.0) for _ in range(2)]
        responses = [job.result() for job in sends]
    need(all(reply.verified for reply in responses), "unverified concurrent duplicate response")
    results = [reply for reply in responses if reply.status == "RESULT"]
    need(bool(results), "all concurrent attempts rejected")
    for reply in results:
        valid_result(reply, body)
        need(reply.body["result_sha256"] == results[0].body["result_sha256"],
             "duplicate returned a different result")
    guard = AdoptionGuard()
    need(observe(guard, results[0], body), "initial duplicate-race winner not adoptable")
    need(not observe(guard, results[0], body), "same signed result adopted twice")
    need(guard.counts["duplicate"] == 1, "duplicate result rejected for another reason")
    initial = task_audit(client, body["task_id"])
    renewed = issue(client, "duplicates")
    need(renewed["body"]["generation"] > first["body"]["generation"], "duplicate case did not renew")
    replay = task_body(renewed, body["task_id"], source)
    reply = client.call("TASK", replay, source, timeout_s=1.0)
    need(reply.verified, "unverified cross-generation duplicate response")
    need(reply.status in {"REJECT", "RESULT"}, f"unexpected duplicate status: {reply.status}")
    if reply.status == "RESULT":
        need(reply.body["result_sha256"] == initial["result_sha256"], "renewed duplicate changed outcome")
    row = task_audit(client, body["task_id"])
    need(initial == row, "logical identity or effect state changed on cross-generation repeat")
    fresh = task_body(renewed, "fresh-under-renewal", source)
    fresh_reply = client.call("TASK", fresh, source, timeout_s=1.0)
    valid_result(fresh_reply, fresh)
    need(observe(AdoptionGuard(), fresh_reply, fresh), "renewal blocked an unrelated new task")
    return {
        "same_generation_statuses": [response.status for response in responses],
        "renewed_duplicate_status": reply.status,
        "worker_starts_for_reused_id": row["starts"], "effects_for_reused_id": row["effects"],
        "duplicate_adoption_rejections": 1, "guard": dict(guard.counts),
        "fresh_task_under_renewed_permit": fresh_reply.status,
    }


def source_fingerprints():
    paths = [
        *sorted((RDINP / "protocol" / "permit-v1").glob("*.py")),
        RDINP / "protocol" / "permit-v1" / "permit.schema.json",
        *[RDINP / "protocol" / "c2" / name
          for name in ("contracts.py", "crypto.py", "trust.schema.json")],
        RDINP / "experiments" / "service-worker" / "image_workload.py",
        Path(__file__).resolve(),
        Path(__file__).with_name("adoption.py").resolve(),
    ]
    return {
        path.relative_to(RDINP).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    before = source_fingerprints()
    cases = [
        ("clean_control", clean_path),
        ("receipt_lost", lambda build, source: receipt_fault(build, source, "lost")),
        ("receipt_delayed", lambda build, source: receipt_fault(build, source, "delayed")),
        ("late_result", late_result),
        ("old_generation_result", stale_result),
        ("duplicate_commit_across_renewal", duplicate_commit),
    ]
    source = png_fixture()
    rows = []
    with lab_directory() as folder:
        process, build = start_lab(folder)
        try:
            for name, check in cases:
                try:
                    rows.append({"case": name, "status": "PASS", **check(build, source)})
                except Exception as error:
                    rows.append({"case": name, "status": "FAIL",
                                 "error_type": type(error).__name__, "error": str(error)})
                    break
        finally:
            stop_lab(process)
    source_unchanged = before == source_fingerprints()
    passed = source_unchanged and len(rows) == len(cases) and all(row["status"] == "PASS" for row in rows)
    data = {
        "scope": "signatures, durable task effects, independent loopback authority, controlled receipt faults",
        "fixture_input_sha256": hashlib.sha256(source).hexdigest(),
        "source_sha256": before, "source_unchanged": source_unchanged,
        "python": platform.python_version(), "clock": "perf_counter_ns (shared local host)",
        "deadline_ms": TASK_MS, "local_reserve_ms": LOCAL_MS,
        "status": "PASS" if passed else "FAIL", "expected_cases": len(cases), "cases": rows,
        "old_generation_pollution": 0 if passed else None,
        "duplicate_effects": 0 if passed else None,
    }
    (output / "safety.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False))
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    sys.exit(0 if run(args.out) else 1)

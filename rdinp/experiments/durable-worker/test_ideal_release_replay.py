"""Regression coverage for the C2-conditioned release sensitivity."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ideal_release_replay import analyze

ROOT_CLOCK = {"host": "test-host", "boot": "host-boot", "clock": "host-monotonic"}
DIGEST = "a" * 64
CONTRACT = "b" * 64
WORKLOAD = "e" * 64
ORIGIN = 10_000
C2_ORIGIN = 9_800


def write_events(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def plan_for(c2=True):
    # A starts at t=100, then falls back at t=250. B's grant at t=300
    # can complete before its fallback only when A's slot is free.
    tasks = [
        {"task_id": "a", "terminal": 0, "input_sha256": DIGEST, "release_offset_ns": 0,
         "fallback_ns": 250, "deadline_ns": 720},
        {"task_id": "b", "terminal": 1, "input_sha256": DIGEST, "release_offset_ns": 200,
         "fallback_ns": 350, "deadline_ns": 620},
        {"task_id": "c", "terminal": 2, "input_sha256": DIGEST, "release_offset_ns": 0,
         "fallback_ns": 720, "deadline_ns": 930},
        {"task_id": "d", "terminal": 3, "input_sha256": DIGEST, "release_offset_ns": 0,
         "fallback_ns": 720, "deadline_ns": 930},
    ]
    return {
        "schema": "rdinp-concurrent-v1", "run_id": "run1",
        "authorization": "frozen_bilateral_c2" if c2 else "prebound_application",
        "minimum_quality": "edge", "public_fallback": True, "lease_ns": 300,
        "rto_ns": 100, "service_ms": 0.0002,
        "source_sha256": {"image_workload.py": WORKLOAD},
        "pairs": [{"pair_id": "pair1", "load": 0.9, "condition": "none", "slots": 1,
                   "tasks": tasks, "windows": []}],
    }


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "runs" / "pair1" / "B2-info" / "events.jsonl"

    def write_plan(self, plan):
        (self.root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

    def fixture(self):
        plan = plan_for()
        self.write_plan(plan)
        events = []

        def add(name, timestamp, task=None, **fields):
            events.append({"event": name, "monotonic_ns": timestamp,
                           "task_id": None if task is None else task["task_id"],
                           "negotiationId": None if task is None else task["task_id"],
                           "method": "B2-info", "run_id": "run1", "pair_id": "pair1", **ROOT_CLOCK, **fields})

        add("C2_CLOCK_BIND", C2_ORIGIN + 1, origin_ns=C2_ORIGIN, c2_boot="c2-boot",
            c2_contract_digest=CONTRACT)
        add("CASE_START", ORIGIN - 50, authorization=plan["authorization"], origin_ns=ORIGIN)
        add("CASE_END", ORIGIN + 1_900, rows=4)
        for task, offset, before_lease in zip(plan["pairs"][0]["tasks"], (2, 210, None, 101), (True, True, False, False)):
            index = task["terminal"]
            intent = "0123"[index] * 64
            binding = {**task, "pair_id": "pair1", "timing_contract_digest": CONTRACT, "authority": "authority",
                       "initiator": f"terminal-{index}"}
            start = ORIGIN + task["release_offset_ns"]
            add("C2_TASK_BIND", ORIGIN - 80 + index, task,
                terminal=index, input_sha256=DIGEST, intentId=intent, binding=binding)
            add("RELEASE", start + 1, task, terminal=index, release_ns=start,
                fallback_ns=start + task["fallback_ns"], deadline_ns=start + task["deadline_ns"])
            add("C2_CLIENT_TERMINAL", ORIGIN + 1_000 + index, task, terminal=index, intentId=intent)
            approval = None
            lane_events = [{"event": "BOOT_READY"}]
            if offset is not None:
                absolute = ORIGIN + offset
                observed = absolute - C2_ORIGIN
                approval = {
                    "c2_authority_state": "CONFIRMED", "c2_intent_id": intent, "c2_terminal": index,
                    "c2_commit_effect_tx": f"effect-{index}", "c2_commit_transaction_id": f"txn-{index}",
                    "c2_commit_before_lease": before_lease, "c2_commit_return_ns": absolute,
                    "c2_receipt_digest": "c" * 64, "c2_decision_digest": "d" * 64, "c2_request_raw_sha256": DIGEST,
                }
                lane_events.extend([
                    {"event": "LEASE_ANCHOR", "leaseUntilNs": observed + (1 if before_lease else -1),
                     "intentId": intent, "negotiationId": task["task_id"]},
                    {"event": "DURABLE_COMMIT_RETURN", "effectTx": f"effect-{index}",
                     "transactionId": f"txn-{index}", "rawSha256": DIGEST,
                     "phase": "COMMIT_INITIAL", "intentId": intent, "negotiationId": task["task_id"],
                     "observedNs": observed},
                ])
                add("C2_DURABLE_AUTHORIZED", absolute + 1, task, **approval)
            add("C2_FINAL_AUTHORIZATION", ORIGIN + 1_500 + index, task, approval=approval)
            for ordinal, event in enumerate(lane_events):
                event.update(role="responder", boot="c2-boot", unit="NANOSECONDS",
                             clockId=f"c2-authority-{index}", ordinal=ordinal)
            write_events(self.path.parent / "c2" / f"terminal-{index}" / "authority_events.jsonl", lane_events)
        events.sort(key=lambda e: e["monotonic_ns"])
        for index, event in enumerate(events):
            event["index"] = index
        write_events(self.path, events)
        return plan, events

    def split(self, calibration=True):
        delays = {"stop_ms": 0.0001} if calibration else {}
        return analyze(self.root, local_ms=0.00001, **delays)

    def test_fixed_authority_inputs_preserve_the_stop_delay_contrast(self):
        _, _ = self.fixture()
        report = self.split()
        self.assertEqual(report["status"], "MODELLED")
        case, = report["pairs"]
        inputs = {e["task_id"]: [e["state"], e["grant_ready_ns"]] for e in case["authorization_inputs"]}
        self.assertEqual(inputs, {"a": ["committed_before_lease", 2],
                                  "b": ["committed_before_lease", 210],
                                  "c": ["no_durable_commit", None],
                                  "d": ["committed_after_lease", None]})
        self.assertEqual(case["ideal_minus_control_qualified_pp"], 25.0)
        for mode, expected_b in (("model_control", "local"), ("model_ideal", "edge")):
            arm = case[mode]
            self.assertEqual(arm["released"], 4)
            outcomes = {r["task_id"]: r["modeled_origin"] for r in arm["tasks"]}
            self.assertEqual(outcomes, {"a": "local", "b": expected_b, "c": "local", "d": "local"})
        self.assertEqual(len(report["source_event_sha256"]), 5)

    def test_unsealed_old_c2_trace_returns_no_results(self):
        _, es = self.fixture()
        write_events(self.path, [e for e in es if e["event"] != "C2_FINAL_AUTHORIZATION"])
        report = self.split()
        self.assertEqual(report["status"], "NOT_CALIBRATED")
        self.assertEqual(report["missing_calibration"], ["c2_authority_coverage"])
        self.assertEqual(report["pairs"], [])

    def test_rejects_partial_or_missing_event_proof(self):
        _, es = self.fixture()
        write_events(self.path, [e for e in es if not (e["event"] == "C2_FINAL_AUTHORIZATION"
                           and e["task_id"] == "a")])
        with self.assertRaisesRegex(ValueError, "incomplete C2_FINAL_AUTHORIZATION"):
            self.split()

    def test_rejects_tampered_commit_clock_even_when_final_and_prior_agree(self):
        _, es = self.fixture()
        for e in es:
            if e["task_id"] == "a" and e["event"] == "C2_DURABLE_AUTHORIZED":
                e["c2_commit_return_ns"] += 1
            if e["task_id"] == "a" and e["event"] == "C2_FINAL_AUTHORIZATION":
                e["approval"]["c2_commit_return_ns"] += 1
        write_events(self.path, es)
        with self.assertRaisesRegex(ValueError, "proof disagree"):
            self.split()

    def test_independent_cancel_calibration_fingerprints_all_six_trials(self):
        self.fixture()
        for trial in range(6):
            trial_id = f"trial-{trial:02d}"
            task_id = trial_id + "-0"
            path = self.root / "stop-calibration" / trial_id / "events.jsonl"
            raw = [
                {"event": "CASE_START", "scope": "stop_calibration", "slots": 1, "origin_ns": 100,
                 "input_sha256": DIGEST, "workload_sha256": WORKLOAD},
                {"event": "APP_GRANT"},
                {"event": "APP_START", "worker_pid": 20},
                {"event": "APP_CANCEL_ACCEPTED", "reason": "diagnostic_stop_calibration", "commit_return_ns": 110},
                {"event": "APP_WORKER_EXIT_CONFIRMED", "worker_pid": 20, "confirmed_ns": 201},
                {"event": "APP_RELEASE", "reason": "diagnostic_stop_calibration", "release_ns": 210,
                 "commit_return_ns": 210},
                {"event": "CASE_END", "attempted": 1},
            ]
            for index, (e, timestamp) in enumerate(zip(raw, (101, 102, 103, 111, 208, 211, 220))):
                task = None if e["event"] in ("CASE_START", "CASE_END") else task_id
                e.update(monotonic_ns=timestamp, index=index, run_id="run1", pair_id=trial_id, method="stop-calibration",
                         task_id=task, negotiationId=task, **ROOT_CLOCK)
                if task:
                    e.update(epoch=1, slot=0)
            write_events(path, raw)
        report = self.split(calibration=False)
        self.assertEqual(report["status"], "MODELLED")
        self.assertEqual(report["calibration"]["stop_observations"], 6)
        self.assertEqual(report["calibration"]["positive_stop_ns"], 100)
        files = report["calibration"]["stop_calibration_files"]
        self.assertEqual(len(files), 6)
        for fname in files:
            self.assertEqual(report["source_event_sha256"][fname],
                             hashlib.sha256((self.root / fname).read_bytes()).hexdigest())
        path = self.root / files[-1]
        traces = [json.loads(line) for line in path.read_bytes().splitlines()]
        traces[0]["workload_sha256"] = "0" * 64
        write_events(path, traces)
        with self.assertRaisesRegex(ValueError, "invalid stop-calibration case binding"):
            self.split(calibration=False)

    def test_prebound_schema_remains_usable(self):
        plan = plan_for(False)
        del plan["authorization"]
        self.write_plan(plan)
        report = self.split()
        self.assertEqual(report["status"], "MODELLED")
        self.assertEqual(report["authorization"]["mode"], "prebound_application")
        self.assertNotIn("authorization_inputs", report["pairs"][0])


if __name__ == "__main__":
    unittest.main()

"""Small synthetic receipts, never G1-A experiment results."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from concurrent_audit import FIELDS, LOADS, METHODS, audit, audit_authorization, paired_interval


DIGEST_INPUT = "a" * 64
DIGESTS = {"edge": "b" * 64, "local": "c" * 64}


class ConcurrentAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def write_fixture(self, scope="engineering", methods=METHODS, *, corrupt=None):
        pairs = []
        rows = []
        for load in LOADS:
            for replicate in range(2):
                pair = f"{load}-{replicate}"
                tasks = []
                for index in range(2):
                    tasks.append({
                        "task_id": f"task{index}", "terminal": index, "release_offset_ns": index * 10,
                        "deadline_ns": 50, "fallback_ns": 30, "input_sha256": DIGEST_INPUT,
                        "expected_output_sha256": DIGESTS,
                    })
                pairs.append({"pair_id": pair, "load": load, "condition": "drop", "tasks": tasks})
                for method in methods:
                    directory = self.out / "runs" / pair / method
                    directory.mkdir(parents=True)
                    events = []
                    for task in tasks:
                        task_id = task["task_id"]

                        def record(event, timestamp, **fields):
                            events.append({
                                "event": event, "monotonic_ns": timestamp, "run_id": "test",
                                "pair_id": pair, "method": method, "task_id": task_id,
                                "negotiationId": task_id, "host": "test", "boot": "test", "clock": "monotonic",
                                **fields,
                            })

                        release = 100 + task["release_offset_ns"]
                        deadline = release + task["deadline_ns"]
                        cutoff = release + task["fallback_ns"]
                        edge = method in ("B2-info", "B2-ideal")
                        source = "edge" if edge else "local"
                        fallback = None if edge or method == "B0" else cutoff
                        adopted = release + (9 if edge else 40)
                        epoch = 2 + task["terminal"]
                        record("RELEASE", release, release_ns=release)
                        if edge:
                            record("APP_GRANT", release + 1, slot=0, epoch=epoch, commit_return_ns=release + 1)
                            record("APP_START", release + 2, slot=0, epoch=epoch, activation_ns=release + 2)
                            record(
                                "APP_WORKER_EXIT_CONFIRMED", release + 6, slot=0, epoch=epoch,
                                confirmed_ns=release + 5,
                            )
                            record(
                                "APP_RELEASE", release + 7, slot=0, epoch=epoch,
                                release_ns=release + 7, commit_return_ns=release + 7, reason="complete",
                            )
                        if fallback is not None:
                            record("FALLBACK", fallback, fallback_started_ns=fallback)
                        row = {
                            "pair_id": pair, "method": method, "task_id": task_id, "terminal": task["terminal"],
                            "input_sha256": DIGEST_INPUT, "release_ns": release, "deadline_ns": deadline,
                            "adopted_ns": adopted, "source": source, "quality": source, "quality_ok": int(edge),
                            "verified": 1, "fallback_ns": cutoff, "fallback_started_ns": fallback,
                            "output_sha256": DIGESTS[source],
                        }
                        if edge:
                            record("APP_COMPLETE", release + 7, slot=0, epoch=epoch, success=True,
                                   result_sha256=DIGESTS[source], commit_return_ns=release + 7)
                            record("EDGE_READBACK_VERIFIED", adopted - 1, epoch=epoch,
                                   observed_ns=adopted - 1, result_sha256=DIGESTS[source])
                        else:
                            record("LOCAL_COMPLETE", adopted - 1, result_sha256=DIGESTS[source])
                        record("ADOPT", adopted, adopted_ns=adopted, source=source, quality=source,
                               output_sha256=DIGESTS[source])
                        if corrupt == "false_digest" and method == "B1":
                            row["output_sha256"] = "d" * 64
                        if corrupt == "duplicate" and method == "B0":
                            rows.append(row)
                        if not (corrupt == "missing_row" and method == "B1" and task_id == "task0"):
                            rows.append(row)
                    if corrupt == "ambiguous_adopt":
                        events = [event for event in events if event["event"] != "ADOPT"]
                    if corrupt == "uncommitted_release":
                        for event in events:
                            if event["event"] == "APP_RELEASE":
                                event["commit_return_ns"] += 1
                    if corrupt == "no_exit":
                        events = [event for event in events if event["event"] != "APP_WORKER_EXIT_CONFIRMED"]
                    (directory / "events.jsonl").write_text(
                        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
                    )

        (self.out / "plan.json").write_text(json.dumps({
            "schema": "rdinp-concurrent-v1", "scope": scope, "minimum_quality": "edge",
            "methods": methods, "run_id": "test", "pairs": pairs,
        }), encoding="utf-8")
        with (self.out / "per_task.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(FIELDS))
            writer.writeheader()
            writer.writerows(rows)

    def test_grant_requires_a_linked_prior_c2_proof(self):
        spec = {"task": {"terminal": 1, "input_sha256": DIGEST_INPUT}}
        proof = {
            "c2_intent_id": "intent", "c2_terminal": 1,
            "c2_authority_state": "CONFIRMED", "c2_commit_return_ns": 2,
            "c2_commit_before_lease": True,
        }
        ordered = [
            ("C2_TASK_BIND", {"terminal": 1, "input_sha256": DIGEST_INPUT, "intentId": "intent"}),
            ("C2_CLIENT_TERMINAL", {"intentId": "intent"}),
            ("C2_DURABLE_AUTHORIZED", proof),
            ("C2_PROOF_CHECKED_FOR_GRANT", {"approval": proof}),
            ("APP_GRANT", {"commit_return_ns": 5}),
        ]
        log = [{"event": kind, "task_id": "task", "monotonic_ns": i, **fields}
               for i, (kind, fields) in enumerate(ordered, 1)]
        self.assertEqual(
            audit_authorization(log, spec, "B1", "frozen_bilateral_c2"),
            {"authorized_tasks": 1, "actuation_grants": 1},
        )
        with self.assertRaisesRegex(ValueError, "lacks a prior C2 authorization"):
            audit_authorization(log[:3] + log[4:], spec, "B1", "frozen_bilateral_c2")
        late_recheck = {**log[3], "monotonic_ns": 6}
        printed_grant = {**log[4], "monotonic_ns": 7}
        self.assertEqual(
            audit_authorization(log[:4] + [late_recheck, printed_grant], spec, "B1", "frozen_bilateral_c2"),
            {"authorized_tasks": 1, "actuation_grants": 1},
        )

    def test_complete_design_uses_all_released_tasks(self):
        self.write_fixture("g1a")
        result = audit(self.out)
        self.assertEqual(result["runs"], 24)
        self.assertEqual(result["released_method_observations"], 48)
        self.assertEqual(result["verdict"], "GO_CANDIDATE_REQUIRES_MANUAL_REVIEW")
        self.assertEqual(result["primary_medium_high_info_minus_b1"]["ci95_pp"], [100.0, 100.0])
        for arm in result["run_results"]:
            if arm["method"] in ("B0", "B1"):
                self.assertEqual(arm["qualified"], 0)
                self.assertEqual(arm["released"], 2)
                self.assertEqual(arm["timely_local"], 2)
                self.assertEqual(arm["timely_low_quality"], 2)

    def test_engineering_partial_never_recommends_go(self):
        self.write_fixture(methods=METHODS[:-1])
        result = audit(self.out)
        self.assertEqual(result["verdict"], "INCOMPLETE_FOR_GATE")
        self.assertEqual(result["methods_not_observed"], ["B2-ideal"])

    def test_missing_row_rejected(self):
        self.write_fixture(corrupt="missing_row")
        with self.assertRaisesRegex(ValueError, "missing tasks"):
            audit(self.out)

    def test_duplicate_row_rejected(self):
        self.write_fixture(corrupt="duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit(self.out)

    def test_wrong_output_rejected(self):
        self.write_fixture(corrupt="false_digest")
        with self.assertRaisesRegex(ValueError, "differs from the planned reference"):
            audit(self.out)

    def test_missing_adoption_witness_rejected(self):
        self.write_fixture(corrupt="ambiguous_adopt")
        with self.assertRaisesRegex(ValueError, "ADOPT witness count"):
            audit(self.out)

    def test_release_before_commit_rejected(self):
        self.write_fixture(corrupt="uncommitted_release")
        with self.assertRaisesRegex(ValueError, "post-commit"):
            audit(self.out)

    def test_worker_exit_needed_for_reuse(self):
        self.write_fixture(corrupt="no_exit")
        with self.assertRaisesRegex(ValueError, "missing verified worker exit"):
            audit(self.out)

    def test_paired_resampling_is_reproducible(self):
        strata = {(0.7, "clean"): (0.0, 1.0, -0.1), (0.9, "drop"): (1.0, 0.5)}
        first = paired_interval(strata)
        self.assertEqual(first, paired_interval(strata))
        self.assertAlmostEqual(first["difference_pp"], 48.0)
        self.assertIsNone(paired_interval({(0.7, "clean"): (1.0,)})["ci95_pp"])


if __name__ == "__main__":
    unittest.main()

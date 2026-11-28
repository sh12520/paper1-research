"""Lightweight checks for G1-A design binding and inference."""

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from concurrent_audit import downstream_witnesses
from g1a_decision import (
    check_measurement, check_plan, evaluate_signal, matched_busy_exposure,
    pivot_exposures, stratified_interval, summarize,
)
from run_concurrent import CONDITIONS, DECISION_PROTOCOL, LEASE_NS, LOADS, METHODS, RTO_NS, make_pair, write_json


def plan_for(terminals=4, slots=1):
    fixture = "a" * 64
    expected = {"edge": "b" * 64, "local": "c" * 64}
    return {
        "schema": "rdinp-concurrent-v1",
        "scope": "g1a",
        "decision_protocol": DECISION_PROTOCOL,
        "authorization": "frozen_bilateral_c2",
        "transport": "directional_application_fault_windows_on_loopback",
        "service_ms": 140,
        "service_source": "calibrated",
        "minimum_quality": "edge",
        "public_fallback": True,
        "lease_ns": LEASE_NS,
        "rto_ns": RTO_NS,
        "source_sha256": {"run_concurrent.py": "d" * 64},
        "frozen_c2_sha256": {"c2": "e" * 64},
        "methods": list(METHODS),
        "run_id": "record",
        "pairs": [make_pair(f"{replicate}-{load}-{condition}", load, condition, terminals, slots,
                            12, 140_000_000, fixture, expected, use_c2=True, replicate=replicate)
                  for replicate in range(6) for load in LOADS for condition in CONDITIONS],
    }


class DesignTest(unittest.TestCase):
    def test_actual_planner_matches_independent_checker(self):
        for terminals, slots in ((4, 1), (8, 2)):
            pairs, topology, fixture = check_plan(plan_for(terminals, slots))
            self.assertEqual(len(pairs), 72)
            self.assertEqual(topology, (terminals, slots))
            self.assertEqual(fixture[0], "a" * 64)

    def test_missing_pair_and_moved_outage_are_rejected(self):
        plan = plan_for()
        bad = deepcopy(plan)
        bad["pairs"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete grid"):
            check_plan(bad)
        bad = deepcopy(plan)
        affected = next(pair for pair in bad["pairs"] if pair["windows"])
        affected["windows"][0]["start_ns"] += 1
        with self.assertRaisesRegex(ValueError, "wrong fault window"):
            check_plan(bad)

    def test_a_changed_release_or_arm_order_is_rejected(self):
        plan = plan_for()
        bad = deepcopy(plan)
        bad["pairs"][0]["tasks"][1]["release_offset_ns"] += 1
        with self.assertRaisesRegex(ValueError, "release schedule mismatch"):
            check_plan(bad)
        bad = deepcopy(plan)
        bad["pairs"][0]["method_order"] = tuple(reversed(bad["pairs"][0]["method_order"]))
        with self.assertRaisesRegex(ValueError, "method order changed"):
            check_plan(bad)

    def test_calibration_mean_is_bound_to_raw_event_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calibration = root / "calibration"
            logs = calibration / "runs" / "calibration" / "B1"
            logs.mkdir(parents=True)
            pairs = []
            for task in range(4):
                pairs.extend((
                    {"event": "APP_GRANT", "task_id": str(task), "run_id": "record",
                     "monotonic_ns": 1},
                    {"event": "APP_RELEASE", "task_id": str(task), "run_id": "record",
                     "release_ns": 140_000_001},
                ))
            (logs / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in pairs), encoding="utf-8")
            write_json(calibration / "measurement.json",
                       {"mean_ms": 140, "slot_occupancy_ns": [140_000_000] * 4})
            plan = plan_for()
            self.assertEqual(len(check_measurement(root, plan)), 64)
            plan["service_ms"] = 141
            with self.assertRaisesRegex(ValueError, "different calibration mean"):
                check_measurement(root, plan)


class InferenceTest(unittest.TestCase):
    def test_resamples_pairs_and_weights_strata_equally(self):
        interval = stratified_interval({"A": [20, 20], "B": [0, 0, 0, 0, 0, 0]})
        self.assertEqual(interval, {"paired_runs": 8, "estimate": 10, "ci95": [10, 10]})
        self.assertEqual(stratified_interval({"A": [0], "B": [0, 0]})["ci95"], None)

    def test_no_signal_is_pivot_only_if_ci_excludes_practical_margin(self):
        downstream = {"ci95": [-0.5, 1]}
        narrow = {"estimate": 0.5, "ci95": [-1, 2]}
        wide = {"estimate": 0.5, "ci95": [-5, 6]}
        self.assertEqual(evaluate_signal(narrow, downstream, [], True, True)["status"],
                         "PIVOT_CANDIDATE_REQUIRES_MANUAL_REVIEW")
        self.assertEqual(evaluate_signal(narrow, downstream, [], True, False)["status"],
                         "INCONCLUSIVE_REQUIRES_MANUAL_REVIEW")
        self.assertEqual(evaluate_signal(wide, downstream, [], True, True)["status"],
                         "INCONCLUSIVE_REQUIRES_MANUAL_REVIEW")


    def test_pivot_exposure_requires_real_triplet_and_counts_retained_epoch(self):
        pair = next(pair for pair in plan_for()["pairs"]
                    if pair["condition"] == "downlink" and pair["load"] == 0.7)
        window, = pair["windows"]
        origin = 111
        drop = {"direction": "downlink", "route": "/status", "fault_gate_ns": origin + window["start_ns"]}
        logs = {"CASE_START": [{"origin_ns": origin}], "FALLBACK": [{}], "APP_BUSY": [{}],
                "C2_RELAY_DROP": [], "RPC_DROP": [drop]}
        run = {"allocation_witnesses": [{"fallback_to_reuse_ns": 7}]}
        present = pivot_exposures(pair, logs, run)["downlink"]
        self.assertEqual(present["pairs_with_realized_drop_fallback_and_busy"], 1)
        self.assertEqual(present["pairs_with_realized_drop_fallback_busy_and_held_epoch"], 1)
        logs["APP_BUSY"] = []
        self.assertEqual(pivot_exposures(pair, logs, run)["downlink"]
                         ["pairs_with_realized_drop_fallback_and_busy"], 0)
        drop["fault_gate_ns"] -= 1
        self.assertEqual(pivot_exposures(pair, logs, run)["downlink"]["realized_drops_in_fallback_window"], 0)

    def test_busy_witness_uses_admission_commit_without_rpc_reply(self):
        host = {"host": "h", "boot": "b", "clock": "c"}
        alloc = {"task_id": "owner", "slot": 0, "epoch": 1, "allocated_ns": 140,
                 "reusable_ns": 190, "clock_domain": ["h", "b", "c"],
                 "fallback_clock_comparable": True}
        busy = {"task_id": "successor", "event": "APP_BUSY", "commit_return_ns": 170,
                "monotonic_ns": 200, **host}
        baseline = {"owner": {"qualified": False, "release_ns": 100, "fallback_started_ns": 160},
                    "successor": {"qualified": False, "release_ns": 120, "fallback_started_ns": 220}}
        oracle = {"owner": {"qualified": False, "release_ns": 1000, "source": "local"},
                  "successor": {"qualified": True, "release_ns": 1020, "source": "edge"}}
        owner = {**alloc, "allocated_ns": 1040, "reusable_ns": 1060}
        successor = {**alloc, "task_id": "successor", "epoch": 2, "allocated_ns": 1080,
                     "activated_ns": 1081, "reusable_ns": 1140}
        plan = {"owner": {"release_offset_ns": 0}, "successor": {"release_offset_ns": 20}}
        result = list(downstream_witnesses("p", baseline, oracle, [busy], [alloc], [owner, successor], plan))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["b1_busy_ns_after_task_release"], 50)

    def test_matched_exposure_requires_capacity_at_the_busy_instant(self):
        timebase = {"host": "h", "boot": "b", "clock": "c"}
        busy = {"task_id": "next", "commit_return_ns": 170, "monotonic_ns": 200, **timebase}
        owner = {"task_id": "owner", "slot": 0, "epoch": 1, "allocated_ns": 140,
                 "reusable_ns": 190, "clock_domain": ["h", "b", "c"]}
        other = {**owner, "task_id": "other", "slot": 1, "epoch": 2}
        logs = {"APP_BUSY": [busy], "FALLBACK": [{"task_id": "owner", "fallback_started_ns": 160}],
                "RPC_DROP": [{"task_id": "owner", "route": "/status", "fault_gate_ns": 153}],
                "C2_RELAY_DROP": []}
        self.assertEqual(matched_busy_exposure(logs, {"allocation_witnesses": [owner]}, 2)
                         ["busy_with_fallen_back_owner"], 0)
        self.assertEqual(matched_busy_exposure(logs, {"allocation_witnesses": [owner, other]}, 2)
                         ["busy_with_fallen_back_owner_and_linked_drop"], 1)

    def test_positive_signal_without_new_information_still_needs_attribution(self):
        primary = {"estimate": 6, "ci95": [1, 10]}
        downstream = {"ci95": [0, 0]}
        scheduler_only = [
            {"topology": (4, 1), "pair_id": str(index), "new_information_precedes_public_cutoff": False}
            for index in range(2)
        ]
        result = evaluate_signal(primary, downstream, scheduler_only, True, True)
        self.assertTrue(result["main_signal"])
        self.assertEqual(result["status"], "QUANTITATIVE_SIGNAL_REQUIRES_ATTRIBUTION")
        self.assertFalse(result["next_stage_authorized"])
        self.assertEqual(evaluate_signal(primary, downstream, scheduler_only, False, True)["status"],
                         "INCOMPLETE_FOR_GATE")


    def test_report_uses_all_releases_and_keeps_shadow_effect_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directories = [root / "416", root / "826"]
            plans = {directory: plan_for(*topology) for directory, topology in
                     zip(directories, ((4, 1), (8, 2)))}
            for directory, plan in plans.items():
                directory.mkdir()
                plan["run_id"] = directory.name
                write_json(directory / "plan.json", plan)

            def physical(directory):
                counts = []
                for pair in plans[directory]["pairs"]:
                    for method in METHODS:
                        qualified = 0 if method == "B0" else 10
                        counts.append({
                            "pair_id": pair["pair_id"], "method": method, "released": 12,
                            "qualified": qualified, "timely_edge": qualified, "timely_local": 12 - qualified,
                            "late": 0, "missing": 0, "timely_low_quality": 12 - qualified,
                            "low_tier_fallback": (12 - qualified) if method != "B0" else 0,
                            "fallback_occupied_slot_ns_per_released": 1000,
                            "fallback_cpu_ns_upper_per_released": 500,
                            "discarded_worker_cpu_ns_per_released": 300,
                            "event_sha256": "0" * 64,
                        })
                return {"run_results": counts, "plan_sha256": "1" * 64, "table_sha256": "2" * 64,
                        "pairs": 72, "released_method_observations": 72 * 3 * 12, "downstream_witnesses": []}

            def model(directory):
                return {
                    "plan_sha256": "1" * 64, "status": "MODELLED",
                    "pairs": [{"pair_id": pair["pair_id"], "model_control": {"released": 12, "qualified": 7},
                               "model_ideal": {"released": 12, "qualified": 12}}
                              for pair in plans[directory]["pairs"]],
                }

            with (patch("g1a_decision.check_measurement", return_value="3" * 64),
                  patch("g1a_decision.audit", side_effect=physical),
                  patch("g1a_decision.replay", side_effect=model),
                  patch("g1a_decision.load_timeline", return_value=defaultdict(lambda: defaultdict(list))),
                  patch("g1a_decision.audit_busy", return_value=set()),
                  patch("g1a_decision.pivot_exposures", return_value={
                      "uplink": {"pairs_with_realized_drop_fallback_and_busy": 1},
                      "downlink": {"pairs_with_realized_drop_fallback_and_busy": 1},
                  }),
                  patch("g1a_decision.read_rows", return_value=defaultdict(dict)),
                  patch("g1a_decision.verify_b1_authorities", return_value={}),
                  patch("g1a_decision.BOOTSTRAP_REPLICATES", 20)):
                report = summarize(directories, ideal_filename=None)
            self.assertEqual(report["primary"]["paired_runs"], 96)
            self.assertEqual(report["primary"]["ci95"], [0, 0])
            self.assertEqual(report["physical_counts"]["B1"]["released"], 144 * 12)
            self.assertEqual(report["B2-ideal_model_sensitivity_only"][0]["evidence"]["pairs"][0]
                             ["model_ideal"]["qualified"], 12)
            self.assertEqual(report["decision"]["status"], "PIVOT_CANDIDATE_REQUIRES_MANUAL_REVIEW")


if __name__ == "__main__":
    unittest.main()

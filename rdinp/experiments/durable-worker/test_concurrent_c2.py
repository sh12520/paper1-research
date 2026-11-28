"""Small frozen-C2 authorization and directional fault checks."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from concurrent_c2 import C2Authorization


class CommitReplyLoss:
    def suppresses(self, direction, route, timestamp_ns):
        return direction == "downlink" and route == "/rdinp/commit"


class C2BridgeChecks(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.events = []

    def pair(self, terminals):
        digest = hashlib.sha256(b"immutable image fixture identity").hexdigest()
        tasks = [
            {"task_id": f"task-{i}", "terminal": terminal, "input_sha256": digest,
             "release_offset_ns": i * 100_000_000, "deadline_ns": 800_000_000,
             "fallback_ns": 550_000_000}
            for i, terminal in enumerate(terminals)
        ]
        return {"pair_id": "dev-pair", "terminals": max(terminals) + 1, "tasks": tasks}

    def log(self, event, **fields):
        self.events.append((event, fields))

    def test_distinct_terminal_lanes_share_only_physical_capacity(self):
        pair = self.pair([0, 1, 0])
        with C2Authorization(self.path / "c2", pair, None, self.log) as bridge:
            self.assertIsNone(bridge.committed("task-0"))
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(bridge.negotiate, pair["tasks"][:2]))
            results.append(bridge.negotiate(pair["tasks"][2]))
            self.assertTrue(all(result["status"] == "COMMITTED" for result in results))
            proofs = [bridge.committed(task["task_id"]) for task in pair["tasks"]]
            self.assertTrue(all(proof is not None for proof in proofs))
            self.assertEqual([proof["c2_terminal"] for proof in proofs], [0, 1, 0])
            self.assertEqual(len({proof["c2_commit_effect_tx"] for proof in proofs}), 3)
            self.assertEqual(len({proof["c2_intent_id"] for proof in proofs}), 3)
            self.assertEqual(bridge.committed("task-0"), proofs[0])
            with self.assertRaises(ValueError):
                bridge.negotiate({**pair["tasks"][0], "fallback_ns": 0})
        self.assertEqual(
            sorted(fields["logical_ticket_count"] for name, fields in self.events if name == "C2_LANE_READY"),
            [1, 2],
        )

    def test_reply_loss_keeps_durable_authorization_distinct(self):
        pair = self.pair([0])
        with C2Authorization(self.path / "c2", pair, CommitReplyLoss(), self.log) as bridge:
            terminal = bridge.negotiate(pair["tasks"][0])
            self.assertEqual(terminal["status"], "RECOVERY_REQUIRED")
            self.assertEqual(terminal["effectKnowledge"], "UNKNOWN")
            self.assertIsNotNone(bridge.committed("task-0"))
        drops = [fields for name, fields in self.events if name == "C2_RELAY_DROP"]
        self.assertTrue(drops and all(row["direction"] == "downlink" for row in drops))
        self.assertEqual({row["phase"] for row in drops}, {"COMMIT_INITIAL"})


if __name__ == "__main__":
    unittest.main()

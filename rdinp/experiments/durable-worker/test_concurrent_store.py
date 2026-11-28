"""Targeted G1-A regressions for durable capacity and fenced recovery."""

import base64
from contextlib import closing
import hashlib
import io
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import time
import unittest

from PIL import Image

from concurrent_store import ConcurrentStore

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service-worker"))
from run_study import compute_edge


def until(call, statuses, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        answer = call()
        if answer["status"] in statuses:
            return answer
        time.sleep(0.012)
    raise AssertionError(f"did not reach {statuses}, last answer {answer['status']}")


class ConcurrentStoreTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "tasks.sqlite"
        with io.BytesIO() as out:
            Image.new("RGB", (640, 480), (140, 30, 60)).save(out, format="PNG")
            self.payload = out.getvalue()
        release = time.monotonic_ns()
        self.tasks = {
            task_id: {
                "input_sha256": hashlib.sha256(self.payload).hexdigest(),
                "release_ns": release, "fallback_ns": release + 8_000_000_000,
                "deadline_ns": release + 10_000_000_000,
            } for task_id in ("a", "b", "c")
        }
        self.events = []

    def emit(self, event, **fields):
        if event == "APP_RELEASE":
            # A separate reader must see the released slot at publication time.
            with closing(sqlite3.connect(self.db)) as reader:
                slot, = reader.execute("SELECT slot FROM tasks WHERE task_id=?",
                                       (fields["task_id"],)).fetchone()
            if slot is not None or fields["release_ns"] > time.monotonic_ns():
                raise AssertionError("release was emitted without visible committed capacity")
        self.events.append((event, fields))

    def store(self, slots=1, lease=5_000_000_000):
        store = ConcurrentStore(self.db, self.tasks, slots, lease, self.emit)
        self.addCleanup(store.close)
        return store

    def test_unused_lease_regrant_has_new_epoch_and_rejects_stale_token(self):
        store = self.store(slots=2, lease=250_000_000)
        first = store.grant("a")
        second = store.grant("b")
        self.assertEqual((first["slot"], second["slot"]), (0, 1))
        self.assertEqual(store.grant("c")["status"], "BUSY")
        until(lambda: store.status("a"), {"ARMED"})
        third = store.grant("a")
        self.assertGreater(third["epoch"], second["epoch"])
        self.assertNotEqual(third["token"], first["token"])
        self.assertEqual(store.execute("a", first["token"], self.payload)["status"], "INVALID_TOKEN")
        self.assertEqual(store.cancel("a", first["token"])["status"], "INVALID_TOKEN")

    def test_durable_result_replays_after_lost_reply_and_reopen(self):
        store = self.store()
        self.assertEqual(store.status("a")["status"], "ARMED")
        grant = store.grant("a")
        reply = store.execute("a", grant["token"], self.payload)
        self.assertEqual(reply["status"], "IN_PROGRESS")
        recovered = until(lambda: store.status("a"), {"RESULT", "COMPUTE_FAILED"})
        self.assertEqual(recovered["status"], "RESULT")
        self.assertEqual(base64.b64decode(recovered["result_b64"]), compute_edge(self.payload))
        self.assertEqual(store.execute("a", grant["token"], self.payload), recovered)
        store.close()
        reopened = self.store()
        self.assertEqual(reopened.status("a"), recovered)
        self.assertEqual(reopened.cancel("a"), recovered)
        self.assertEqual(reopened.grant("b")["status"], "GRANTED")
        self.assertEqual(len([e for e, _ in self.events if e == "APP_START"]), 1)

    def test_cancel_fences_before_grant_and_awaits_active_process_exit(self):
        store = self.store()
        self.assertEqual(store.cancel("c")["status"], "CANCELLED")
        self.assertEqual(store.grant("c")["status"], "CANCELLED")
        first = store.grant("a")
        self.assertEqual(store.execute("a", first["token"], self.payload)["status"], "IN_PROGRESS")
        self.assertEqual(store.cancel("a", first["token"])["status"], "CANCELLING")
        until(lambda: store.status("a"), {"CANCELLED"})
        second = store.grant("b")
        self.assertEqual(second["status"], "GRANTED")
        self.assertEqual(second["slot"], first["slot"])
        confirmed, = [f for e, f in self.events if e == "APP_WORKER_EXIT_CONFIRMED" and f["task_id"] == "a"]
        released, = [f for e, f in self.events if e == "APP_RELEASE" and f["task_id"] == "a"]
        self.assertLessEqual(confirmed["confirmed_ns"], released["release_ns"])
        self.assertLessEqual(released["release_ns"], [
            f["decision_ns"] for e, f in self.events if e == "APP_GRANT" and f["task_id"] == "b"
        ][0])


if __name__ == "__main__":
    unittest.main()

"""The terminal must start local fallback while the remote RPC remains blocked."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
from unittest.mock import patch

from run_concurrent import run_task, sha256


class FallbackTimerTest(unittest.TestCase):
    def test_stalled_remote_never_owns_the_fallback_timer(self):
        network_started = threading.Event()
        let_remote_return = threading.Event()
        local = b"local output"
        events = []

        def stalled_rpc(*_):
            network_started.set()
            if not let_remote_return.wait(timeout=3):
                raise AssertionError("test failed to release the stalled RPC")
            return sha256(b"remote output")

        task = {
            "task_id": "one",
            "pair_id": "pair",
            "terminal": 0,
            "release_offset_ns": 0,
            "fallback_ns": 100_000_000,
            "deadline_ns": 900_000_000,
            "input_sha256": sha256(b"input"),
            "expected_output_sha256": {"local": sha256(local), "edge": sha256(b"remote output")},
        }
        remote, cancel = [], []
        with (ThreadPoolExecutor(1) as network,
              ThreadPoolExecutor(1) as cancellation,
              patch("run_concurrent.seek_edge", side_effect=stalled_rpc),
              patch("run_concurrent.compute_local", return_value=local),
              patch("run_concurrent.cancel_on_wire", return_value=None)):
            try:
                row = run_task(
                    task, time.monotonic_ns(), "B1", b"input", "", "local",
                    lambda event, **_fields: events.append(event),
                    threading.Lock(), None, None, cancellation, cancel,
                    None, None, [], network, remote,
                )
                self.assertTrue(network_started.is_set())
                self.assertFalse(remote[0].done())
                self.assertEqual(row["source"], "local")
                self.assertGreaterEqual(row["fallback_started_ns"], row["fallback_ns"])
                self.assertEqual(events.count("ADOPT"), 1)
            finally:
                let_remote_return.set()
            remote[0].result(timeout=2)
        self.assertEqual(events.count("ADOPT"), 1)


if __name__ == "__main__":
    unittest.main()

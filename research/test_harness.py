"""Regression checks for cross-platform locks, immutable publication and recovery."""

from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic, sleep
import unittest
from unittest.mock import patch

import harness


class ResearchHarnessTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="paper1-harness-test-")
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name).resolve()
        self.directory = self.state / "opv2v-evidence"

    def worker(self, code, *args):
        return [sys.executable, "-B", "-E", "-c", code, *map(str, args)]

    def test_publication_does_not_replace_existing_file(self):
        path = self.state / "receipt.json"
        harness.publish(path, b"original")
        with self.assertRaises(FileExistsError):
            harness.publish(path, b"replacement")
        self.assertEqual(path.read_bytes(), b"original")
        self.assertEqual(list(self.state.iterdir()), [path])

    def test_lock_refuses_a_second_process(self):
        ready = self.state / "ready"
        code = (
            "from pathlib import Path; import sys,time; import harness\n"
            "with harness.lock_task(Path(sys.argv[1])):\n"
            " Path(sys.argv[2]).touch()\n"
            " time.sleep(30)\n"
        )
        child = subprocess.Popen(self.worker(code, self.directory, ready), cwd=Path(harness.__file__).parent)
        try:
            deadline = monotonic() + 8
            while not ready.exists() and monotonic() < deadline and child.poll() is None:
                sleep(0.03)
            self.assertTrue(ready.exists(), "Child failed to acquire the lock")
            with self.assertRaisesRegex(harness.HarnessError, "task lock"):
                with harness.lock_task(self.directory):
                    self.fail("The child still holds the task lock")
        finally:
            child.kill()
            child.wait(timeout=8)
        with harness.lock_task(self.directory):
            self.assertTrue((self.directory / ".lock").is_file())

    def test_abrupt_worker_exit_is_recorded_under_lock(self):
        attempt = self.directory / "123-0123456789ab"
        code = (
            "from pathlib import Path; import os,sys; import harness\n"
            "a = Path(sys.argv[1]); inputs = {'files': {}}\n"
            "with harness.lock_task(a.parent):\n"
            " a.mkdir()\n"
            " harness.publish_json(a/'reservation.json', dict(schema=1, task=a.parent.name, "
            "attempt=a.name, inputs=inputs, input_sha256=harness.json_digest(inputs)))\n"
            " os._exit(81)\n"
        )
        child = subprocess.run(self.worker(code, attempt), cwd=Path(harness.__file__).parent, check=False)
        self.assertEqual(child.returncode, 81)
        self.assertFalse((attempt / "receipt.json").exists())
        with harness.lock_task(self.directory):
            self.assertEqual(harness.recover(self.directory), 1)
            self.assertEqual(harness.recover(self.directory), 0)
        self.assertEqual(harness.verify(attempt)[1]["status"], "interrupted")

    def test_reuse_new_input_and_tamper_rejection(self):
        task = harness.TASKS[self.directory.name]
        old = {"files": {"input": "first"}}
        new = {"files": {"input": "second"}}
        completed = subprocess.CompletedProcess([], 0, stdout=b"fixture check passed\n")
        with patch.object(harness, "execute", return_value=completed) as execute:
            with patch.object(harness, "snapshot", return_value=old):
                self.assertEqual(harness.run_task(self.directory, task), 0)
                self.assertEqual(harness.run_task(self.directory, task), 0)
                self.assertEqual(execute.call_count, 1)
            with patch.object(harness, "snapshot", return_value=new):
                self.assertEqual(harness.run_task(self.directory, task), 0)
                self.assertEqual(execute.call_count, 2)
                latest, older = harness.attempts(self.directory)
                self.assertEqual(harness.verify(older)[1]["status"], "passed")
                (latest / "output.log").write_bytes(b"changed")
                with self.assertRaisesRegex(harness.HarnessError, "artifact mismatch"):
                    harness.run_task(self.directory, task)
                self.assertEqual(execute.call_count, 2)

    def test_change_during_run_marks_failed(self):
        task = harness.TASKS[self.directory.name]
        completed = subprocess.CompletedProcess([], 0, stdout=b"fixture check passed\n")
        with patch.object(harness, "execute", return_value=completed):
            with patch.object(harness, "snapshot", side_effect=[{"first": 1}, {"second": 2}]):
                self.assertEqual(harness.run_task(self.directory, task), 1)
        attempt, = harness.attempts(self.directory)
        self.assertEqual(harness.verify(attempt)[1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()

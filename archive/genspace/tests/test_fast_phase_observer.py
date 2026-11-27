"""FAST phase observer regression using an already serialized engineering input.

Does not derive any seed or generate an instance. Run after the engineering
snapshot is rebuilt against the frozen source tree.
"""
import json
import unittest
from pathlib import Path

from src.fast_exact import FastLibrary
from src.fast_runner import run_paired_fast

ROOT = Path(__file__).resolve().parents[1]


class FastPhaseObserverTests(unittest.TestCase):
    def test_real_input_observer_preserves_non_timing_outputs(self):
        path = ROOT / 'results/memory_recovery_engineering/instances/00.json'
        self.assertTrue(path.is_file(), 'missing preserved engineering fixture')
        serialized = path.read_text(encoding='utf8')
        self.assertEqual(json.loads(serialized)['namespace'], 'GENSPACE-FAIL-01-ENGINEERING')
        lib = FastLibrary.from_graph(scope='engineering')
        baseline, _ = run_paired_fast(serialized, lib)
        events = []
        observed, _ = run_paired_fast(serialized, lib, phase_observer=events.append)
        def scientific(rows):
            return [{k: v for k, v in row.items() if k != 'runtime_seconds'} for row in rows]
        self.assertEqual(scientific(baseline), scientific(observed))
        self.assertEqual(events, [
            'INSTANCE_START', 'PUBLIC_FILTER_START', 'PUBLIC_FILTER_END',
            'V4_START', 'V4_END', 'V5_START', 'V5_END',
            'REPRESENTATIVE_SELECTED', 'SERIALIZATION_START',
            'SERIALIZATION_END', 'FAST_EVALUATION_COMPLETE'])

    def test_exception_propagates_fail_closed(self):
        path = ROOT / 'results/memory_recovery_engineering/instances/00.json'
        serialized = path.read_text(encoding='utf8')
        def reject(event):
            raise RuntimeError('observer failure')
        # INSTANCE_START occurs before the library is accessed.
        with self.assertRaisesRegex(RuntimeError, 'observer failure'):
            run_paired_fast(serialized, object(), phase_observer=reject)


if __name__ == '__main__':
    unittest.main()

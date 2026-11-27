import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.phase_memory import EMERGENCY_FLOOR, PhaseMemoryObserver


class PhaseMemoryTests(unittest.TestCase):
    def test_records_then_stops_on_emergency(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'events.jsonl'
            data = {'event': 'V4_START', 'system_available_physical': EMERGENCY_FLOOR - 1}
            observer = PhaseMemoryObserver(path, 1, 'engineering_fixture')
            with patch('src.phase_memory.memory_event', return_value=data):
                with self.assertRaises(MemoryError):
                    observer('V4_START')
            saved = json.loads(path.read_text(encoding='utf8'))
            self.assertEqual(saved['instance_id'], 'engineering_fixture')
            self.assertEqual(saved['event'], 'V4_START')

    def test_floor_never_lowered(self):
        with self.assertRaises(ValueError):
            PhaseMemoryObserver('unused', 1, 'id', floor=EMERGENCY_FLOOR - 1)

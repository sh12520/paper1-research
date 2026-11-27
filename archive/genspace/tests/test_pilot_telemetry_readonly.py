import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.phase_memory import ReadOnlyTelemetry


class ReadOnlyTelemetryTests(unittest.TestCase):
    def test_namespace_scope_and_off_switch(self):
        from src.phase_memory import telemetry_enabled
        for ns in ('GENSPACE-FAIL-01-ENGINEERING-SHADOW','GENSPACE-FAIL-01-CONFIRM'):
            self.assertTrue(telemetry_enabled(ns,{}))
            self.assertFalse(telemetry_enabled(ns,{'GENSPACE_TELEMETRY':'off'}))
        self.assertTrue(telemetry_enabled('GENSPACE-FAIL-01-PILOT',{}))
        self.assertTrue(telemetry_enabled('GENSPACE-FAIL-01-PILOT',{'GENSPACE_TELEMETRY':'off'}))
        for ns in ('GENSPACE-FAIL-01-ENGINEERING','GENSPACE-FAIL-01-SMOKE','unknown'):
            self.assertFalse(telemetry_enabled(ns,{}))
            self.assertFalse(telemetry_enabled(ns,{'GENSPACE_TELEMETRY':'on'}))

    def test_records_identity_memory_and_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'events.jsonl'
            def info(pid): return ({'pid':pid,'creation_time':123}, 1234, 2345)
            with patch('src.phase_memory.process_info',side_effect=info), patch('src.phase_memory.system_memory',return_value=(12345,67890)):
                sink=ReadOnlyTelemetry(path,10,'a'*64,['i1'])
                sink.emit('INSTANCE_START','i1',worker_pid=11)
            event=json.loads(path.read_text())
            self.assertEqual(event['event'],'INSTANCE_START')
            self.assertEqual(event['instance_id'],'i1')
            self.assertEqual(event['process_identity']['pid'],11)
            self.assertEqual(event['orchestrator_identity']['pid'],10)
            self.assertEqual(event['worker_peak_rss'],2345)
            self.assertEqual(event['system_available_physical'],67890)
            self.assertEqual(event['execution_snapshot_hash'],'a'*64)

    def test_sampling_failure_never_propagates(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'events.jsonl'
            with patch('src.phase_memory.memory_event',side_effect=OSError('synthetic failure')):
                ReadOnlyTelemetry(path,10,'b'*64,['i1']).emit('V4_START','i1')
            event=json.loads(path.read_text())
            self.assertEqual(event['event'],'TELEMETRY_ERROR')
            self.assertEqual(event['failed_event'],'V4_START')

    def test_launcher_observations_are_nonblocking(self):
        from src.windows_suspended_job import launch
        names=[]
        def observe(name,pid,metadata):
            names.append(name)
            raise OSError('observational failure')
        child=launch([sys.executable,'-c','pass'],lifecycle_observer=observe)
        result=child.finish(lifecycle_observer=observe)
        self.assertTrue(result['pass'])
        self.assertEqual(names,['JOB_ASSIGNMENT','JOB_COMPLETE'])


if __name__=='__main__':unittest.main()

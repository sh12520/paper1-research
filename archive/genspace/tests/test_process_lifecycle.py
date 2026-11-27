import subprocess
import sys
import time
import unittest
import os
from unittest.mock import patch
from src.process_lifecycle import identity, classify, LifecycleTracker, prelaunch_guard, emergency_guard, PRELAUNCH_FLOOR, EMERGENCY_FLOOR
from src.process_lifecycle import create_job, join_job, job_active, close_job

class LifecycleTests(unittest.TestCase):
    def test_classification_absent_reused_original(self):
        original={'pid':42,'creation_time':7}
        for current, status, expected in ((None,'ABSENT',True),({'pid':42,'creation_time':8},'PID_REUSED',True),(original,'ORIGINAL_PROCESS_OBJECT_STILL_ACCESSIBLE',False)):
            with self.subTest(status=status), patch('src.process_lifecycle.identity',return_value=current):
                result=classify(original)
                self.assertEqual((result['status'],result['pass']),(status,expected))

    def test_guards(self):
        self.assertTrue(prelaunch_guard(lambda:{'available':PRELAUNCH_FLOOR},interval=0)['pass'])
        self.assertFalse(prelaunch_guard(lambda:{'available':PRELAUNCH_FLOOR-1},interval=0)['pass'])
        self.assertTrue(emergency_guard(lambda:{'available':EMERGENCY_FLOOR})['pass'])
        self.assertFalse(emergency_guard(lambda:{'available':EMERGENCY_FLOOR-1})['pass'])

    def test_real_process_identity_after_exit(self):
        proc=subprocess.Popen([sys.executable,'-c','import time;time.sleep(0.5)'])
        tracker=LifecycleTracker(proc)
        self.assertEqual(identity(proc.pid),tracker.original)
        proc.wait()
        result=tracker.finish(timeout=5)
        self.assertEqual(result['returncode'],0)
        self.assertTrue(result['root']['pass'],result)
        self.assertEqual(result['descendants'],[])

    def test_job_tracks_surviving_descendant(self):
        h,name=create_job()
        try:
            env={**os.environ,'GENSPACE_JOB':name}
            code=('import os,subprocess,sys;from src.process_lifecycle import join_job;'
                  'join_job(os.environ["GENSPACE_JOB"]);'
                  'subprocess.Popen([sys.executable,"-c","import time;time.sleep(1.5)"])')
            p=subprocess.Popen([sys.executable,'-c',code],env=env)
            self.assertEqual(p.wait(),0)
            self.assertGreaterEqual(job_active(h)['active_processes'],1)
            deadline=time.monotonic()+5
            while job_active(h)['active_processes'] and time.monotonic()<deadline:time.sleep(.1)
            self.assertEqual(job_active(h)['active_processes'],0)
        finally:close_job(h)

if __name__ == '__main__': unittest.main()

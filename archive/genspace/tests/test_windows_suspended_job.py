import os,sys,tempfile,time,unittest,ctypes
from pathlib import Path
from unittest.mock import patch
from src import windows_suspended_job as sj
from src.process_lifecycle import K,job_active

class SuspendedJobTests(unittest.TestCase):
    def test_running_classification(self):
        p=sj.launch([sys.executable,'-c','import time; time.sleep(5)'])
        try:self.assertEqual(p.status(),'RUNNING')
        finally:p.terminate();p.finish(expected_exit=1)
    def test_short_tasks_assigned_before_resume(self):
        for _ in range(3):
            p=sj.launch([sys.executable,'-c','pass'])
            r=p.finish();self.assertTrue(r['pass'],r)
            self.assertTrue(r['assignment_before_resume']);self.assertEqual(r['resume_result'],1)
            self.assertEqual(r['job_accounting']['active_processes'],0)
            self.assertTrue(r['job_limit_flags'] & sj.KILL);self.assertFalse(r['job_limit_flags'] & sj.BREAKAWAY)
            self.assertIn(r['classification'],('TERMINATED_OBJECT_QUERYABLE','PID_REUSED','ABSENT'))

    def test_assignment_failure_does_not_run_python(self):
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'must_not_exist'
            with patch.object(K,'AssignProcessToJobObject',return_value=0):
                with self.assertRaises(OSError):sj.launch([sys.executable,'-c',f'open({str(marker)!r},"w").write("executed")'])
            time.sleep(.1);self.assertFalse(marker.exists())

    def test_last_job_handle_kills_process_tree(self):
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'pid.txt'
            program=('import subprocess,sys,time;'
                     'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
                     f'open({str(marker)!r},"w").write(str(p.pid));time.sleep(30)')
            p=sj.launch([sys.executable,'-c',program]);deadline=time.monotonic()+10
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(marker.exists(),'worker did not launch descendant')
            pid=int(marker.read_text());h=K.OpenProcess(0x100000|0x1000,False,pid)
            self.assertTrue(h);self.assertGreaterEqual(job_active(p.job_handle)['active_processes'],2)
            p.close() # last job handle closes with KILL_ON_JOB_CLOSE
            try:self.assertEqual(K.WaitForSingleObject(h,5000),0,'descendant survived job close')
            finally:K.CloseHandle(h)

if __name__=='__main__':unittest.main()

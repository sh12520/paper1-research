"""Independent normal/resume/tamper check using one existing PILOT instance."""
import json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CASE=ROOT/'results/method_dev_v1'/('audit_resume_case_'+str(os.getpid()))

class ResumeIntegrityTests(unittest.TestCase):
    def test_normal_resume_and_tamper_fail_closed(self):
        if CASE.exists():raise RuntimeError('audit case must be new')
        env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
        command=[sys.executable,str(ROOT/'results/method_dev_v1/harness.py'),'--limit','1','--methods','B2','--output',str(CASE.relative_to(ROOT))]
        def invoke():return subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
        first=invoke();self.assertEqual(first.returncode,0,first.stderr[-1500:])
        iid=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances'][0]['instance_id']
        path=CASE/iid/'record.json'; original=path.read_bytes()
        second=invoke();self.assertEqual(second.returncode,0,second.stderr[-1500:])
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(json.loads((CASE/'_guard.json').read_text())['validated_skips'],1)
        try:
            path.write_bytes(original+b' ')
            bad=invoke();self.assertNotEqual(bad.returncode,0)
            self.assertIn('invalid or incompatible completed record',bad.stderr)
        finally:path.write_bytes(original)
        manifest=CASE/'run_manifest.json'; original_manifest=manifest.read_bytes()
        try:
            state=json.loads(original_manifest);state['config_sha256']='0'*64
            manifest.write_text(json.dumps(state),encoding='utf8')
            bad=invoke();self.assertNotEqual(bad.returncode,0)
            self.assertIn('resume source/config/plan mismatch',bad.stderr)
        finally:manifest.write_bytes(original_manifest)

if __name__=='__main__':unittest.main()

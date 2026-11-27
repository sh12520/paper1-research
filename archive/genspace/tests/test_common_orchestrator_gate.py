import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile,json
from src.experiment_orchestrator import run_experiment

class CommonGateTests(unittest.TestCase):
    def test_smoke_denied_before_plan_or_generation(self):
        class Poison:
            def __eq__(self, other):raise AssertionError('plan accessed before authorization')
        with patch('src.smoke_authorization.authorize',side_effect=PermissionError('AUTHORIZATION_DENIED')) as auth, \
             patch('src.instances.generate_instance') as generate, patch('src.instances.derive_seed') as derive:
            with self.assertRaises(PermissionError):
                run_experiment(Poison(),'GENSPACE-FAIL-01-SMOKE','formal-snapshot','authorization',output_root='unused')
        auth.assert_called_once()
        generate.assert_not_called();derive.assert_not_called()

    def test_recorded_memory_pause_and_explained_job(self):
        import src.experiment_orchestrator as mod
        with tempfile.TemporaryDirectory() as td, patch.object(mod,'OUT',Path(td)):
            state={'phase':'AUDIT_ARTIFACTS'};segment={'jobs':[]}
            mod.record_memory_pause(state,segment,Path(td)/'segment.json','AUDIT_ARTIFACTS')
            self.assertEqual(json.loads((Path(td)/'state.json').read_text())['resume_phase'],'AUDIT_ARTIFACTS')
            self.assertEqual(json.loads((Path(td)/'segment.json').read_text())['status'],'PAUSED_MEMORY')
        self.assertTrue(mod.explained_job({'status':'PAUSED_MEMORY','guard':{'pass':False}}))
        self.assertTrue(mod.explained_job({'status':'PAUSED_MEMORY','guard':{'pass':True},'samples':[{'available':1}],
                           'lifecycle':{'assignment_verified':True,'job_accounting':{'active_processes':0},'job_limit_flags':8192}}))
        self.assertFalse(mod.explained_job({'status':'PAUSED_MEMORY','guard':{'pass':True},'samples':[{'available':1}],
                            'lifecycle':{'assignment_verified':True,'job_accounting':{'active_processes':1},'job_limit_flags':8192}}))
        self.assertFalse(mod.explained_job({'status':'ERROR'}))

    def test_formal_base_plan_accepts_derived_subsets_and_context(self):
        import src.experiment_orchestrator as mod
        base={'namespace':'GENSPACE-FAIL-01-SMOKE','instances':[]}
        enriched={**base,'audit4':[],'rerun8':[],'fresh_repeat16':[]}
        with tempfile.TemporaryDirectory() as td, \
             patch('src.smoke_authorization.authorize',return_value={'snapshot_sha256':'a'*64}) as auth, \
             patch.object(mod,'getplan',return_value=enriched), patch.object(mod,'run',return_value=True) as run, \
             patch.multiple(mod,OUT=mod.OUT,NAMESPACE=mod.NAMESPACE,SCOPE=mod.SCOPE,
                            SNAPSHOT_CONTEXT=mod.SNAPSHOT_CONTEXT,AUTH_CONTEXT=mod.AUTH_CONTEXT):
            snap=Path(td)/'formal.json';policy=Path(td)/'auth.json'
            self.assertTrue(run_experiment(base,'GENSPACE-FAIL-01-SMOKE',snap,policy,output_root=td))
            self.assertEqual(mod.SNAPSHOT_CONTEXT,str(snap.resolve()))
            self.assertEqual(mod.AUTH_CONTEXT,str(policy.resolve()))
            run.assert_called_once()
            self.assertGreaterEqual(auth.call_count,2)

if __name__=='__main__':unittest.main()

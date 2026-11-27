"""Namespace-only and schema fingerprint tests without experimental seeds."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src.fast_runner import run_paired_fast
from src.fast_exact import FastEvaluator
from src import fingerprints
from src.smoke_authorization import verify_authorization,expected_state

class RoutingTests(unittest.TestCase):
    def test_namespace_is_in_instance_identity_and_hash(self):
        from src.instances import Instance
        shadow=Instance('GENSPACE-FAIL-01-ENGINEERING-SHADOW','0',None,None)
        engineering=Instance('GENSPACE-FAIL-01-ENGINEERING','0',None,None)
        self.assertNotEqual(shadow.serialize(),engineering.serialize())
        self.assertNotEqual(shadow.instance_hash,engineering.instance_hash)

    def test_forbidden_routes_fail_before_deserialization(self):
        with patch('src.smoke_authorization.authorize',side_effect=PermissionError('AUTHORIZATION_DENIED')):
            with self.assertRaises(PermissionError):run_paired_fast(json.dumps({'namespace':'GENSPACE-FAIL-01-SMOKE'}),None)
            with self.assertRaises(PermissionError):FastEvaluator(SimpleNamespace(namespace='GENSPACE-FAIL-01-SMOKE'),None)
        for namespace in ('GENSPACE-FAIL-01-PILOT','GENSPACE-FAIL-01-CONFIRM'):
            with self.assertRaises(RuntimeError):run_paired_fast(json.dumps({'namespace':namespace}),None)
            with self.assertRaises(RuntimeError):FastEvaluator(SimpleNamespace(namespace=namespace),None)

    def test_shadow_scope_reaches_public_verifier(self):
        instance=SimpleNamespace(namespace='GENSPACE-FAIL-01-ENGINEERING-SHADOW',public=object())
        library=SimpleNamespace(snapshot={'execution_scope':'shadow'})
        with patch('src.execution_snapshot.verify_public_instance',side_effect=ValueError('public reached')):
            with self.assertRaisesRegex(ValueError,'public reached'):FastEvaluator(instance,library)
        with self.assertRaises(RuntimeError):FastEvaluator(instance,SimpleNamespace(snapshot={'execution_scope':'engineering'}))

    def test_authorization_requires_correct_snapshot_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=Path(tmp)/'s.json'; auth=Path(tmp)/'a.json';snapshot.write_text('{}')
            formal=Path(tmp)/'f.json';formal.write_text('{}')
            auth.write_text(json.dumps(expected_state(snapshot,formal)))
            with patch('src.smoke_authorization.verify_snapshot'):
                snapshot.write_text('{"execution_scope":"shadow"}')
                auth.write_text(json.dumps(expected_state(snapshot,formal)))
                self.assertEqual(verify_authorization(auth,snapshot)['namespace'],'GENSPACE-FAIL-01-ENGINEERING-SHADOW')
                bad=expected_state(snapshot,formal);bad['namespace_authorizations']['PILOT']['allowed']=True;auth.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):verify_authorization(auth,snapshot)
                auth.write_text(json.dumps(expected_state(snapshot,formal)));snapshot.write_text('{"execution_scope":"shadow", "changed":true}')
                with self.assertRaises(ValueError):verify_authorization(auth,snapshot)

    def test_schema_bytes_bind_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'schemas').mkdir();(root/'schemas'/'x.json').write_text('1')
            (root/'SMOKE02_PLAN_TEMPLATE.json').write_text('{}')
            (root/'config.yaml').write_text('{}')
            from src.execution_snapshot import source_tree_hash
            before=source_tree_hash('fixture-source',root)
            (root/'schemas'/'x.json').write_text('2')
            after=source_tree_hash('fixture-source',root)
            self.assertNotEqual(before,after)
    def test_formal_plan_bytes_bind_source_hash(self):
        from src.execution_snapshot import source_tree_hash
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'schemas').mkdir();plan=root/'SMOKE02_PLAN_TEMPLATE.json';plan.write_text('1')
            before=source_tree_hash('source',root);plan.write_text('2')
            self.assertNotEqual(before,source_tree_hash('source',root))

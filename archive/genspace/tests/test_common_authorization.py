"""Seed-free authorization tests; no experiment instance is generated."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from src import smoke_authorization as a

class CommonAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name)
        self.shadow=p/'shadow.json';self.formal=p/'formal.json';self.auth=p/'authorization.json'
        self.shadow.write_text(json.dumps({'execution_scope':'shadow'}))
        self.formal.write_text(json.dumps({'execution_scope':'smoke02'}))
        self.auth.write_text(json.dumps(a.expected_state(self.shadow,self.formal)))
        self.verify=patch('src.smoke_authorization.verify_snapshot',return_value={});self.verify.start()
    def tearDown(self):self.verify.stop();self.tmp.cleanup()
    def test_shadow_allowed_formal_snapshot_mismatch(self):
        self.assertEqual(a.authorize(a.SHADOW,self.shadow,self.auth)['namespace'],a.SHADOW)
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):a.authorize(a.SHADOW,self.formal,self.auth)
    def test_smoke_false_denied_and_wrong_scope_mismatch_first(self):
        with self.assertRaisesRegex(PermissionError,'AUTHORIZATION_DENIED'):a.authorize(a.SMOKE,self.formal,self.auth)
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):a.authorize(a.SMOKE,self.shadow,self.auth)
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):a.authorize(a.PILOT,self.formal,self.auth)
        for n in (a.CONFIRM,'unknown'):
            with self.assertRaises(PermissionError):a.authorize(n,self.formal,self.auth)
    def test_snapshot_tamper_and_policy_tamper(self):
        self.shadow.write_text('{"execution_scope":"shadow", "changed":true}')
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_MISMATCH'):a.authorize(a.SHADOW,self.shadow,self.auth)
        self.auth.write_text(json.dumps(a.expected_state(self.shadow,self.formal)))
        x=json.loads(self.auth.read_text());x['namespace_authorizations']['PILOT']['allowed']=True
        self.auth.write_text(json.dumps(x))
        with self.assertRaises(ValueError):a.authorize(a.SHADOW,self.shadow,self.auth)

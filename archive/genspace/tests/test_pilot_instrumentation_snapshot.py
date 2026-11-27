"""Seed-free tests for locked pilot instrumentation preparation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src import pilot_instrumentation_snapshot as m


class PilotPreparationTests(unittest.TestCase):
    def test_preparation_scope_is_not_a_fast_execution_route(self):
        from src.execution_snapshot import EXECUTION_SCOPES
        from src.fast_exact import FastLibrary
        self.assertIn(m.PILOT_PREPARATION_SCOPE, EXECUTION_SCOPES)
        with self.assertRaises(ValueError):
            FastLibrary.from_graph(scope=m.PILOT_PREPARATION_SCOPE)

    def test_snapshot_binds_current_inputs_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); snapshot=root/'snapshot.json'; historical=root/'historical.json'
            original={key:'value-'+key for key in m.UNCHANGED_FIELDS}
            historical.write_text(json.dumps(original),encoding='utf8')
            actual={**original,'execution_scope':m.PILOT_PREPARATION_SCOPE}
            snapshot.write_text(json.dumps(actual),encoding='utf8')
            with patch.object(m,'build_preparation_snapshot',return_value=actual), \
                 patch.object(m,'compare_research_inputs',side_effect=lambda data: {
                     key:data.get(key)==original[key] for key in m.UNCHANGED_FIELDS}):
                self.assertEqual(m.verify_preparation_snapshot(snapshot),actual)
                modified=dict(actual); modified['config_sha256']='changed'
                snapshot.write_text(json.dumps(modified),encoding='utf8')
                with self.assertRaises(ValueError):m.verify_preparation_snapshot(snapshot)

    def test_locked_flags_and_snapshot_hash_are_exact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); snapshot=root/'snapshot.json'; auth=root/'authorization.json'
            snapshot.write_text('{}',encoding='utf8')
            with patch.object(m,'verify_preparation_snapshot',return_value={}):
                good=m.locked_authorization(snapshot)
                auth.write_text(json.dumps(good),encoding='utf8')
                self.assertEqual(m.verify_locked_authorization(auth,snapshot),good)
                bad=json.loads(json.dumps(good));bad['namespace_authorizations']['PILOT']['allowed']=True
                auth.write_text(json.dumps(bad),encoding='utf8')
                with self.assertRaises(ValueError):m.verify_locked_authorization(auth,snapshot)
                auth.write_text(json.dumps(good),encoding='utf8');snapshot.write_text('{ }',encoding='utf8')
                with self.assertRaises(ValueError):m.verify_locked_authorization(auth,snapshot)

    def test_never_overwrites_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'x.json';m._write_new(path,{'x':1})
            with self.assertRaises(FileExistsError):m._write_new(path,{'x':2})

if __name__=='__main__':unittest.main()

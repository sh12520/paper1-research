"""Synthetic namespace/snapshot scope tests: no experimental seeds are generated."""
import json
import hashlib
from types import SimpleNamespace
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from src.execution_snapshot import build_snapshot, verify_snapshot, availability_index_digests
from src.fast_exact import FastEvaluator
from src.fast_runner import run_paired_fast
from src.runner import run_paired
from src.instances import Instance, PublicInstance, PrivatePreferences

class SmokeScopeTests(unittest.TestCase):
    def test_smoke02_has_distinct_snapshot_scope(self):
        smoke02 = build_snapshot(scope='smoke02')
        self.assertNotEqual(smoke02, build_snapshot(scope='smoke'))
        with TemporaryDirectory() as td:
            file = Path(td) / 'snapshot.json'
            file.write_text(json.dumps(smoke02), encoding='utf8')
            self.assertEqual(verify_snapshot(path=file, scope='smoke02'), smoke02)
            with self.assertRaises(ValueError):
                verify_snapshot(path=file, scope='smoke')

    def test_snapshot_scopes_are_bound(self):
        engineering=build_snapshot(scope='engineering')
        smoke=build_snapshot(scope='smoke')
        self.assertNotEqual(engineering,smoke)
        with TemporaryDirectory() as td:
            file=Path(td)/'snapshot.json'
            file.write_text(json.dumps(smoke),encoding='utf8')
            self.assertEqual(verify_snapshot(path=file,scope='smoke'),smoke)
            with self.assertRaises(ValueError): verify_snapshot(path=file,scope='engineering')
            file.write_text(json.dumps(engineering),encoding='utf8')
            with self.assertRaises(ValueError): verify_snapshot(path=file,scope='smoke')

    def test_namespace_is_serialized_and_bound_to_instance_hash(self):
        # Pure synthetic data: no derived seed and no instance generator.
        public=PublicInstance(family='F1', configuration={}, horizon=3,
            states=('still','moving'), capacity=(), m0_profiles=(), mr_profiles=(),
            b2_profiles=(), capabilities=(), conditions=(), durations=(), offsets=(),
            intervals=(), offload_levels=(), public_constraints={}, resource_parameters={},
            registry={}, model_config_hash='synthetic')
        private=PrivatePreferences(application={},network={})
        engineering=Instance('GENSPACE-FAIL-01-ENGINEERING','synthetic',public,private)
        smoke=Instance('GENSPACE-FAIL-01-SMOKE','synthetic',public,private)
        self.assertEqual(engineering.public_hash,smoke.public_hash)
        self.assertEqual(engineering.private_hash,smoke.private_hash)
        self.assertNotEqual(engineering.instance_hash,smoke.instance_hash)
        self.assertEqual(json.loads(smoke.serialize())['namespace'],'GENSPACE-FAIL-01-SMOKE')

    def test_index_tampering_is_detected(self):
        with TemporaryDirectory() as td:
            root=Path(td); items=[]
            for pattern in [0,*range(16,32)]:
                payload=('index-%d'%pattern).encode()
                (root/f'availability_{pattern:02d}.bin.gz').write_bytes(payload)
                items.append({'pattern':pattern,'sha256':hashlib.sha256(payload).hexdigest(),
                              'class_set_mismatches':0})
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'format':'GENSPACE-AVAILABILITY-MANIFEST-v1',
                                            'patterns':items}),encoding='utf8')
            with patch('src.execution_snapshot.AVAILABILITY_MANIFEST',manifest):
                self.assertEqual(len(availability_index_digests()),17)
                (root/'availability_00.bin.gz').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'index mismatch'):
                    availability_index_digests()

    def test_disabled_namespaces_fail_before_public_access(self):
        for namespace in ('GENSPACE-FAIL-01-PILOT','GENSPACE-FAIL-01-CONFIRM','invalid'):
            with self.subTest(namespace=namespace):
                with self.assertRaisesRegex(RuntimeError,'namespace not enabled'):
                    FastEvaluator(SimpleNamespace(namespace=namespace),None)
                with self.assertRaisesRegex(RuntimeError,'namespace not enabled'):
                    run_paired_fast(json.dumps({'namespace':namespace}),None)
                with self.assertRaisesRegex(RuntimeError,'namespace not enabled'):
                    run_paired(json.dumps({'namespace':namespace}))

    def test_smoke_dispatch_requires_fast_library(self):
        with self.assertRaisesRegex(RuntimeError,'snapshot-verified FAST'):
            run_paired(json.dumps({'namespace':'GENSPACE-FAIL-01-SMOKE'}))

    def test_scope_mismatch_fails_before_public_access(self):
        for namespace,scope in (('GENSPACE-FAIL-01-SMOKE','engineering'),
                                ('GENSPACE-FAIL-01-ENGINEERING','smoke')):
            with self.subTest(namespace=namespace), self.assertRaisesRegex(RuntimeError,'scope differ'):
                FastEvaluator(SimpleNamespace(namespace=namespace),SimpleNamespace(snapshot={'execution_scope':scope}))

    def test_smoke_scope_reaches_public_validation(self):
        instance=SimpleNamespace(namespace='GENSPACE-FAIL-01-SMOKE',public=object())
        library=SimpleNamespace(snapshot={'execution_scope':'smoke'})
        with patch('src.execution_snapshot.verify_public_instance',side_effect=ValueError('public validation reached')):
            with self.assertRaisesRegex(ValueError,'public validation reached'):
                FastEvaluator(instance,library)

if __name__=='__main__': unittest.main()

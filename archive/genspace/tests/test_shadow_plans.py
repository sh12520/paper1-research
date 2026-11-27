import copy
import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from src.shadow_plans import (SHADOW_NAMESPACE,SMOKE_NAMESPACE,shadow_plan,
    smoke_template,validate_plan,shadow_seed_token,generate_shadow)

class PlansTest(unittest.TestCase):
    def test_complete_deterministic_grids(self):
        a,b=smoke_template(),shadow_plan()
        self.assertTrue(validate_plan(a,'smoke'));self.assertTrue(validate_plan(b,'shadow'))
        self.assertEqual(len(a['instances']),192);self.assertEqual(len(b['instances']),16)
        existing=json.loads((Path(__file__).resolve().parent.parent/'SMOKE02_PLAN.json').read_text(encoding='utf8'))
        self.assertEqual(a['instances'],existing['instances'])
        self.assertEqual((len(b['audit4']),len(b['rerun8']),len(b['fresh_repeat16'])),(4,8,16))
        self.assertEqual(smoke_template(),a);self.assertEqual(shadow_plan(),b)
        for plan,kind in ((a,'smoke'),(b,'shadow')):
            bad=copy.deepcopy(plan);bad['instances'][-1]=bad['instances'][0]
            with self.assertRaises(ValueError):validate_plan(bad,kind)

    def test_shadow_factory_tag_and_namespace(self):
        slot=shadow_plan()['instances'][0]
        from src import instances
        before=instances.derive_seed
        def fake(family,configuration,seed,namespace=None):
            return namespace,derive_seed(namespace,family,configuration,seed)
        with patch.object(instances,'generate_instance',fake):
            ns,derived=generate_shadow(slot['family'],slot['configuration'],slot['seed_index'])
        self.assertEqual(ns,SHADOW_NAMESPACE)
        self.assertEqual(instances.derive_seed,before)
        self.assertEqual(derived,int(instances.digest({'namespace':SHADOW_NAMESPACE,'family':slot['family'],
             'configuration':slot['configuration'],'seed':'0'}),16))
        token=shadow_seed_token(slot['family'],slot['configuration'],0)
        self.assertEqual(token,shadow_seed_token(slot['family'],slot['configuration'],0))
        self.assertNotEqual(token,shadow_seed_token(slot['family'],slot['configuration'],1))

    def test_snapshot_is_explicitly_non_executable(self):
        from src.smoke_snapshot_draft import locked_draft
        fake={'semantic_library_format_version':'fixture','snapshot_version':2}
        with patch('src.smoke_snapshot_draft.build_snapshot',return_value=fake):
            data=locked_draft()
        self.assertIs(data['authorized_for_execution'],False)
        self.assertIn('orchestrator',data['integration_bindings'])
        self.assertEqual(data['schema_versions']['orchestrator_commit'],'UNIMPLEMENTED_PENDING_REVIEW')

if __name__=='__main__':unittest.main()

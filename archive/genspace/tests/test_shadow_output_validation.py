"""Seed-free failure checks for the shared per-instance schema gate."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from src.shadow_output_validation import validate, SHADOW_NAMESPACE

class ValidationTests(unittest.TestCase):
    def test_validates_via_common_rows_checker(self):
        instance=SimpleNamespace(namespace=SHADOW_NAMESPACE)
        item={'instance_id':'i','snapshot_hash':'a'*64,'snapshot_pre_verified':True,
              'snapshot_post_verified':True,'ok':True,'rows':[],
              'check':{'ok':True}}
        with patch('src.shadow_output_validation.check_rows',return_value={'ok':True}) as check:
            self.assertTrue(validate('i',instance,item))
            self.assertEqual(check.call_args.kwargs['namespace'],SHADOW_NAMESPACE)
        with patch('src.shadow_output_validation.check_rows',return_value={'ok':False,'checks':{'schema':False}}):
            with self.assertRaises(ValueError):validate('i',instance,item)

    def test_missing_snapshot_or_identity_is_rejected(self):
        item={'instance_id':'i','snapshot_hash':'a'*64,'snapshot_pre_verified':True,
              'snapshot_post_verified':True,'ok':True,'rows':[],'check':{'ok':True}}
        with self.assertRaises(ValueError):validate('i',SimpleNamespace(namespace='other'),item)
        item['snapshot_post_verified']=False
        with self.assertRaises(ValueError):validate('i',SimpleNamespace(namespace=SHADOW_NAMESPACE),item)

if __name__=='__main__':unittest.main()

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from src.smoke02_commit import commit_instance, inspect_complete, quarantine_incomplete, NAMESPACE

INSTANCE=b'{"synthetic":true}'
HASH='a'*64
SNAP='b'*64
IID='F1__test'
def validator(raw):
    if raw!=INSTANCE: raise ValueError('bad instance')
    return HASH,NAMESPACE
def snap(): return SNAP
def result():
    return {'instance_id':IID,'instance_hash':HASH,'namespace':NAMESPACE,
            'rows':[{'method':m,'instance_hash':HASH,'namespace':NAMESPACE} for m in ('B0','B1','B2','O1')]}

class CommitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_commit_and_resume(self):
        self.assertFalse(inspect_complete(self.root,IID,HASH,SNAP,snap,validator))
        commit_instance(self.root,IID,HASH,INSTANCE,result(),SNAP,snap,validator)
        self.assertTrue(inspect_complete(self.root,IID,HASH,SNAP,snap,validator))
        with self.assertRaises(FileExistsError):commit_instance(self.root,IID,HASH,INSTANCE,result(),SNAP,snap,validator)
    def test_snapshot_mismatch_fails_closed(self):
        commit_instance(self.root,IID,HASH,INSTANCE,result(),SNAP,snap,validator)
        with self.assertRaises(ValueError): inspect_complete(self.root,IID,HASH,SNAP,lambda:'c'*64,validator)
        with self.assertRaises(ValueError): inspect_complete(self.root,IID,HASH,'c'*64,snap,validator)
    def test_shadow_and_smoke_transactions_share_primitive_but_not_identity(self):
        shadow='GENSPACE-FAIL-01-ENGINEERING-SHADOW'
        out=result();out['namespace']=shadow
        for row in out['rows']:row['namespace']=shadow
        def shadow_validator(raw):
            if raw!=INSTANCE: raise ValueError('bad instance')
            return HASH,shadow
        commit_instance(self.root,IID,HASH,INSTANCE,out,SNAP,snap,shadow_validator,namespace=shadow)
        self.assertTrue(inspect_complete(self.root,IID,HASH,SNAP,snap,shadow_validator,namespace=shadow))
        with self.assertRaises(ValueError):inspect_complete(self.root,IID,HASH,SNAP,snap,shadow_validator,namespace=NAMESPACE)
    def test_tamper_or_incomplete_schema(self):
        bad=result();bad['rows'].pop()
        with self.assertRaises(ValueError):commit_instance(self.root,IID,HASH,INSTANCE,bad,SNAP,snap,validator)
        commit_instance(self.root,IID,HASH,INSTANCE,result(),SNAP,snap,validator)
        (self.root/IID/'result.json').write_text('{}',encoding='utf8')
        with self.assertRaises(ValueError):inspect_complete(self.root,IID,HASH,SNAP,snap,validator)
    def test_real_child_killed_after_rename_recovery(self):
        script='''import os,sys\nfrom src.smoke02_commit import *\nr={"instance_id":"F1__test","instance_hash":"a"*64,"namespace":NAMESPACE,"rows":[{"method":m,"instance_hash":"a"*64,"namespace":NAMESPACE} for m in ("B0","B1","B2","O1")]}\ndef hook(stage):\n if stage=="after_rename": os._exit(79)\ncommit_instance(sys.argv[1],"F1__test","a"*64,b\'{"synthetic":true}\',r,"b"*64,lambda:"b"*64,lambda b:("a"*64,NAMESPACE),hook=hook)\n'''
        p=subprocess.run([sys.executable,'-c',script,str(self.root)],capture_output=True)
        self.assertEqual(p.returncode,79,p.stderr)
        with self.assertRaises(ValueError):inspect_complete(self.root,IID,HASH,SNAP,snap,validator)
        q=quarantine_incomplete(self.root,IID,SNAP,snap)
        self.assertTrue(q.is_dir())
        commit_instance(self.root,IID,HASH,INSTANCE,result(),SNAP,snap,validator)
        self.assertTrue(inspect_complete(self.root,IID,HASH,SNAP,snap,validator))


class StreamingDigestTests(unittest.TestCase):
    def test_matches_full_layer_array_across_chunks(self):
        import hashlib
        import numpy as np
        from src.smoke02_commit import streaming_failure_digest
        domain=np.array([False,True,True,True,True,True,True,True],dtype=bool)
        generated=np.array([False,False,True,True,True,True,True,True],dtype=bool)
        v2=np.array([False,False,False,True,True,True,True,True],dtype=bool)
        v3=np.array([False,False,False,False,True,True,True,True],dtype=bool)
        physical=np.array([False,False,False,False,False,True,True,True],dtype=bool)
        accepted=np.array([False,False,False,False,False,False,True,True],dtype=bool)
        expected=hashlib.sha256(bytes([0,1,3,4,5,6,7,7])).hexdigest()
        for chunk in (1,3,8,100):
            self.assertEqual(streaming_failure_digest(domain,generated,v2,v3,physical,accepted,chunk),expected)

if __name__=='__main__': unittest.main()


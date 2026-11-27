"""ENGINEERING-only real FAST transaction path. No research seeds are used."""
from __future__ import annotations
import hashlib,json,os,tempfile,time
from pathlib import Path
from .instances import deserialize_instance
from .execution_snapshot import SNAPSHOT,verify_snapshot,sha256_file
from .smoke02_commit import streaming_failure_digest

NS='GENSPACE-FAIL-01-ENGINEERING'
METHODS=('B0','B1','B2','O1')
SCHEMA='GENSPACE-ENGINEERING-FAST-COMMIT-v1'

def _bytes(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def _hash(b):return hashlib.sha256(b).hexdigest()

def snapshot():
    verify_snapshot(scope='engineering')
    return sha256_file(SNAPSHOT)

def instance(raw):
    x=deserialize_instance(raw.decode() if isinstance(raw,bytes) else raw)
    if x.namespace != NS:raise ValueError('only ENGINEERING namespace enabled')
    return x

def _write(path,b):
    with Path(path).open('xb') as f:
        f.write(b);f.flush();os.fsync(f.fileno())

def validate_result(result,x,iid,snap):
    if result.get('schema')!=SCHEMA or result.get('instance_id')!=iid or result.get('snapshot_hash')!=snap:raise ValueError('result identity/schema mismatch')
    if (result.get('namespace'),result.get('instance_hash'),result.get('public_hash'),result.get('private_hash')) != (NS,x.instance_hash,x.public_hash,x.private_hash):raise ValueError('instance/hash mismatch')
    rows=result.get('rows')
    if not isinstance(rows,list) or len(rows)!=4 or {r.get('method') for r in rows}!=set(METHODS):raise ValueError('method completeness')
    fields={'agreement','candidate_count','verified_count','validator_rejections','representative','application_utility','network_utility','nash_welfare','compiled_actions','namespace','instance_hash'}
    for row in rows:
        if not fields.issubset(row) or row['namespace']!=NS or row['instance_hash']!=x.instance_hash:raise ValueError('method schema/identity')
        for k in ('application_utility','network_utility','nash_welfare'):
            v=row[k]
            if v is not None and (not isinstance(v,(int,float)) or not 0<=v<=1):raise ValueError('utility outside range')
    if not isinstance(result.get('first_failure_sha256'),str) or len(result['first_failure_sha256'])!=64:raise ValueError('missing digest')
    _bytes(result)

def inspect(root,iid,raw,snap):
    if snapshot()!=snap:raise ValueError('snapshot mismatch')
    x=instance(raw); final=Path(root)/iid
    if not final.exists():return False
    from .smoke02_commit import inspect_complete
    def identity(value):
        v=instance(value);return v.instance_hash,v.namespace
    if not inspect_complete(root,iid,x.instance_hash,snap,snapshot,identity,namespace=NS):return False
    payload=(final/'result.json').read_bytes(); ib=(final/'instance.json').read_bytes()
    result=json.loads(payload);validate_result(result,x,iid,snap)
    if ib!=raw:raise ValueError('serialized instance mismatch')
    if snapshot()!=snap:raise ValueError('snapshot changed')
    return True

def run_one(root,iid,raw,library,*,phase_observer=None,inject=None):
    """Run or validate-and-skip. Caller supplies a previously serialized instance."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True); raw=raw.encode() if isinstance(raw,str) else raw
    x=instance(raw);snap=snapshot()
    if library.snapshot.get('execution_scope')!='engineering' or library.snapshot!=verify_snapshot(scope='engineering'):raise ValueError('library snapshot mismatch')
    final=root/iid
    if final.exists():
        if (final/'COMPLETE.json').exists():
            inspect(root,iid,raw,snap);return 'skipped'
        # P4: preserve incomplete publication; never count as complete.
        interrupted=root/'.interrupted';interrupted.mkdir(exist_ok=True)
        dest=Path(tempfile.mkdtemp(prefix=iid+'-',dir=interrupted));dest.rmdir();os.rename(final,dest)
    def fault(point):
        if inject==point:os._exit(80+int(point[1]))
    def phase(event):
        if phase_observer is not None:phase_observer(event)
        if event=='INSTANCE_START':fault('P1')
    digest=[]; invariants=[]
    def observation(inst,lib,evaluator,result,variant):
        import numpy as np
        generated=variant.mask(inst.public.configuration['composition_depth'])
        digest.append(streaming_failure_digest(result.in_domain,generated,result.v2_pass,result.v3_pass,result.physical_ok,result.accepted))
        stages=(result.in_domain,result.v2_pass,result.v3_pass,result.physical_ok,result.accepted)
        nested=all(not np.any(b & ~a) for a,b in zip(stages,stages[1:]))
        finite=True
        for value in (result.application_utility,result.network_utility,result.nash):
            defined=value[result.physical_ok]
            finite &= bool(np.all(np.isfinite(defined)&(defined>=0)&(defined<=1)))
        invariants.append({'stage_masks_nested':bool(nested),'defined_utilities_finite_unit_interval':bool(finite),'verified_count':int(np.count_nonzero(generated & result.accepted)),'generated_count':int(np.count_nonzero(generated))})
    from .fast_runner import run_paired_fast
    rows,stages=run_paired_fast(raw.decode(),library,evaluation_observer=observation,phase_observer=phase)
    fault('P2')
    if len(digest)!=1 or not all((invariants[0]['stage_masks_nested'],invariants[0]['defined_utilities_finite_unit_interval'])):raise ValueError('failed evaluator audit')
    data={'schema':SCHEMA,'instance_id':iid,'namespace':NS,'instance_hash':x.instance_hash,'public_hash':x.public_hash,'private_hash':x.private_hash,'snapshot_hash':snap,'rows':rows,'stages':stages,'first_failure_sha256':digest[0],'invariant_metadata':invariants[0]}
    if phase_observer is not None:phase_observer('PERSISTENCE_START')
    validate_result(data,x,iid,snap)
    from .smoke02_commit import commit_instance
    def identity(value):
        v=instance(value);return v.instance_hash,v.namespace
    def hook(stage):
        point={'before_rename':'P3','after_rename':'P4','after_marker':'P5'}.get(stage)
        if point:fault(point)
    commit_instance(root,iid,x.instance_hash,raw,data,snap,snapshot,identity,hook=hook,namespace=NS)
    inspect(root,iid,raw,snap)
    if phase_observer is not None:
        phase_observer('PERSISTENCE_END')
        phase_observer('INSTANCE_COMPLETE')
    return 'completed'

def run_batch(root,items,library,*,phase_observer=None):
    if len(items)>4:raise ValueError('maximum four instances per child')
    return [run_one(root,iid,raw,library,phase_observer=phase_observer) for iid,raw in items]

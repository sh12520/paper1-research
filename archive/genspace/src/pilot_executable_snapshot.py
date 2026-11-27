"""Locked PILOT execution fingerprint; no seeds or research instances."""
import json, os
from pathlib import Path
from .execution_snapshot import (ROOT, PILOT_EXECUTABLE_SNAPSHOT, PILOT_PREPARATION_SNAPSHOT,
                                 build_snapshot, verify_snapshot, sha256_file)
from .smoke_authorization import PILOT_AUTHORIZATION

def write_locked():
    snapshot=build_snapshot(scope='pilot-execution')
    previous=json.loads(PILOT_PREPARATION_SNAPSHOT.read_text(encoding='utf8'))
    fields=('config_sha256','semantic_library_format_version','semantic_library_sha256',
            'availability_manifest_sha256','availability_index_sha256','registry_fingerprint',
            'model_fingerprint','independent_reference_report_sha256')
    if any(snapshot[k]!=previous[k] for k in fields):raise ValueError('research inputs changed')
    # instances.py differs only by a fixed, strictly verified authorization
    # guard; build_snapshot already checked stripping it against the original
    # independently audited bytes. All remaining core source hashes are exact.
    if any(v!=previous['semantic_core_source_hashes'].get(k) for k,v in snapshot['semantic_core_source_hashes'].items() if k!='src/instances.py'):
        raise ValueError('semantic core changed')
    if PILOT_EXECUTABLE_SNAPSHOT.exists():raise FileExistsError('execution snapshot already exists')
    PILOT_EXECUTABLE_SNAPSHOT.write_text(json.dumps(snapshot,sort_keys=True,indent=2)+'\n',encoding='utf8')
    verify_snapshot(path=PILOT_EXECUTABLE_SNAPSHOT,scope='pilot-execution')
    state={'authorization_version':1,'namespace_authorizations':{'PILOT':{'allowed':False,
        'required_snapshot_sha256':sha256_file(PILOT_EXECUTABLE_SNAPSHOT)},'CONFIRM':{'allowed':False}}}
    old=json.loads(PILOT_AUTHORIZATION.read_text(encoding='utf8'))
    if old.get('namespace_authorizations',{}).get('PILOT',{}).get('allowed') is not False or old.get('namespace_authorizations',{}).get('CONFIRM')!={'allowed':False}:
        raise ValueError('existing pilot authorization is not locked')
    temp=PILOT_AUTHORIZATION.with_suffix('.tmp')
    with temp.open('x',encoding='utf8') as f:
        json.dump(state,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,PILOT_AUTHORIZATION)
    return state

if __name__=='__main__':
    print(json.dumps(write_locked(),sort_keys=True))

"""Namespace-specific authorization for the common experiment route.

Mutable authorization is deliberately outside both immutable snapshots.
These functions do not generate or inspect experimental instances or seeds.
"""
import json
from pathlib import Path
from .execution_snapshot import ROOT,SMOKE02_SHADOW_SNAPSHOT,SMOKE02_SNAPSHOT,PILOT_EXECUTABLE_SNAPSHOT,sha256_file,verify_snapshot

AUTHORIZATION=ROOT/'SMOKE02_AUTHORIZATION_STATE.json'
PILOT_AUTHORIZATION=ROOT/'PILOT_AUTHORIZATION_STATE.json'
SHADOW='GENSPACE-FAIL-01-ENGINEERING-SHADOW'
SMOKE='GENSPACE-FAIL-01-SMOKE'
PILOT='GENSPACE-FAIL-01-PILOT'
CONFIRM='GENSPACE-FAIL-01-CONFIRM'
ROUTES={SHADOW:('ENGINEERING_SHADOW','shadow',SMOKE02_SHADOW_SNAPSHOT),
        SMOKE:('SMOKE','smoke02',SMOKE02_SNAPSHOT)}

def expected_state(shadow_snapshot=SMOKE02_SHADOW_SNAPSHOT,formal_snapshot=SMOKE02_SNAPSHOT):
    return {'authorization_version':2,'namespace_authorizations':{
      'ENGINEERING_SHADOW':{'allowed':True,'required_snapshot_sha256':sha256_file(shadow_snapshot)},
      'SMOKE':{'allowed':False,'required_snapshot_sha256':sha256_file(formal_snapshot)},
      'PILOT':{'allowed':False},'CONFIRM':{'allowed':False}}}

def authorize(namespace,snapshot_path=None,auth_path=None):
    """Check snapshot selection before permission, then fail closed.

    A formal SMOKE call with a shadow snapshot is SNAPSHOT_MISMATCH even when
    the formal authorization is disabled. No generation happens here.
    """
    if namespace == PILOT:
        path=Path(PILOT_EXECUTABLE_SNAPSHOT if snapshot_path is None else snapshot_path)
        authority=Path(PILOT_AUTHORIZATION if auth_path is None else auth_path)
        try:
            candidate=json.loads(path.read_text(encoding='utf8'))
            if candidate.get('execution_scope')!='pilot-execution':raise ValueError('SNAPSHOT_MISMATCH')
            verify_snapshot(path=path,scope='pilot-execution')
            state=json.loads(authority.read_text(encoding='utf8'))
            routes=state['namespace_authorizations']; entry=routes['PILOT']
            version=state['authorization_version']
            if type(version) is not int or version<1 or set(routes)!={'PILOT','CONFIRM'} or routes['CONFIRM']!={'allowed':False}:raise ValueError('invalid authorization schema')
            sha=sha256_file(path)
            if entry.get('required_snapshot_sha256')!=sha:raise ValueError('SNAPSHOT_MISMATCH')
            if type(entry.get('allowed')) is not bool:raise ValueError('invalid permission flag')
            if not entry['allowed']:raise PermissionError('AUTHORIZATION_DENIED')
            return {'namespace':namespace,'snapshot_sha256':sha,'authorization_version':state['authorization_version']}
        except (KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('invalid authorization or snapshot') from exc
    if namespace not in ROUTES:raise PermissionError('AUTHORIZATION_DENIED')
    if auth_path is None:auth_path=AUTHORIZATION
    key,scope,default_path=ROUTES[namespace]
    path=Path(default_path if snapshot_path is None else snapshot_path)
    try:
        candidate=json.loads(path.read_text(encoding='utf8'))
        if candidate.get('execution_scope')!=scope:raise ValueError('SNAPSHOT_MISMATCH')
        verify_snapshot(path=path,scope=scope)
        state=json.loads(Path(auth_path).read_text(encoding='utf8'))
        routes=state['namespace_authorizations']
        if state['authorization_version']!=2 or set(routes)!={'ENGINEERING_SHADOW','SMOKE','PILOT','CONFIRM'}:raise ValueError('invalid authorization schema')
        entry=routes[key]; sha=sha256_file(path)
        if entry.get('required_snapshot_sha256')!=sha:raise ValueError('SNAPSHOT_MISMATCH')
        if routes['PILOT']!={'allowed':False} or routes['CONFIRM']!={'allowed':False}:raise ValueError('forbidden namespace policy')
        if type(entry.get('allowed')) is not bool:raise ValueError('invalid permission flag')
        if not entry['allowed']:raise PermissionError('AUTHORIZATION_DENIED')
        return {'namespace':namespace,'snapshot_sha256':sha,'authorization_version':state['authorization_version']}
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError('invalid authorization or snapshot') from exc

def verify_authorization(path=AUTHORIZATION,snapshot_path=SMOKE02_SHADOW_SNAPSHOT):
    """Compatibility for existing SHADOW helpers, still namespace-explicit."""
    return authorize(SHADOW,snapshot_path,path)

def write_authorization(path=AUTHORIZATION,shadow_snapshot=SMOKE02_SHADOW_SNAPSHOT,formal_snapshot=SMOKE02_SNAPSHOT):
    verify_snapshot(path=shadow_snapshot,scope='shadow')
    verify_snapshot(path=formal_snapshot,scope='smoke02')
    data=expected_state(shadow_snapshot,formal_snapshot)
    Path(path).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',encoding='utf8')
    return data

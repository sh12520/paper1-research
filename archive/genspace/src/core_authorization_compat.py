"""Verify one exact routing guard without weakening old core byte audit.

The historical sampler bytes must match the independently audited SHA-256
after removing exactly one fixed guard at exactly the audited function entry.
The full modified source is still bound by the current execution snapshot.
"""
import hashlib
from pathlib import Path

ANCHOR=b'def derive_seed(namespace, family, configuration, seed):\r\n'
GUARD=(b'    # BEGIN EXACT AUTHORIZATION GUARD v1\r\n'
       b"    if namespace == 'GENSPACE-FAIL-01-CONFIRM':\r\n"
       b"        raise PermissionError('AUTHORIZATION_DENIED')\r\n"
       b"    if namespace in ('GENSPACE-FAIL-01-SMOKE', 'GENSPACE-FAIL-01-PILOT'):\r\n"
       b'        from .smoke_authorization import authorize\r\n'
       b'        authorize(namespace)\r\n'
       b'    # END EXACT AUTHORIZATION GUARD v1\r\n')

def core_source_matches(relative,expected,current,root):
    if not isinstance(expected,str) or not isinstance(current,str): return False
    if relative!='src/instances.py': return expected==current
    raw=(Path(root)/relative).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=current:return False
    if (raw.count(ANCHOR)!=1 or raw.count(GUARD)!=1 or raw.count(ANCHOR+GUARD)!=1
        or raw.count(b'BEGIN EXACT AUTHORIZATION GUARD v1')!=1
        or raw.count(b'END EXACT AUTHORIZATION GUARD v1')!=1):return False
    return hashlib.sha256(raw.replace(GUARD,b'',1)).hexdigest()==expected

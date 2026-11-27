"""Strict instance result schema validation, shared with full aggregation."""
from __future__ import annotations
import re
from .smoke_invariants import check_rows, SHADOW_NAMESPACE

def validate(iid, instance, item, *, namespace=SHADOW_NAMESPACE):
    if not isinstance(iid,str) or not iid or not isinstance(item,dict):
        raise ValueError('invalid result identity')
    if instance.namespace != namespace or item.get('instance_id') != iid:
        raise ValueError('namespace or identity mismatch')
    snap=item.get('snapshot_hash')
    if (not isinstance(snap,str) or not re.fullmatch(r'[0-9a-f]{64}',snap)
            or item.get('snapshot_pre_verified') is not True
            or item.get('snapshot_post_verified') is not True):
        raise ValueError('missing execution snapshot evidence')
    if item.get('ok') is not True or not isinstance(item.get('rows'),list):
        raise ValueError('invalid result envelope')
    validation=item.get('check')
    if not isinstance(validation,dict) or validation.get('ok') is not True:
        raise ValueError('missing independent validation')
    result=check_rows(item['rows'],{iid:instance},expected_ids=[iid],
                      validations={iid:validation},namespace=namespace)
    if result.get('ok') is not True:
        raise ValueError('invalid result schema or candidate counts: '+str(result.get('checks')))
    return True

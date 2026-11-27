"""Identity-only plans and a shadow fixture factory, without running experiments.

The shadow fixture factory applies the audited sampler's unchanged code with
an isolated globals mapping for shadow-only seed derivation. It constructs no
ENGINEERING-labelled intermediate or relabelled instance.
"""
from __future__ import annotations
from hashlib import sha256
from itertools import product
import json

SHADOW_NAMESPACE = 'GENSPACE-FAIL-01-ENGINEERING-SHADOW'
SMOKE_NAMESPACE = 'GENSPACE-FAIL-01-SMOKE'
ENGINEERING_NAMESPACE = 'GENSPACE-FAIL-01-ENGINEERING'
FAMILIES = ('F1','F2','F3','F4')
PRESSURES = ('low','medium','high')
CONFLICTS = ('medium','high')
RICHNESS = ('sparse','rich')
DEPTHS = (1,2)

def _slot(f,p,c,r,d,s):
    return {'instance_id':f'{f}__{p}__{c}__{r}__d{d}__s{s}',
            'family':f,'configuration':{'resource_pressure':p,'preference_conflict':c,
            'capability_richness':r,'composition_depth':d},'seed_index':s}

def smoke_template():
    slots=[_slot(*v) for v in product(FAMILIES,PRESSURES,CONFLICTS,RICHNESS,DEPTHS,(0,1))]
    return {'run_id':'SMOKE-02','namespace':SMOKE_NAMESPACE,'planned_count':192,'instances':slots,
            'identity_slots_only':True}

def shadow_plan():
    slots=[_slot(f,'medium','high',r,d,0) for f,r,d in product(FAMILIES,RICHNESS,DEPTHS)]
    audits=[x['instance_id'] for x in slots if x['configuration']['capability_richness']=='rich' and x['configuration']['composition_depth']==2]
    rerun=[x['instance_id'] for x in slots if x['configuration']['composition_depth']==2]
    return {'run_id':'ENGINEERING-SHADOW-01','namespace':SHADOW_NAMESPACE,'planned_count':16,'instances':slots,
            'audit4':audits,'rerun8':rerun,'fresh_repeat16':[x['instance_id'] for x in slots]}

def validate_plan(plan,kind):
    expected={'smoke':smoke_template,'shadow':shadow_plan}.get(kind)
    if expected is None: raise ValueError('unsupported plan kind')
    if plan != expected(): raise ValueError('plan differs from deterministic complete identity grid')
    if len({s['instance_id'] for s in plan['instances']}) != plan['planned_count']:
        raise ValueError('duplicate instance identity')
    return True

def shadow_seed_token(family,configuration,seed_index):
    if family not in FAMILIES or not isinstance(seed_index,int) or seed_index<0:
        raise ValueError('invalid shadow seed identity')
    payload={'namespace':SHADOW_NAMESPACE,'family':family,'configuration':configuration,'seed':str(seed_index)}
    data=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')
    return 'SHADOW-SHA256:'+sha256(data).hexdigest()

def generate_shadow(family,configuration,seed_index):
    # Reuse the audited sampler bytecode unchanged with a private globals map.
    # No ENGINEERING Instance is ever constructed or relabelled, and the
    # original function/global derive_seed remains untouched. Only the seed
    # namespace gate is different; seed encoding is identical to the core.
    from types import FunctionType
    from . import instances
    original = instances.generate_instance
    def shadow_derive(namespace, family, configuration, seed):
        if namespace != SHADOW_NAMESPACE:
            raise ValueError('shadow sampler accepts only shadow namespace')
        return int(instances.digest({'namespace':namespace, 'family':family,
                                     'configuration':configuration, 'seed':str(seed)}),16)
    scoped_globals = dict(original.__globals__)
    scoped_globals['derive_seed'] = shadow_derive
    scoped = FunctionType(original.__code__, scoped_globals, original.__name__,
                          original.__defaults__, original.__closure__)
    return scoped(family,configuration,seed_index,namespace=SHADOW_NAMESPACE)

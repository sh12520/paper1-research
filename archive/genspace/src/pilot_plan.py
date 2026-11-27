"""Deterministic PILOT identity slots only; never derives a random seed."""
from collections import Counter
from itertools import product
from .shadow_plans import FAMILIES, PRESSURES, CONFLICTS, RICHNESS, DEPTHS, _slot

PILOT_NAMESPACE = 'GENSPACE-FAIL-01-PILOT'


def pilot_template():
    """Return 96 configurations × 20 indices, without sampling any data."""
    slots = []
    for f, p, c, r, d, index in product(FAMILIES, PRESSURES, CONFLICTS,
                                       RICHNESS, DEPTHS, range(20)):
        slots.append({**_slot(f, p, c, r, d, index), 'namespace': PILOT_NAMESPACE})
    return {'run_id': 'PILOT-01', 'namespace': PILOT_NAMESPACE,
            'planned_count': 1920, 'identity_slots_only': True, 'instances': slots}


def validate_pilot_template(plan):
    """Reject gaps, duplicates, reordering, other namespaces, or altered grid."""
    if plan != pilot_template():
        raise ValueError('PILOT plan differs from deterministic identity grid')
    slots = plan['instances']
    identities = {s['instance_id'] for s in slots}
    counts = Counter((s['family'], tuple(sorted(s['configuration'].items()))) for s in slots)
    if len(slots) != 1920 or len(identities) != 1920 or len(counts) != 96:
        raise ValueError('PILOT plan has incorrect coverage')
    if any(n != 20 for n in counts.values()) or any(s['namespace'] != PILOT_NAMESPACE for s in slots):
        raise ValueError('PILOT identity namespace or per-configuration count mismatch')
    return True


def inherited_engineering_subsets(plan):
    """Select existing SMOKE diagnostic coordinates, not research gates.

    These public deterministic checks are inherited engineering defaults; the
    prior research preregistration does not explicitly preregister them for
    PILOT. They must not be represented as previously registered PILOT gates.
    """
    validate_pilot_template(plan)
    slots=plan['instances']
    cfg={'resource_pressure':'medium','preference_conflict':'high',
         'capability_richness':'rich','composition_depth':2}
    return {
        'audit4':[s['instance_id'] for s in slots if s['configuration']==cfg and s['seed_index']==0],
        'rerun8':[s['instance_id'] for s in slots if s['configuration']==cfg and s['seed_index'] in (0,1)],
        'fresh_repeat16':[s['instance_id'] for s in slots if s['configuration']['resource_pressure'] in ('low','high')
                          and s['configuration']['preference_conflict']=='medium'
                          and s['configuration']['capability_richness']=='sparse'
                          and s['seed_index']==0],
    }

"""Serializable public/private benchmark instances and deterministic toy model.

The caller supplies the namespace and seed; no namespace is sampled implicitly.
The module never passes private preferences to candidate enumeration.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from itertools import product
import json
import random
from pathlib import Path
from .models import Profile, Capability
from .registry import default_registry

NAMESPACES = ('GENSPACE-FAIL-01-ENGINEERING', 'GENSPACE-FAIL-01-SMOKE', 'GENSPACE-FAIL-01-PILOT', 'GENSPACE-FAIL-01-CONFIRM')
FAMILIES = ('F1', 'F2', 'F3', 'F4')

@dataclass(frozen=True)
class PublicInstance:
    family: str
    configuration: dict
    horizon: int
    states: tuple[str, ...]
    capacity: tuple[tuple[int,str,float,float,float], ...]
    m0_profiles: tuple[Profile, ...]
    mr_profiles: tuple[Profile, ...]
    b2_profiles: tuple[Profile, ...]
    capabilities: tuple[str, ...]
    conditions: tuple[str, ...]
    durations: tuple[int, ...]
    offsets: tuple[int, ...]
    intervals: tuple[tuple[int, int], ...]
    offload_levels: tuple[str, ...]
    public_constraints: dict
    resource_parameters: dict
    registry: dict
    model_config_hash: str

@dataclass(frozen=True)
class PrivatePreferences:
    application: dict
    network: dict

@dataclass(frozen=True)
class Instance:
    namespace: str
    seed_label: str
    public: PublicInstance
    private: PrivatePreferences

    def serialize(self):
        return canonical_json(asdict(self))

    @property
    def public_hash(self):
        return digest(asdict(self.public))

    @property
    def private_hash(self):
        return digest(asdict(self.private))

    @property
    def instance_hash(self):
        return digest(asdict(self))


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical_json(value).encode('utf-8')).hexdigest()


def derive_seed(namespace, family, configuration, seed):
    # BEGIN EXACT AUTHORIZATION GUARD v1
    if namespace == 'GENSPACE-FAIL-01-CONFIRM':
        raise PermissionError('AUTHORIZATION_DENIED')
    if namespace in ('GENSPACE-FAIL-01-SMOKE', 'GENSPACE-FAIL-01-PILOT'):
        from .smoke_authorization import authorize
        authorize(namespace)
    # END EXACT AUTHORIZATION GUARD v1
    if namespace not in NAMESPACES:
        raise ValueError('unknown namespace')
    # Length-delimited canonical JSON preserves namespace-tagged identity.
    payload = {'namespace':namespace, 'family':family, 'configuration':configuration, 'seed':str(seed)}
    return int(digest(payload), 16)


def _profiles(qs, ds=(1.0,), rs=(1.0,)):
    return tuple(Profile(q,d,r) for q,d,r in product(qs,ds,rs))


def load_model_config():
    """JSON is valid YAML; stdlib parser avoids an optional dependency."""
    config = json.loads((Path(__file__).resolve().parent.parent / 'config.yaml').read_text(encoding='utf-8'))
    expected = config['capability_cost_accounting']
    registry = default_registry()
    if expected['accounting_rule'] != 'active_path_distinct_roles_per_active_cell_setup_zero':
        raise ValueError('unsupported capability cost accounting rule')
    for key, cap in registry.items():
        if expected['execution_cost_per_active_cell'].get(key) != cap.execution_cost or expected['resource_cost_per_active_cell'].get(key, {}) != cap.resource_cost:
            raise ValueError('config and registry capability costs differ: ' + key)
    return config


def generate_instance(family, configuration, seed, namespace='GENSPACE-FAIL-01-ENGINEERING'):
    if family not in FAMILIES:
        raise ValueError('unknown family')
    required = {'resource_pressure','preference_conflict','capability_richness','composition_depth'}
    if not required <= configuration.keys():
        raise ValueError('missing configuration fields')
    pressure, conflict, richness, depth = (configuration[k] for k in ('resource_pressure','preference_conflict','capability_richness','composition_depth'))
    if pressure not in ('low','medium','high') or conflict not in ('medium','high') or richness not in ('sparse','rich') or depth not in (1,2):
        raise ValueError('invalid configuration')
    full = load_model_config()
    m = full['model_draft']
    config = {k: configuration[k] for k in sorted(required)}
    rng = random.Random(derive_seed(namespace, family, config, seed))
    states = tuple(m['states'])
    caps = set(default_registry())
    if richness == 'sparse':
        structural = [('apply_conditional_policy','observe_motion_state'), ('schedule_start',), ('apply_phased_policy',), ('enable_edge_offload','reserve_edge_compute')]
        for group in structural:
            if rng.random() < m['sparse_structural_group_drop_probability']:
                caps.difference_update(group)
    base = m['pressure_ran_baseline'][pressure]
    jitter = rng.uniform(*m['pressure_uniform_jitter'])
    factors = m['family_ran_multiplier']
    capacity = []
    for t,s in product(range(m['horizon']), states):
        factor = 1.0
        if family == 'F1' and s == 'moving': factor = factors['F1_moving']
        if family == 'F2' and t == 0: factor = factors['F2_time0']
        if family == 'F3' and t == 0: factor = factors['F3_time0']
        if family == 'F4': factor = factors['F4_all']
        capacity.append((t,s,round((base+jitter)*factor,6),round(m['fh_capacity_intercept']+m['fh_capacity_slope']*(base+jitter),6),round(m['edge_capacity_intercept']+m['edge_capacity_slope']*(base+jitter),6)))
    def profiles(which):
        values = m['scalar_domains'][which]
        return _profiles(values['quality'],values['deadline'],values['rate'])
    registry = json.loads(canonical_json({k: asdict(v) for k,v in sorted(default_registry().items())}))
    model_config_hash = digest({'model_draft':m,'capability_cost_accounting':full['capability_cost_accounting']})
    public = PublicInstance(family, config, m['horizon'], states, tuple(capacity), profiles('m0'), profiles('mr'), profiles('b2'), tuple(sorted(caps)), tuple(m['conditions']), tuple(m['durations']), tuple(m['offsets']), tuple(tuple(x) for x in m['intervals']), tuple(m['offload_levels']), dict(m['public_hard_constraints']), dict(m['demand']), registry, model_config_hash)
    aw, nw = m['application_weight_ranges'], m['network_weight_ranges']
    app = {'quality_weight':rng.uniform(*aw['quality']), 'latency_weight':rng.uniform(*aw['latency']), 'start_delay_weight':rng.uniform(*aw['start_delay']), 'switching_penalty':rng.uniform(*aw['switching']), 'reservation':rng.uniform(*m['application_reservation'][conflict])}
    net = {'ran_cost':rng.uniform(*nw['ran']), 'fh_cost':rng.uniform(*nw['fh']), 'edge_cost':rng.uniform(*nw['edge']), 'policy_complexity_cost':rng.uniform(*nw['policy_complexity']), 'actuation_switching_cost':rng.uniform(*nw['switching']), 'reservation':rng.uniform(*m['network_reservation'][conflict])}
    return Instance(namespace, str(seed), public, PrivatePreferences(app,net))


def deserialize_instance(text):
    obj = json.loads(text)
    p = obj['public']
    for name in ('m0_profiles','mr_profiles','b2_profiles'):
        p[name] = tuple(Profile(**x) for x in p[name])
    for name in ('states','capabilities','conditions','durations','offsets','offload_levels'):
        p[name] = tuple(p[name])
    p['capacity'] = tuple(tuple(row) for row in p['capacity'])
    p['intervals'] = tuple(tuple(row) for row in p['intervals'])
    return Instance(obj['namespace'], obj['seed_label'], PublicInstance(**p), PrivatePreferences(**obj['private']))


def registry_from_public(public):
    """Rehydrate exactly the declared registry from the hashed public record."""
    out = {}
    for key, raw in public.registry.items():
        fields = dict(raw)
        for name in ('input_types', 'output_types', 'preconditions', 'effects', 'supported_scope'):
            fields[name] = tuple(fields[name])
        item = Capability(**fields)
        if item.id != key:
            raise ValueError('registry key and capability ID differ')
        out[key] = item
    return out

def demand(public, profile, level, t, state):
    p = public.resource_parameters
    offload = level == 'edge'
    return {'RAN':profile.quality*(p['offload_ran_factor'] if offload else 1), 'FH':profile.rate*p['fh_rate_factor']*(p['offload_fh_factor'] if offload else 1), 'EDGE':profile.quality*p['offload_edge_factor'] if offload else 0.0}


def hard_check(public, actions):
    c = public.public_constraints
    return (len(actions) >= c['min_active_slots'] and all(a[2].quality >= c['min_quality'] and a[2].deadline <= c['max_deadline'] for a in actions))


def utilities(public, private, actions, execution_cost=0., resource_surcharge=None, cell_surcharges=None, cell_execution_costs=None):
    """Utilities depend solely on realized schedule, never AST syntax."""
    total = public.horizon*len(public.states)
    amap = {(t,s):(p,l) for t,s,p,l in actions}
    quality = sum(p.quality for _,_,p,_ in actions)/total
    latency = sum(1/(1+p.deadline) for _,_,p,_ in actions)/total
    starts = [min((t for t in range(public.horizon) if (t,s) in amap), default=public.horizon) / public.horizon for s in public.states]
    delay = sum(starts)/len(starts)
    transitions = sum(amap.get((t,s)) != amap.get((t-1,s)) for s in public.states for t in range(1,public.horizon)) / max(1,len(public.states)*(public.horizon-1))
    a=private.application
    au = (a['quality_weight']*quality + a['latency_weight']*latency + a['start_delay_weight']*(1-delay) + a['switching_penalty']*(1-transitions)) / sum(a[k] for k in ('quality_weight','latency_weight','start_delay_weight','switching_penalty'))
    surcharge = resource_surcharge or {}
    loads = [demand(public,p,l,t,s) for t,s,p,l in actions]
    avg = {k: sum(x[k] + (cell_surcharges.get((action[0], action[1]), {}).get(k, 0.) if cell_surcharges is not None else surcharge.get(k, 0.)) for x, action in zip(loads, actions))/total for k in ('RAN','FH','EDGE')}
    n=private.network
    complexity = len({(p,l) for _,_,p,l in actions})/total
    nu = 1 - (n['ran_cost']*avg['RAN'] + n['fh_cost']*avg['FH'] + n['edge_cost']*avg['EDGE'] + n['policy_complexity_cost']*complexity + n['actuation_switching_cost']*transitions) / sum(n[k] for k in ('ran_cost','fh_cost','edge_cost','policy_complexity_cost','actuation_switching_cost')) - (sum(cell_execution_costs.values())/total if cell_execution_costs is not None else execution_cost*len(actions)/total)
    return max(0.,min(1.,au)),max(0.,min(1.,nu))

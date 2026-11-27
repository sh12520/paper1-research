"""Public instance representation and the benchmark evaluator."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from .models import Capability, Profile
from .registry import default_registry


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

"""Public-only candidate ordering for the DG-PCE development prototype.

Scores are deliberately approximate: they omit capability resource surcharge,
hard profile constraints, preconditions, and acceptance. They do not assert
V1--V4 feasibility and do not consume or substitute for exact verification.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,itertools,time
import numpy as np

MARGIN_WEIGHT=0.025
COST_WEIGHT=0.02
QUALITY_WEIGHT=0.08
GROUP_COMPLEXITY_WEIGHT=0.01
PROBE_COST_WEIGHT=0.02
PROBE_GROUP_PENALTY=0.01
GROUPS=((1,'C',('apply_conditional_policy','observe_motion_state')),
        (2,'D',('schedule_start',)),
        (4,'P',('apply_phased_policy','set_validity_interval')),
        (8,'O',('enable_edge_offload','reserve_edge_compute')))

@dataclass(frozen=True)
class PublicView:
    depth:int
    states:tuple
    horizon:int
    capacity:tuple
    profiles:tuple
    capabilities:tuple
    resource_parameters:tuple
    public_constraints:tuple
    role_costs:tuple

def sanitize_public(public):
    """Copy an explicit allowlist; never copy family, configuration labels or hashes."""
    return PublicView(depth=int(public.configuration['composition_depth']),
        states=tuple(public.states),horizon=int(public.horizon),
        capacity=tuple((int(t),str(s),float(a),float(b),float(c)) for t,s,a,b,c in public.capacity),
        profiles=tuple((float(p.quality),float(p.deadline),float(p.rate)) for p in public.b2_profiles),
        capabilities=tuple(sorted(public.capabilities)),
        resource_parameters=tuple(sorted((str(k),float(v)) for k,v in public.resource_parameters.items())),
        public_constraints=tuple(sorted((str(k),v) for k,v in public.public_constraints.items())),
        role_costs=tuple(sorted((str(k),float(v['execution_cost']),
            tuple(sorted((str(a),float(b)) for a,b in v['resource_cost'].items()))) for k,v in public.registry.items())))

def group_bits(library):
    from src.registry import default_registry
    roles=tuple(sorted(default_registry())); out=np.zeros(len(library.keys),dtype=np.uint8)
    for bit,names in ((1,('apply_conditional_policy',)),(2,('schedule_start',)),
                      (4,('apply_phased_policy','set_validity_interval')),(8,('enable_edge_offload',))):
        for name in names:out|=(library.keys[:,1+2*roles.index(name)]!=255).astype(np.uint8)*bit
    return out

def _capacities(view):
    m={(t,s):(a,b,c) for t,s,a,b,c in view.capacity}
    return np.asarray([m[t,s] for t in range(view.horizon) for s in view.states],dtype=np.float64)

def _static_deficits(view):
    caps=_capacities(view);p=dict(view.resource_parameters)
    profiles=np.asarray(view.profiles,dtype=np.float64)
    demand=np.stack((profiles[:,0],profiles[:,2]*p['fh_rate_factor'],np.zeros(len(profiles))),axis=1)
    # Smooth public proxy: omitted capability surcharge and hard constraints.
    deficit=np.maximum(demand[:,None,:]-caps[None,:,:],0.)/np.maximum(caps[None,:,:],1e-9)
    choice=int(np.argmin(deficit.mean(axis=(1,2))))
    return caps,deficit[choice],float(deficit[choice].mean())

def deadlock_signature(view,b2_public_feasible_count,baseline=None):
    caps,deficits,best=_static_deficits(view) if baseline is None else baseline
    means=caps.mean(axis=0);d=deficits.reshape(view.horizon,len(view.states),3)
    state=d.mean(axis=(0,2));timing=d.mean(axis=(1,2))
    early=caps[:len(view.states)].mean(axis=0);late=caps[len(view.states):].mean(axis=0)
    # Remaining average EDGE capacity after the lowest B2-profile offload
    # demand, normalized by average EDGE capacity; this is a public proxy.
    min_edge=min(q*dict(view.resource_parameters)['offload_edge_factor'] for q,_,_ in view.profiles)
    headroom=max(0.,float(means[2])-min_edge)/max(float(means[2]),1e-9)
    return {'resource_normalized_deficit':tuple(float(x) for x in d.mean(axis=(0,1))),
       'per_state_deficit':tuple(float(x) for x in state),
       'state_deficit_heterogeneity':float(np.ptp(state)),
       'per_time_deficit':tuple(float(x) for x in timing),
       'time_deficit_heterogeneity':float(np.ptp(timing)),
       'early_late_capacity_relief':tuple(float((l-e)/max(abs(e),1e-9)) for e,l in zip(early,late)),
       'ran_fh_deficit_edge_headroom':(float(d[:,:,0].mean()),float(d[:,:,1].mean()),headroom),
       'b2_public_feasible_count':int(b2_public_feasible_count),
       'available_capabilities':view.capabilities,'best_b2_proxy_violation':best}

def _proxy(view,library,ids):
    """Estimate normalized capacity excess, margin and cost; never validate."""
    caps=_capacities(view); pars=dict(view.resource_parameters)
    profiles=np.asarray(view.profiles);q=profiles[:,0];rate=profiles[:,2]
    n=len(ids);violation=np.zeros(n);margin=np.zeros(n);quality=np.zeros(n);cost=np.zeros(n)
    role_costs=getattr(library,'role_costs',None); execution=getattr(library,'execution_costs',None)
    for j in range(len(caps)):
        ix=library.profiles[ids,j];active=ix!=255;safe=np.where(active,ix,0)
        off=library.level[ids,j]==1
        ran=np.where(active,q[safe]*np.where(off,pars['offload_ran_factor'],1.),0.)
        fh=np.where(active,rate[safe]*pars['fh_rate_factor']*np.where(off,pars['offload_fh_factor'],1.),0.)
        edge=np.where(active & off,q[safe]*pars['offload_edge_factor'],0.)
        for k,demand in enumerate((ran,fh,edge)):
            normalized=(demand-caps[j,k])/max(caps[j,k],1e-9)
            violation+=np.maximum(normalized,0.)
            margin+=np.clip(-normalized,-1.,1.)
        quality+=np.where(active,q[safe],0.)
        if role_costs is not None and execution is not None:
            masks=library.role_masks[ids,j];cost+=np.where(active,execution[masks]+role_costs[masks].sum(axis=1),0.)
    scale=float(len(caps));violation/=3*scale;margin/=3*scale;quality/=scale;cost/=scale
    return violation,margin,quality,cost

def _deficit_vectors(view,library,ids):
    """Public proxy excess by cell/resource, omitting surcharge and hard checks."""
    caps=_capacities(view);pars=dict(view.resource_parameters);profiles=np.asarray(view.profiles)
    out=np.zeros((len(ids),len(caps),3),dtype=float)
    for j in range(len(caps)):
        ix=library.profiles[ids,j];active=ix!=255;safe=np.where(active,ix,0);off=library.level[ids,j]==1
        q=profiles[safe,0];rate=profiles[safe,2]
        demand=np.stack((np.where(active,q*np.where(off,pars['offload_ran_factor'],1.),0.),
          np.where(active,rate*pars['fh_rate_factor']*np.where(off,pars['offload_fh_factor'],1.),0.),
          np.where(active & off,q*pars['offload_edge_factor'],0.)),axis=1)
        out[:,j,:]=np.maximum(demand-caps[j],0.)/np.maximum(caps[j],1e-9)
    return out

def complementarity(first,second):
    """Incremental union of per-cell/resource reductions beyond best alone."""
    return float(np.maximum(first,second).mean()-max(first.mean(),second.mean()))

@dataclass
class Plan:
    order:np.ndarray
    signature:dict
    mechanism_order:tuple
    path:tuple
    probe_count:int
    probe_seconds:float
    public_ranking_seconds:float
    relief:dict
    stages:tuple
    public_ranked_count:int
    public_setup_seconds:float
    pair_complementarity:dict
    b2_proxy_count:int

def make_plan(view,library,availability,b2_public_feasible_count,strategy,budget=10000):
    """Return candidate IDs ordered solely by allowed public information.

    All non-B2 comparators share classes with <=2 distinct operator groups.
    Only singleton classes are used for public probes. See METHOD_SPEC.
    """
    if not isinstance(view,PublicView):raise TypeError('sanitized PublicView required')
    if strategy not in ('DG-PCE','SINGLETON-ONLY','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY'):raise ValueError('unknown strategy')
    if view.depth not in (1,2):raise ValueError('unsupported depth')
    started=time.perf_counter();baseline=_static_deficits(view);sig=deadlock_signature(view,b2_public_feasible_count,baseline)
    bits=group_bits(library);universe=availability.mask(view.depth)
    single=(bits==1)|(bits==2)|(bits==4)|(bits==8)
    pair=np.zeros(len(bits),dtype=bool)
    for a,b in itertools.combinations((1,2,4,8),2):pair|=bits==(a|b)
    universe=universe & (single | pair)
    probe_start=time.perf_counter()
    relief={name:None for _,name,_ in GROUPS};raw_relief=dict(relief);vectors={};extra_probes=0
    pi=np.empty(0,dtype=np.int64)
    if strategy in ('DG-PCE','SINGLETON-ONLY'):
        probes=availability.mask(1)&single
        pi=np.flatnonzero(probes);pv,pm,pq,pc=_proxy(view,library,pi)
        for bit,name,required in GROUPS:
            picked=bits[pi]==bit
            # Sequence and ValidFor are alternative constructors in P; either
            # surviving role suffices to admit a phase-group depth-one probe.
            available=(any(x in view.capabilities for x in required) if name=='P' else all(x in view.capabilities for x in required))
            if not available or not np.any(picked):continue
            positions=np.flatnonzero(picked);best=int(positions[np.argmin(pv[positions])])
            probe_min=float(pv[best]);raw_relief[name]=sig['best_b2_proxy_violation']-probe_min
            relief[name]=raw_relief[name]-PROBE_COST_WEIGHT*float(pc[best])-PROBE_GROUP_PENALTY
            _,baseline_deficit,_=baseline
            probe_vector=_deficit_vectors(view,library,pi[best:best+1])[0]
            vectors[name]=np.maximum(baseline_deficit-probe_vector,0.);extra_probes+=1
    sig['raw_probe_relief']=raw_relief
    # Explicitly count all approximate probe score evaluations, separately
    # from exact verification budget. No V1--V5 calls occur in this module.
    probe_end=time.perf_counter();ids=np.flatnonzero(universe & single if strategy=='SINGLETON-ONLY' else universe)
    ranked_count=0
    if strategy=='RANDOM-BUDGET':ordered=ids
    else:
        v,m,q,cost=_proxy(view,library,ids)
        # A smooth ranking heuristic, not a private utility or feasibility result.
        score=v-MARGIN_WEIGHT*m+COST_WEIGHT*cost+QUALITY_WEIGHT*(1.-q)
        counts=np.zeros(16,dtype=np.uint8)
        for k in range(16):counts[k]=k.bit_count()
        score+=GROUP_COMPLEXITY_WEIGHT*counts[bits[ids]]
        ranked=np.lexsort((ids,score)); ordered=ids[ranked];ranked_count=len(ids)
    mech=tuple(sorted((name for bit,name,_ in GROUPS if relief[name] is not None),key=lambda n:(-relief[n],n)))
    namebit={name:bit for bit,name,_ in GROUPS}
    complement={}
    for a,b in itertools.combinations(mech,2):
        va,vb=vectors[a],vectors[b]
        complement[a+'+'+b]=complementarity(va,vb)
    if strategy=='RANDOM-BUDGET':
        seed=int.from_bytes(hashlib.sha256(json.dumps(view.__dict__,sort_keys=True,default=list,separators=(',',':')).encode()).digest()[:8],'big')
        rng=np.random.default_rng(seed);ordered=ids[rng.permutation(len(ids))];stages=(('random',len(ordered)),)
    elif strategy=='FLAT-FEASIBILITY':stages=(('flat',len(ordered)),)
    else:
        # Existing PILOT target representative-label counts: O=823, P=38,
        # C=22, D=1 (labels can overlap). Used only by this comparator.
        ranking=mech if strategy!='GLOBAL-FREQUENCY' else tuple(name for name in ('O','P','C','D') if np.any(bits[ids]==namebit[name]))
        pairs=sorted(itertools.combinations(ranking,2),key=lambda pair:(-(sum(relief[n] for n in pair)+complement[pair[0]+'+'+pair[1]]),pair)) if strategy!='GLOBAL-FREQUENCY' else list(itertools.combinations(ranking,2))
        stage_masks=[(n,namebit[n]) for n in ranking]
        if strategy!='SINGLETON-ONLY':stage_masks.extend(('+'.join(x),namebit[x[0]]|namebit[x[1]]) for x in pairs)
        pieces=[];stages=[]
        for name,mask in stage_masks:
            part=ordered[bits[ordered]==mask]
            if len(part):pieces.append(part);stages.append((name,len(part)))
        ordered=np.concatenate(pieces) if pieces else np.empty(0,dtype=np.int64)
        mech=ranking
    return Plan(ordered,sig,mech,tuple(name for name,_ in stages),len(pi)+extra_probes,probe_end-probe_start,time.perf_counter()-probe_end,relief,tuple(stages),ranked_count,probe_start-started,complement,len(view.profiles))

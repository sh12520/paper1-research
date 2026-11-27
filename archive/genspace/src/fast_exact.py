"""Exact vectorized packed-graph evaluation, experimental engineering only.

No research instance is generated here. Requires independently audited graph
and a matching, fail-closed execution snapshot. Floating operations follow the
reference order; candidate-level differential validation is mandatory.
"""
from __future__ import annotations
import gzip,json,struct
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from .compact_semantics import SCOPES
from .instances import load_model_config,digest

def _compensated_add(high, low, value):
    """Vector Neumaier accumulator matching CPython 3.12 float sum."""
    total=high+value
    error=np.where(np.abs(high)>=np.abs(value),(high-total)+value,(value-total)+high)
    return total, low+error


@dataclass
class Evaluation:
    public_ok: object
    physical_ok: object
    application_utility: object
    network_utility: object
    accepted: object
    nash: object
    winner: int | None
    timings: dict
    in_domain: object
    v2_pass: object
    v3_pass: object


class FastPublicCompatibility:
    """Resolve fixed public descriptors without constructing contract ASTs."""
    def __init__(self, public):
        from .instances import registry_from_public
        from .registry import default_registry
        from .state_machine import bind_capabilities, _signature
        reference = default_registry()
        registry = registry_from_public(public)
        self.roles = tuple(sorted(reference))
        self.role_index = {role: i for i, role in enumerate(self.roles)}
        self.available, self.expected, self.supported = [], [], []
        for role in self.roles:
            item = registry[role]
            bound = bind_capabilities({role}, public.capabilities, registry)
            self.available.append(bool(bound) and _signature(item) == _signature(reference[role]))
            self.expected.append((1 << len(item.preconditions)) - 1)
            self.supported.append(sum(1 << i for i, scope in enumerate(SCOPES)
                                      if scope in item.supported_scope))
        self.capacities = {(t, state): (ran, fh, edge)
                           for t, state, ran, fh, edge in public.capacity}

class FastLibrary:
    def __init__(self, header, records, snapshot):
        self.snapshot=snapshot
        self.header=header
        self.records=records
        self.keys=records[:,:49]
        self.tokens=records[:,49:56]
        self.cells=self.keys[:,25:49].reshape(-1,6,4)
        self.profiles=self.cells[:,:,0]
        self.active=self.profiles!=255
        self.level=self.cells[:,:,1]
        self.role_masks=(self.cells[:,:,2].astype(np.uint16)<<8)|self.cells[:,:,3].astype(np.uint16)
        self.required_role_masks=np.zeros(len(self.keys),dtype=np.uint16)
        for i in range(12):
            self.required_role_masks |= (self.keys[:,1+2*i]!=255).astype(np.uint16) << i
        self.class_ids=np.arange(len(self.keys),dtype=np.uint32)
        self._basis=None

    @classmethod
    def from_graph(cls,path=None, *, scope='engineering'):
        from .execution_snapshot import verify_snapshot,GRAPH,SNAPSHOT,SMOKE02_SHADOW_SNAPSHOT,SMOKE02_SNAPSHOT,PILOT_EXECUTABLE_SNAPSHOT
        if scope not in ('engineering','shadow','smoke02','pilot-execution'):
            raise ValueError('unsupported execution scope')
        graph=GRAPH if path is None else path
        snapshot_path={'engineering': SNAPSHOT, 'shadow': SMOKE02_SHADOW_SNAPSHOT, 'smoke02': SMOKE02_SNAPSHOT, 'pilot-execution': PILOT_EXECUTABLE_SNAPSHOT}[scope]
        if scope in ('smoke02','pilot-execution'):
            from .smoke_authorization import authorize
            authorize('GENSPACE-FAIL-01-SMOKE' if scope == 'smoke02' else 'GENSPACE-FAIL-01-PILOT',snapshot_path)
        started=perf_counter()
        if scope=='engineering':
            snapshot=verify_snapshot(graph=graph)
        else:
            snapshot=verify_snapshot(path=snapshot_path,graph=graph,scope=scope)
        with gzip.open(graph,'rb') as f:
            if f.read(4)!=b'GSG1': raise ValueError('bad graph magic')
            raw=f.read(4)
            if len(raw)!=4: raise ValueError('truncated graph header')
            length=struct.unpack('>I',raw)[0]
            header=json.loads(f.read(length)); payload=f.read()
        if header.get('format')!='GENSPACE-GRAPH-v1' or header.get('key_bytes')!=49: raise ValueError('unsupported graph')
        if len(payload)!=1394064*56: raise ValueError('incorrect graph record count')
        records=np.frombuffer(payload,dtype=np.uint8).reshape(-1,56)
        library=cls(header,records,snapshot)
        library.snapshot_path=snapshot_path
        graph_load=perf_counter()-started
        started=perf_counter()
        from .availability_index import AvailabilityBundle
        library.availability=AvailabilityBundle.load(snapshot)
        library.load_timings={'graph_load_s':graph_load,
                              'availability_indices_load_s':perf_counter()-started,
                              'availability_index_count':len(library.availability.entries)}
        return library

    def bind_public_basis(self,p):
        """One-time, fixed-library profile/grammar check and public feature build."""
        config=load_model_config(); m=config['model_draft']
        expected=digest({'model_draft':m,'capability_cost_accounting':config['capability_cost_accounting']})
        profiles=tuple((q,d,r) for q in m['scalar_domains']['b2']['quality'] for d in m['scalar_domains']['b2']['deadline'] for r in m['scalar_domains']['b2']['rate'])
        basis=(p.horizon,p.states,tuple((x.quality,x.deadline,x.rate) for x in p.b2_profiles),p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels,p.model_config_hash)
        required=(3,('still','moving'),profiles,tuple(m['conditions']),tuple(m['durations']),tuple(m['offsets']),tuple(tuple(x) for x in m['intervals']),tuple(m['offload_levels']),expected)
        if basis!=required: raise ValueError('instance grammar/model basis differs from audited graph')
        from .registry import default_registry
        from .instances import registry_from_public
        from .state_machine import _signature
        reg=registry_from_public(p)
        if any(r not in reg or _signature(reg[r])!=_signature(v) for r,v in default_registry().items()):
            raise ValueError('canonical registry differs from audited graph')
        if self._basis is not None:
            if self._basis!=basis: raise ValueError('inconsistent library basis')
            return
        # Exact precomputed public templates; no capacity or private inputs.
        from .instances import demand
        self.base_demand=np.array([[[demand(p,profile,level,0,'still')[k] for k in ('RAN','FH','EDGE')] for level in ('none','edge')] for profile in p.b2_profiles],dtype=np.float64)
        self.role_costs=np.zeros((4096,3),dtype=np.float64)
        self.execution_costs=np.zeros(4096,dtype=np.float64)
        roles=tuple(sorted(default_registry()))
        for mask in range(4096):
            selected=[reg[role] for i,role in enumerate(roles) if mask & (1<<i)]
            self.role_costs[mask]=[sum(x.resource_cost.get(k,0.) for x in selected) for k in ('RAN','FH','EDGE')]
            self.execution_costs[mask]=sum(x.execution_cost for x in selected)
        # Rich depth-one and no-structural B2 class sets were independently
        # precomputed with the availability bundle. No AST enumeration occurs
        # during library binding or per-instance execution.
        self.depth1=self.availability.entries[31].depth1
        self.structural=np.logical_not(self.availability.entries[0].generated)
        if np.count_nonzero(self.depth1)!=1539 or np.count_nonzero(~self.structural)!=27:
            raise ValueError('audited depth1/B2 inclusion failed')
        valid_ix=np.where(self.active,self.profiles,0)
        quality=np.array([x.quality for x in p.b2_profiles]); latency=np.array([1/(1+x.deadline) for x in p.b2_profiles])
        qhi=np.zeros(len(self.keys)); qlo=np.zeros(len(self.keys))
        lhi=np.zeros(len(self.keys)); llo=np.zeros(len(self.keys))
        for j in range(6):
            qhi,qlo=_compensated_add(qhi,qlo,np.where(self.active[:,j],quality[valid_ix[:,j]],0.))
            lhi,llo=_compensated_add(lhi,llo,np.where(self.active[:,j],latency[valid_ix[:,j]],0.))
        self.qsum=(qhi+qlo)/6; self.lsum=(lhi+llo)/6
        starts=[]
        for st in range(2): starts.append(np.where(self.active[:,st],0,np.where(self.active[:,st+2],1,np.where(self.active[:,st+4],2,3)))/3)
        self.delay=(starts[0]+starts[1])/2
        changes=np.zeros(len(self.keys),dtype=np.int8)
        complexity=np.zeros(len(self.keys),dtype=np.int8)
        for j in range(6):
            first=self.active[:,j].copy()
            for k in range(j): first &= ~(self.active[:,k] & (self.profiles[:,j]==self.profiles[:,k]) & (self.level[:,j]==self.level[:,k]))
            complexity += first
        for t in (1,2):
            for st in range(2):
                j=t*2+st; k=j-2
                equal=(~self.active[:,j] & ~self.active[:,k]) | (self.active[:,j] & self.active[:,k] & (self.profiles[:,j]==self.profiles[:,k]) & (self.level[:,j]==self.level[:,k]))
                changes += ~equal
        self.switch=changes/4; self.complexity=complexity/6
        # Behavior-based mechanism labels: 1 STATIC, 2 STATE_CONDITIONAL,
        # 4 DELAYED_START, 8 TEMPORAL_PHASED, 16 OFFLOAD, 32 HYBRID.
        labels=np.zeros(len(self.keys),dtype=np.uint8)
        same=np.all(self.cells==self.cells[:,0:1,:],axis=2)
        static=np.all(self.active,axis=1) & np.all(same,axis=1) & (self.level[:,0]==0)
        labels |= static.astype(np.uint8)
        conditional=np.zeros(len(self.keys),dtype=bool)
        phased=np.zeros(len(self.keys),dtype=bool)
        delayed=np.zeros(len(self.keys),dtype=bool)
        for t in range(3): conditional |= np.any(self.cells[:,2*t,:]!=self.cells[:,2*t+1,:],axis=1)
        for st in range(2):
            delayed |= ~self.active[:,st] & (self.active[:,st+2] | self.active[:,st+4])
            for t in (1,2):
                j=2*t+st;k=j-2
                phased |= self.active[:,j] & self.active[:,k] & np.any(self.cells[:,j,:]!=self.cells[:,k,:],axis=1)
        offload=np.any(self.active & (self.level==1),axis=1)
        labels |= conditional.astype(np.uint8)*2 | delayed.astype(np.uint8)*4 | phased.astype(np.uint8)*8 | offload.astype(np.uint8)*16
        multi=conditional.astype(np.uint8)+delayed.astype(np.uint8)+phased.astype(np.uint8)+offload.astype(np.uint8)
        labels |= (multi>=2).astype(np.uint8)*32
        self.mechanism_bits=labels
        # Publish the basis only after every derived array is complete.
        for value in vars(self).values():
            if isinstance(value,np.ndarray): value.flags.writeable=False
        self._basis=basis

    def witness(self, i, depth=2, *, evaluator):
        """Return a witness for this instance's capability-conditioned space."""
        return self.availability.for_evaluator(evaluator).witness(i, depth)

class FastEvaluator:
    def __init__(self,instance,library):
        scopes={'GENSPACE-FAIL-01-ENGINEERING':'engineering','GENSPACE-FAIL-01-ENGINEERING-SHADOW':'shadow','GENSPACE-FAIL-01-SMOKE':'smoke02','GENSPACE-FAIL-01-PILOT':'pilot-execution'}
        if instance.namespace not in scopes: raise RuntimeError('namespace not enabled')
        if instance.namespace in ('GENSPACE-FAIL-01-SMOKE','GENSPACE-FAIL-01-PILOT'):
            from .smoke_authorization import authorize
            authorize(instance.namespace)
        allowed = (scopes[instance.namespace],)
        if library.snapshot.get('execution_scope') not in allowed: raise RuntimeError('namespace and verified snapshot scope differ')
        from .execution_snapshot import verify_public_instance
        verify_public_instance(instance.public,library.snapshot)
        self.instance=instance; self.lib=library
        library.bind_public_basis(instance.public)
        self.reference=FastPublicCompatibility(instance.public)
        self.available_role_mask=sum((1<<i) for i,yes in enumerate(self.reference.available) if yes)

    def evaluate(self, phase_observer=None):
        # Instrumentation is observational only: callbacks receive a name,
        # never arrays or instance state. Their exceptions remain fail-closed.
        def event(name):
            if phase_observer is not None:
                phase_observer(name)
        lib=self.lib; p=self.instance.public; private=self.instance.private
        event('PUBLIC_FILTER_START')
        ts={}; begin=perf_counter(); count=len(lib.keys)
        depth=p.configuration['composition_depth']
        allowed=lib.depth1.copy() if depth==1 else np.ones(count,dtype=bool)
        # Graph is preverified V1; domain is depth membership. V2 is
        # evaluated before the encoded V3 status, preserving stage markers.
        missing_mask=np.uint16((~self.available_role_mask) & 0xFFF)
        v2_pass=allowed & ((lib.required_role_masks & missing_mask)==0)
        for i in range(len(self.reference.roles)):
            scope=lib.keys[:,1+2*i]; predicate=lib.keys[:,2+2*i]
            ok=(scope==255) | (self.reference.available[i] & ((scope & (~self.reference.supported[i] & 255))==0) & (predicate==self.reference.expected[i]))
            v2_pass &= ok
        v3_pass=v2_pass & (lib.keys[:,0]==1)
        public_ok=v3_pass
        event('PUBLIC_FILTER_END')
        ts['public_filter_s']=perf_counter()-begin; t=perf_counter()
        event('V4_START')
        # Exact public V4 short-circuit: once a capacity/hard check fails,
        # later guards cannot make that candidate feasible again. No private
        # value is consulted and all candidate status outputs remain present.
        live=np.flatnonzero(public_ok)
        vals=np.array([(x.quality,x.deadline,x.rate) for x in p.b2_profiles])
        surcharge=lib.role_costs; execution=lib.execution_costs
        capacities=np.array([self.reference.capacities[(t,s)] for t in range(3) for s in p.states])
        sums=[np.zeros(count) for _ in range(3)]; residuals=[np.zeros(count) for _ in range(3)]
        exsum=np.zeros(count); exres=np.zeros(count)
        edge_bit=1<<self.reference.role_index['reserve_edge_compute']
        c=p.public_constraints
        for j in range(6):
            if not live.size: break
            active=lib.active[live,j]
            idx=np.where(active,lib.profiles[live,j],0); q=vals[idx,0]; deadline=vals[idx,1]
            off=lib.level[live,j]==1
            mask=lib.role_masks[live,j]; sur=surcharge[mask]
            templates=lib.base_demand[idx,off.astype(np.uint8)]
            loads=(templates[:,0]+sur[:,0],templates[:,1]+sur[:,1],templates[:,2]+sur[:,2])
            passed=np.ones(live.size,dtype=bool)
            for k in range(3):
                passed &= (~active) | (np.isfinite(loads[k]) & (loads[k]>=0) & (loads[k]<=capacities[j,k]))
            passed &= (~active) | ((deadline<=c['max_deadline']) & (q>=c['min_quality']))
            passed &= (~active) | (loads[2]==0) | ((mask & edge_bit)!=0)
            kept=live[passed]; kept_active=active[passed]
            for k in range(3):
                hi,lo=_compensated_add(sums[k][kept],residuals[k][kept],np.where(kept_active,loads[k][passed],0.))
                sums[k][kept]=hi; residuals[k][kept]=lo
            hi,lo=_compensated_add(exsum[kept],exres[kept],np.where(kept_active,execution[mask[passed]],0.))
            exsum[kept]=hi; exres[kept]=lo
            live=kept
        ok=np.zeros(count,dtype=bool)
        if live.size:
            hard_active=np.sum(lib.active[live],axis=1)>=c['min_active_slots']
            ok[live[hard_active]]=True
        event('V4_END')
        ts['physical_s']=perf_counter()-t; t=perf_counter()
        event('V5_START')
        # Private input is first inspected at V5, never during generation,
        # eligibility or the public hard-constraint checks above.
        from .execution_snapshot import verify_private_preferences
        verify_private_preferences(private)
        a=private.application; n=private.network
        # V5 is reached only after all public/physical checks pass.
        ii=np.flatnonzero(ok)
        aa=(a['quality_weight']*lib.qsum[ii]+a['latency_weight']*lib.lsum[ii]+a['start_delay_weight']*(1-lib.delay[ii])+a['switching_penalty']*(1-lib.switch[ii]))/sum(a[k] for k in ('quality_weight','latency_weight','start_delay_weight','switching_penalty'))
        nn=1-(n['ran_cost']*((sums[0][ii]+residuals[0][ii])/6)+n['fh_cost']*((sums[1][ii]+residuals[1][ii])/6)+n['edge_cost']*((sums[2][ii]+residuals[2][ii])/6)+n['policy_complexity_cost']*lib.complexity[ii]+n['actuation_switching_cost']*lib.switch[ii])/sum(n[k] for k in ('ran_cost','fh_cost','edge_cost','policy_complexity_cost','actuation_switching_cost'))-(exsum[ii]+exres[ii])/6
        aa=np.clip(aa,0,1); nn=np.clip(nn,0,1)
        au=np.full(count,np.nan); nu=np.full(count,np.nan); nash=np.full(count,np.nan)
        au[ii]=aa; nu[ii]=nn; nash[ii]=aa*nn
        accepted=np.zeros(count,dtype=bool)
        accepted[ii]=(aa>=a['reservation']) & (nn>=n['reservation'])
        event('V5_END')
        ts['utility_s']=perf_counter()-t; t=perf_counter()
        # Lexical representatives are capability-conditioned: the globally
        # smallest rich-grammar witness may use an unavailable constructor.
        variant=lib.availability.for_evaluator(self)
        ids=np.flatnonzero(accepted & variant.mask(depth)); winner=None
        if ids.size:
            top=np.max(nash[ids]); ties=ids[nash[ids]==top]
            winner=int(min(ties,key=lambda i:variant.tie_key(i,depth)))
        event('REPRESENTATIVE_SELECTED')
        ts['selection_s']=perf_counter()-t
        # Utilities and Nash are undefined unless public and physical checks pass.
        return Evaluation(public_ok,ok,au,nu,accepted,nash,winner,ts,allowed,v2_pass,v3_pass)

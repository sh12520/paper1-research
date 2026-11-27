"""ENGINEERING-only timing of packed depth-two graph; not an exactness proof.

The caller must independently validate graph completeness and fingerprint. This
module refuses research namespaces. No private value enters graph construction
or public filtering. Measurements are not scientific observations.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, statistics, struct
from time import perf_counter
from pathlib import Path
from .compact_semantics import CompactEncoder, SCOPES
from .instances import generate_instance, demand, utilities, hard_check, registry_from_public
from .registry import default_registry
from .state_machine import bind_capabilities, _signature
from .enumeration import candidates, syntax_key
from .state_machine import verify_instance

NAMESPACE = 'GENSPACE-FAIL-01-ENGINEERING'


def read_graph(path):
    """Read serialized graph in one pass, with strict format and truncation checks."""
    with gzip.open(path,'rb') as f:
        if f.read(4)!=b'GSG1': raise ValueError('invalid graph magic')
        hdr=f.read(4)
        if len(hdr)!=4: raise ValueError('truncated header')
        size=struct.unpack('>I',hdr)[0]
        raw=f.read(size)
        if len(raw)!=size: raise ValueError('truncated header payload')
        header=json.loads(raw)
        if header.get('format')!='GENSPACE-GRAPH-v1' or header.get('key_bytes')!=49:
            raise ValueError('unsupported graph')
        entries=[]
        while True:
            record=f.read(56)
            if not record: break
            if len(record)!=56: raise ValueError('truncated graph record')
            entries.append((record[:49],record[49:]))
    return header, entries


def render_token(token, header):
    op_id,param_id,left,right=struct.unpack('>BHHH',token)
    op=header['operators'][op_id]; param=header['parameters'][param_id]
    if op=='Static': return param
    out='['+json.dumps(op)+','+param+','+header['pool'][left]
    if right!=65535: out+=','+header['pool'][right]
    return out+']'


class PackedEvaluator:
    def __init__(self, instance):
        if instance.namespace!=NAMESPACE: raise ValueError('engineering namespace required')
        self.instance=instance; self.p=instance.public
        self.enc=CompactEncoder(self.p); self.reg=registry_from_public(self.p)
        if self.p.horizon!=3 or self.p.states!=('still','moving') or not self.enc.all_predicates_true:
            raise ValueError('packed evaluator requires the fixed positive-predicate 3x2 domain')
        self.roles=self.enc.roles; self.bindings={r:bind_capabilities({r},self.p.capabilities,self.reg) for r in self.roles}
        ref=default_registry(); self.expected=[]; self.supported=[]; self.available=[]
        for role in self.roles:
            item=self.reg[role]; match=self.bindings[role]
            self.available.append(bool(match) and _signature(item)==_signature(ref[role]))
            self.expected.append((1<<len(item.preconditions))-1)
            mask=sum(1<<i for i,s in enumerate(SCOPES) if s in item.supported_scope)
            self.supported.append(mask)
        self.capacities={(t,s):(a,b,c) for t,s,a,b,c in self.p.capacity}
        self.offset=1+2*len(self.roles); self.cost_cache={}

    def public_filter(self,key):
        """V1/V2 check, using only public data and packed footprint."""
        if len(key)!=49 or key[0]!=1: return False
        for i in range(len(self.roles)):
            scope=key[1+2*i]
            if scope==255: continue
            if not self.available[i] or scope & ~self.supported[i] or key[2+2*i]!=self.expected[i]: return False
        return True

    def role_cost(self,mask):
        if mask not in self.cost_cache:
            roles=[self.reg[r] for i,r in enumerate(self.roles) if mask & (1<<i)]
            self.cost_cache[mask]=({k:sum(c.resource_cost.get(k,0.) for c in roles) for k in ('RAN','FH','EDGE')},sum(c.execution_cost for c in roles))
        return self.cost_cache[mask]

    def physical(self,key):
        """V3/V4 checks and complete per-cell utility inputs; no private access."""
        p=self.p; actions=[]; costs={}; executions={}
        for cell in range(6):
            off=self.offset+4*cell; pi=key[off]
            if pi==255: continue
            if pi>=len(p.b2_profiles) or key[off+1] not in (0,1): return None
            level='edge' if key[off+1] else 'none'
            rolemask=(key[off+2]<<8)|key[off+3]
            t=cell//2; state=p.states[cell%2]; profile=p.b2_profiles[pi]
            surcharge,execution=self.role_cost(rolemask)
            load=demand(p,profile,level,t,state); cap=self.capacities.get((t,state))
            if cap is None or any(load[k]+surcharge[k]>cap[i] for i,k in enumerate(('RAN','FH','EDGE'))): return None
            if surcharge['EDGE']+load['EDGE'] and not (rolemask & (1<<self.enc.role_index['reserve_edge_compute'])): return None
            actions.append((t,state,profile,level)); costs[t,state]=surcharge; executions[t,state]=execution
        actions=tuple(actions)
        if not hard_check(p,actions): return None
        return actions,costs,executions

    def acceptance(self,physical):
        actions,costs,executions=physical
        a,n=utilities(self.p,self.instance.private,actions,cell_surcharges=costs,cell_execution_costs=executions)
        accepted=a>=self.instance.private.application['reservation'] and n>=self.instance.private.network['reservation']
        return accepted,a,n


def make_fixtures():
    return [generate_instance(('F1','F2','F3','F4')[i%4],
        {'resource_pressure':('low','medium','high')[i%3], 'preference_conflict':('medium','high')[i%2],
         'capability_richness':('rich','sparse')[i%2], 'composition_depth':2},
        'depth2-performance-fixture-'+str(i),namespace=NAMESPACE) for i in range(20)]


def run(graph_path, max_candidates=None, max_fixtures=20):
    before=perf_counter(); header, entries=read_graph(graph_path); load_seconds=perf_counter()-before
    if max_candidates is not None: entries=entries[:max_candidates]
    instances=make_fixtures()[:max_fixtures]
    rows=[]
    for instance in instances:
        evaluator=PackedEvaluator(instance); public_seconds=physical_seconds=private_seconds=0.; winner=None; surviving=0
        started=perf_counter()
        for key,token in entries:
            s=perf_counter(); passed=evaluator.public_filter(key); public_seconds+=perf_counter()-s
            if not passed: continue
            s=perf_counter(); physical=evaluator.physical(key); physical_seconds+=perf_counter()-s
            if physical is None: continue
            s=perf_counter(); accepted,a,n=evaluator.acceptance(physical)
            if accepted:
                rank=(-a*n,render_token(token,header)); surviving+=1
                if winner is None or rank<winner: winner=rank
            private_seconds+=perf_counter()-s
        o1=perf_counter()-started
        paired_start=perf_counter()
        for method in ('B0','B1','B2'):
            best=None
            for node in candidates(method,instance.public,2):
                result=verify_instance(node,instance,2)
                if result.verified:
                    rank=(-result.application_utility*result.network_utility,syntax_key(node))
                    if best is None or rank<best: best=rank
        baseline=perf_counter()-paired_start
        rows.append({'public_filter_s':public_seconds,'v3_v4_s':physical_seconds,'v5_and_selection_s':private_seconds,
                     'o1_total_s':o1,'baseline_b0_b1_b2_s':baseline,'paired_total_s':o1+baseline,
                     'instance_hash':instance.instance_hash})
    return {'purpose':'engineering performance only; no research outcomes', 'namespace':NAMESPACE,
        'graph_path':str(Path(graph_path).resolve()), 'graph_sha256':hashlib.sha256(Path(graph_path).read_bytes()).hexdigest(),
        'graph_load_seconds':load_seconds,'fixture_count':len(rows),'semantic_records_loaded':len(entries),
        'complete':max_candidates is None and len(rows)==20,'rows':rows,
        'o1_median_seconds':statistics.median(x['o1_total_s'] for x in rows) if rows else None}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('graph'); parser.add_argument('--candidate-limit',type=int); parser.add_argument('--fixture-limit',type=int,default=20)
    args=parser.parse_args(); print(json.dumps(run(args.graph,args.candidate_limit,args.fixture_limit),indent=2))

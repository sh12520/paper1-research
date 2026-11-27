"""Timing-only replay of original V1 methods on existing serialized instances.

Never calls instance or seed generators. Outputs go only to this audit folder.
The transformed make_plan is created in memory, has timing marks only, and is
compared against the original output for each replayed instance.
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, hashlib, json, os, threading, time
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'results' / 'method_dev_v1'
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(BASE)]
import numpy as np
import public_search as search
import private_protocol as protocol
import runtime
from src.instances import deserialize_instance
import src.instances as instance_module
from src.fast_exact import FastLibrary
from src.fast_runner import _decode_witness
from src.state_machine import verify_instance
from tools.smoke_01 import memory_status, process_memory

def forbidden(*args, **kwargs):
    raise RuntimeError('generation of instance or seed is forbidden in this audit')
instance_module.derive_seed = forbidden
instance_module.generate_instance = forbidden

class Clock:
    def __init__(self): self.sums=defaultdict(float); self.name=None; self.last=0.
    def mark(self,name):
        now=time.perf_counter()
        if self.name is not None: self.sums[self.name]+=now-self.last
        self.name=name; self.last=now
    def wrap(self,name,fn):
        def call(*args,**kwargs):
            t=time.perf_counter()
            try: return fn(*args,**kwargs)
            finally: self.sums[name]+=time.perf_counter()-t
        return call

def instrument_plan(clock):
    # No semantic changes: insert only timing calls at pre-existing statement
    # boundaries in an in-memory copy of the actual development implementation.
    source=(BASE/'public_search.py').read_text(encoding='utf8')
    source=source[source.index('def make_plan('):]
    replacements=[
        ("    started=time.perf_counter();baseline=", "    _clock.mark('plan_public_setup')\n    started=time.perf_counter();baseline="),
        ("    bits=group_bits(library);universe=", "    _clock.mark('conditioning')\n    bits=group_bits(library);universe="),
        ("    probe_start=time.perf_counter()", "    _clock.mark('mechanism_probes')\n    probe_start=time.perf_counter()"),
        ("    probe_end=time.perf_counter();ids=", "    _clock.mark('conditioning')\n    probe_end=time.perf_counter();ids="),
        ("        v,m,q,cost=_proxy(view,library,ids)", "        _clock.mark('feature_calculation')\n        v,m,q,cost=_proxy(view,library,ids)\n        _clock.mark('proxy_score_calculation')"),
        ("        ranked=np.lexsort((ids,score));", "        _clock.mark('sorting_topk')\n        ranked=np.lexsort((ids,score));"),
        ("    mech=tuple(sorted(", "    _clock.mark('stage_construction')\n    mech=tuple(sorted("),
        ("    return Plan(ordered,sig,", "    _clock.mark(None)\n    return Plan(ordered,sig,")]
    for before,after in replacements:
        if source.count(before)!=1: raise ValueError('V1 source changed: '+before)
        source=source.replace(before,after)
    ns=dict(search.__dict__);ns['_clock']=clock
    exec(compile(source,str(BASE/'public_search.py')+':timed-copy','exec'),ns)
    return ns['make_plan']

def normalized(x):
    if isinstance(x,dict):
        ignored={'elapsed_seconds','public_probe_seconds','public_setup_seconds','public_ranking_seconds'}
        return {str(k):normalized(v) for k,v in x.items() if k not in ignored}
    if isinstance(x,list): return [normalized(v) for v in x]
    return x

def fixed_public_signatures(plan):
    return (plan.order.tobytes(),plan.signature,plan.mechanism_order,plan.path,
            plan.probe_count,plan.relief,plan.stages,plan.public_ranked_count,
            plan.pair_complementarity,plan.b2_proxy_count)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=96);ap.add_argument('--only',default=None)
    ap.add_argument('--tag',required=True);a=ap.parse_args()
    if not a.tag.replace('-','').replace('_','').isalnum(): raise ValueError('unsafe tag')
    for _ in range(3):
        if memory_status()[1]<2048*1048576: raise RuntimeError('PAUSED_MEMORY: prelaunch < 2 GiB')
        time.sleep(.2)
    stop=threading.Event(); sample={'min_available':memory_status()[1],'peak_rss':0,'emergency':False}
    def watch():
        while not stop.wait(.25):
            available=memory_status()[1];sample['min_available']=min(sample['min_available'],available)
            try: sample['peak_rss']=max(sample['peak_rss'],process_memory(os.getpid())[1])
            except OSError: pass
            if available<768*1048576:
                sample['emergency']=True
                os._exit(75)
    threading.Thread(target=watch,daemon=True).start()
    plan=json.loads((ROOT/'PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8'))['instances']
    slots=[x for x in plan if x['seed_index']==0][:a.limit]
    if a.only:
        slots=[x for x in plan if x['instance_id']==a.only]
        if len(slots)!=1: raise ValueError('unknown instance ID')
    manifest=json.loads((ROOT/'results/pilot/instances_manifest.json').read_text(encoding='utf8'))
    library=FastLibrary.from_graph(scope='pilot-execution');initialized=False
    fields=['instance_id','family','resource_pressure','preference_conflict','capability_richness','composition_depth',
            'target','method','public_view_setup','plan_public_setup','conditioning','feature_calculation',
            'proxy_score_calculation','sorting_topk','mechanism_probes','stage_construction','exact_verification',
            'bilateral_protocol','representative_reconstruction','residual','total','plan_equality','output_equality']
    destination=OUT/('runtime_'+a.tag+'.csv')
    with destination.open('x',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for slot in slots:
            if memory_status()[1]<768*1048576: raise RuntimeError('PAUSED_MEMORY emergency')
            iid=slot['instance_id'];raw=(ROOT/'results/pilot/instances'/f'{iid}.json').read_bytes()
            instance=deserialize_instance(raw.decode())
            identity={'sha256':hashlib.sha256(raw).hexdigest(),'instance_hash':instance.instance_hash,
                      'public_hash':instance.public_hash,'private_hash':instance.private_hash}
            if identity!=manifest[iid]:raise ValueError('input hash mismatch '+iid)
            prior=json.loads((BASE/'run_protocol_fixed'/iid/'record.json').read_text(encoding='utf8'))
            if not initialized:
                library.bind_public_basis(runtime.verification_public(instance.public));initialized=True
            for method in ('FLAT-FEASIBILITY','DG-PCE'):
                clock=Clock()
                # Reconstruct the public plan independently before the timed
                # run only when expansion is needed, and compare afterwards.
                plan_pairs=[]; instrumented=instrument_plan(clock)
                def plan_wrapper(*args,**kw):
                    result=instrumented(*args,**kw);plan_pairs.append((args,kw,result));return result
                old_plan,old_group,old_negotiate=runtime.make_plan,runtime.group_bits,runtime.negotiate
                old_init,old_prepare,old_verify,old_witness=(protocol.PublicVerifier.__init__,protocol.PublicVerifier.prepare_batch,
                    protocol.PublicVerifier.verify,protocol.PublicVerifier._agreement_witness)
                runtime.make_plan=plan_wrapper
                runtime.group_bits=clock.wrap('conditioning',old_group)
                runtime.negotiate=clock.wrap('bilateral_protocol',old_negotiate)
                protocol.PublicVerifier.__init__=clock.wrap('exact_verification',old_init)
                protocol.PublicVerifier.prepare_batch=clock.wrap('exact_verification',old_prepare)
                protocol.PublicVerifier.verify=clock.wrap('exact_verification',old_verify)
                protocol.PublicVerifier._agreement_witness=clock.wrap('representative_reconstruction',old_witness)
                start=time.perf_counter()
                try:
                    t=time.perf_counter();pub=runtime.verification_public(instance.public);view=search.sanitize_public(instance.public)
                    variant=runtime.choose_variant(pub,library)
                    app=protocol.PrivateAgent('application',pub,instance.private.application)
                    net=protocol.PrivateAgent('network',pub,instance.private.network)
                    clock.sums['public_view_setup']+=time.perf_counter()-t
                    outputs,history=runtime.run(view,pub,variant,app,net,library,method,stop_budget=5000)
                    total=time.perf_counter()-start
                finally:
                    runtime.make_plan, runtime.group_bits,runtime.negotiate=old_plan,old_group,old_negotiate
                    protocol.PublicVerifier.__init__,protocol.PublicVerifier.prepare_batch=old_init,old_prepare
                    protocol.PublicVerifier.verify,protocol.PublicVerifier._agreement_witness=old_verify,old_witness
                old=prior['methods'][method]
                # Same offline verifier as the original harness. This is not
                # included in the online method timings and is never supplied
                # to the candidate ordering or bilateral protocol.
                for out in outputs.values():
                    if out['agreement']:
                        v=verify_instance(_decode_witness(json.loads(out['representative'])),instance,view.depth)
                        if not v.verified: raise ValueError('agreement failed offline witness verification')
                        out.update({'uA':v.application_utility,'uN':v.network_utility,
                                    'nash':v.application_utility*v.network_utility})
                # Original historical run continues to 10,000; the 5,000
                # checkpoint stores the cumulative proposal count. Every
                # proposal contributes exactly PROPOSE + ACCEPT/REJECT.
                proposal_count=outputs[5000]['proposals']
                expected_history=old['history'][:2*proposal_count]
                if len(expected_history)!=2*proposal_count or sum(x['message']=='PROPOSE' for x in expected_history)!=proposal_count:
                    raise ValueError('historical protocol history is not paired')
                expected_budgets={k:v for k,v in old['budgets'].items() if int(k)<=5000}
                eq=normalized({'budgets':outputs,'history':history})==normalized({'budgets':expected_budgets,'history':expected_history})
                if not eq: raise ValueError('non-timing result mismatch '+iid+' '+method)
                for args,kw,timed_plan in plan_pairs:
                    plain=search.make_plan(*args,**kw)
                    if fixed_public_signatures(timed_plan)!=fixed_public_signatures(plain):
                        raise ValueError('timed plan differs from original '+iid+' '+method)
                components={k:clock.sums[k] for k in fields[8:19]}
                row={'instance_id':iid,'family':slot['family'],**slot['configuration'],
                     'target':prior['oracle']['recoverable'],'method':method,**components,'total':total,
                     'residual':total-sum(components.values()),
                     'plan_equality':'PASS' if plan_pairs else 'NOT_APPLICABLE_B2_STOP',
                     'output_equality':True}
                if row['residual'] < -0.002:raise ValueError('overlapping phase timings')
                writer.writerow(row);f.flush()
                print(json.dumps({'instance_id':iid,'method':method,'total':total},ensure_ascii=False),flush=True)
    stop.set();(OUT/('runtime_'+a.tag+'_memory.json')).write_text(json.dumps(sample,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()

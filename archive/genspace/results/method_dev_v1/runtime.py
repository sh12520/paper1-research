"""Shared non-oracular development execution over pre-existing instances.

Public search receives only its sanitized allowlist; private preferences are
passed individually to local agents. Exact candidate checks are all charged,
including 27 B2 checks. B2 agreement stops expansion in every method.
"""
from __future__ import annotations
from types import SimpleNamespace
from time import perf_counter
import numpy as np
from src.fast_exact import FastPublicCompatibility
from private_protocol import PublicVerifier,PrivateAgent,negotiate
from public_search import sanitize_public,make_plan,group_bits

BUDGETS=(100,500,1000,5000,10000)
CHUNK=16
SINGLETON_QUOTA=128
PAIR_QUOTA=1600
ROUND_LIMIT=10000
_PUBLIC=('horizon','states','capacity','m0_profiles','mr_profiles','b2_profiles','capabilities',
         'conditions','durations','offsets','intervals','offload_levels','public_constraints',
         'resource_parameters','registry','model_config_hash')

def verification_public(public):
    """Create a public-only allowlist; no family or configuration object."""
    return SimpleNamespace(**{k:getattr(public,k) for k in _PUBLIC})

def choose_variant(public,library):
    return library.availability.for_evaluator(SimpleNamespace(reference=FastPublicCompatibility(public)))

def run(view, public, variant, app, net, library, method, budgets=BUDGETS, *, stop_budget=10000):
    """Method entry receives no instance, family label, hash, or preferences."""
    if tuple(budgets)!=BUDGETS:raise ValueError('fixed budget checkpoints required')
    if stop_budget not in BUDGETS:raise ValueError('stop_budget must be a fixed checkpoint')
    budgets=tuple(b for b in budgets if b<=stop_budget)
    if method not in ('B2','RANDOM-BUDGET','FLAT-FEASIBILITY','GLOBAL-FREQUENCY','SINGLETON-ONLY','DG-PCE'):
        raise ValueError('method')
    started=perf_counter(); depth=view.depth
    verifier=PublicVerifier(public,variant,depth,max(budgets),library)
    bits=group_bits(library); static=np.flatnonzero(variant.mask(depth)&(bits==0))
    if len(static)!=27:raise ValueError('B2 semantic domain mismatch')
    pool=[];history=[];path=[];solutions={};plan=None;winner=None;stage_stats=[];stop_reason=None
    for i in range(0,len(static),CHUNK):
        part=static[i:i+CHUNK];verifier.prepare_batch(part)
        for cid in part:
            e=verifier.verify(int(cid))
            if e is not None:pool.append(e)
    b2_feasible=len(pool)
    stage_stats.append({'stage':'B2','available':27,'quota':27,'verified':27,'public_feasible':b2_feasible,'cap_hit':False})
    winner,history=negotiate(pool,app,net,max_rounds=ROUND_LIMIT,history=history)
    b2_agreement=winner is not None
    def record(b,solution):
        return {'budget':b,'agreement':solution is not None,'class_id':None if solution is None else solution.class_id,
                'representative':None if solution is None else solution.witness,
                'selected_group_mask':None if solution is None else int(bits[solution.class_id]),
                'verification_calls':verifier.calls,'b2_verification_calls':27,
                'batch_calls':verifier.batch_calls,'batch_candidate_checks':verifier.batch_candidate_checks,
                'state_machine_calls':verifier.state_machine_calls,
                'public_feasible_b2':b2_feasible,'public_feasible_candidates':len(pool),
                'stages':[dict(x) for x in stage_stats],
                'proposals':sum(e['message']=='PROPOSE' for e in history),
                'rounds':sum(e['message']=='PROPOSE' for e in history),
                'path':list(path),'first_mechanism':None if plan is None or not plan.mechanism_order else plan.mechanism_order[0],
                'public_probe_count':0 if plan is None else plan.probe_count,
                'public_ranked_count':0 if plan is None else plan.public_ranked_count,
                'b2_proxy_count':0 if plan is None else plan.b2_proxy_count,
                'public_probe_seconds':0. if plan is None else plan.probe_seconds,
                'public_setup_seconds':0. if plan is None else plan.public_setup_seconds,
                'public_ranking_seconds':0. if plan is None else plan.public_ranking_seconds,
                'termination_reason':('agreement' if solution is not None else ('budget_exhausted' if verifier.calls>=b else (stop_reason or 'candidate_exhaustion'))),
                'elapsed_seconds':perf_counter()-started,'b2_agreement':b2_agreement}
    if winner is not None or method=='B2':
        return {b:record(b,winner) for b in budgets},history
    plan=make_plan(view,library,variant,b2_feasible,method,budget=max(budgets))
    position=0;stage=0;stage_left=0;stage_label=None;stage_used=0
    while verifier.calls<max(budgets) and winner is None:
        if sum(e['message']=='PROPOSE' for e in history)>=ROUND_LIMIT:
            stop_reason='round_limit';break
        while stage_left==0:
            if stage>=len(plan.stages):break
            stage_label,stage_len=plan.stages[stage];stage+=1
            quota=(SINGLETON_QUOTA if '+' not in stage_label else PAIR_QUOTA) if method in ('DG-PCE','GLOBAL-FREQUENCY','SINGLETON-ONLY') else stage_len
            stage_left=min(stage_len,quota);stage_used=stage_len
            path.append(stage_label)
            stage_stats.append({'stage':stage_label,'available':stage_len,'quota':quota,'verified':0,'public_feasible':0,'cap_hit':False})
        if stage_left==0:break
        next_budget=next(b for b in budgets if b>verifier.calls)
        n=min(CHUNK,stage_left,next_budget-verifier.calls)
        part=plan.order[position:position+n];verifier.prepare_batch(part)
        for cid in part:
            e=verifier.verify(int(cid))
            stage_stats[-1]['verified']+=1
            if e is not None:pool.append(e);stage_stats[-1]['public_feasible']+=1
        position+=n;stage_left-=n;stage_used-=n
        proposal_count=sum(e['message']=='PROPOSE' for e in history)
        if proposal_count>=ROUND_LIMIT:stop_reason='round_limit';break
        winner,history=negotiate(pool,app,net,max_rounds=ROUND_LIMIT-proposal_count,history=history)
        if stage_left==0:
            stage_stats[-1]['cap_hit']=stage_used>0
            position+=stage_used
        if verifier.calls in budgets:solutions[verifier.calls]=record(verifier.calls,winner)
    # Candidate exhaustion can occur before the next budget.  No further calls
    # occur at larger budgets, so the terminal result is their actual outcome.
    if stop_reason is None:
        stop_reason='agreement' if winner is not None else ('budget_exhausted' if verifier.calls>=max(budgets) else 'candidate_exhaustion')
    for b in budgets:
        if b not in solutions:solutions[b]=record(b,winner)
    return solutions,history

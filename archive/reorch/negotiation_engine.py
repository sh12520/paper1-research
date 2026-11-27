import itertools
import json
from types import SimpleNamespace
from coupling import coupling_score
from policies import POLICIES

NAMES={'ALL_SEQUENTIAL':'B0','ALL_CONCURRENT':'B1','STATIC_CLUSTER':'B2',
 'OPTIMAL_STATIC_PARTITION':'B3','ONLINE_SEQUENTIAL_RESCHEDULE':'B4','RUNTIME_REPARTITION_ORACLE':'O1'}

def fits(ledger, demand, capacity):
    return all(x+y <= c+1e-9 for x,y,c in zip(ledger,demand,capacity))

def joint_offer(state, group):
    group=tuple(sorted(group))
    cache=getattr(state,'_offer_cache',None)
    if cache is not None and group in cache:
        return cache[group].copy()
    order=sorted(group,key=lambda s:(state.deadlines[s],s))
    best=None; result={}
    # None permits a feasible subset when there is no feasible full-group offer.
    for choices in itertools.product(*[list(range(state.indices[s],3))+[None] for s in group]):
        assigned={s:k for s,k in zip(group,choices) if k is not None}
        demand=[sum(state.profiles[s][k].demand[j] for s,k in assigned.items()) for j in range(3)]
        if not fits(state.ledger,demand,state.capacity): continue
        key=(len(assigned),-sum(state.profiles[s][k].rank for s,k in assigned.items()),
             tuple(-assigned.get(s,4) for s in order))
        if best is None or key>best: best=key; result=assigned
    if cache is not None: cache[group]=result.copy()
    return result

def evaluate_partition(state, partition):
    # Public, current-state one-step proxy; not a clairvoyant or proven upper bound.
    proposals=[(g,joint_offer(state,g)) for g in partition]
    cost=max((1+state.kappa*(len(g)-1) for g in partition),default=0)
    ledger=list(state.ledger); score=0.
    for group,offers in sorted(proposals,key=lambda x:min((state.deadlines[s] for s in x[0]), default=float('inf'))):
        demand=[sum(state.profiles[s][k].demand[j] for s,k in offers.items()) for j in range(3)]
        if fits(ledger,demand,state.capacity):
            ledger=[x+y for x,y in zip(ledger,demand)]
            for s,k in offers.items():
                slack=max(.1,state.deadlines[s]-state.time)
                score += 1.0 - .06*k + .35/slack
    return score - .12*cost

def simulate(instance, policy_name, kappa):
    key=NAMES.get(policy_name,policy_name); policy=POLICIES[key]()
    active=set(instance.profiles); ledger=[0.,0.,0.]; committed={}; indices={s:0 for s in active}
    time=0.; rounds=0; messages=0; rejected=0; ph=[]; ch=[]; missed=set()
    while active:
        expired={s for s in active if instance.deadlines[s]<=time+1e-9}
        active-=expired; missed|=expired
        if not active: break
        state=SimpleNamespace(active=tuple(sorted(active)), deadlines=instance.deadlines, time=time,
            ledger=tuple(ledger), profiles=instance.profiles, indices=indices.copy(), kappa=kappa,
            capacity=instance.capacity, history=ph, initial_partition=None, _offer_cache={})
        partition=policy.select(state)
        if not partition: raise RuntimeError('Policy returned empty partition with active sessions')
        flat=[s for g in partition for s in g]
        if len(flat)!=len(set(flat)) or any(s not in active for s in flat): raise ValueError('Invalid partition')
        dt=max(1+kappa*(len(g)-1) for g in partition)
        offers=[(tuple(g),joint_offer(state,g)) for g in partition]
        ph.append({'time':round(time,4),'groups':[list(g) for g in partition]})
        time=round(time+dt,9); rounds+=sum(len(g) for g in partition); messages+=2*sum(len(g) for g in partition)
        accepted=[]
        for group, offer in offers:
            accept={}
            for s,k in offer.items():
                indices[s]=max(indices[s],k)
                if time>instance.deadlines[s]+1e-9: continue
                frac=min(1.,time/instance.deadlines[s])
                threshold=instance.aspiration_start[s]+frac*(instance.reservation[s]-instance.aspiration_start[s])
                if instance.utilities[s][k]>=threshold: accept[s]=k
            if accept: accepted.append(accept)
        pairs={}
        for a,b in itertools.combinations(sorted(active),2):
            pairs[a+'-'+b]=round(coupling_score(instance.profiles[a][indices[a]],instance.profiles[b][indices[b]],instance.capacity,instance.deadlines[a],instance.deadlines[b],time),6)
        ch.append({'time':round(time,4),'profiles':indices.copy(),'edges':pairs})
        for group in sorted(accepted,key=lambda g:(min(instance.deadlines[s] for s in g),sorted(g))):
            demand=[sum(instance.profiles[s][k].demand[j] for s,k in group.items()) for j in range(3)]
            if fits(ledger,demand,instance.capacity):
                ledger=[x+y for x,y in zip(ledger,demand)]
                for s,k in group.items(): committed[s]=k; active.remove(s)
            else:
                rejected+=len(group)
                for s,k in group.items(): indices[s]=min(2,k+1)
        expired={s for s in active if instance.deadlines[s]<=time+1e-9}
        active-=expired; missed|=expired
    out={'seed':instance.seed,'family':instance.family,'strength':instance.strength,'tightness':instance.tightness,'kappa':kappa,'policy':key,
         'welfare':sum(instance.utilities[s][k] for s,k in committed.items()),'completion_rate':len(committed)/len(instance.profiles),
         'deadline_miss_rate':len(missed)/len(instance.profiles),'wall_time':time,'rounds':rounds,'messages':messages,'rejected_at_commit':rejected,
         'partition_history':json.dumps(ph,separators=(',',':')),'coupling_history':json.dumps(ch,separators=(',',':')),
         'committed_portfolio':json.dumps(committed,sort_keys=True),'final_ledger':json.dumps(ledger)}
    out.update({'agreement_'+s:int(s in committed) for s in instance.profiles})
    return out

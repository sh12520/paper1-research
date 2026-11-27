import random
from models import Instance, Profile

CANONICAL = {
 'A': ([(50,45,10),(38,32,22),(25,20,38)], [1,.90,.78]),
 'B': ([(45,40,12),(35,30,18),(25,22,24)], [1,.90,.80]),
 'C': ([(12,10,50),(10,10,38),(8,8,28)], [1,.92,.84]),
 'D': ([(30,35,5),(20,25,5),(15,18,5)], [1,.88,.78]),
}

def generate_instance(seed, family, strength, tightness):
    rng = random.Random(seed)
    cap=(100.,100.,100.)
    f={'loose':1.3,'medium':1.,'tight':.72}[tightness]
    shift={'weak':.25,'medium':.6,'strong':1.}[strength]
    deadlines={}; profiles={}; utilities={}; reservation={}; aspiration_start={}
    for name, (demands, utils) in CANONICAL.items():
        scale=[rng.uniform(.95,1.05) for _ in range(3)]
        base=demands[0]
        pp=[]
        for k, d in enumerate(demands):
            ratio=sum(d)/sum(base)
            proportional=[x*ratio for x in base]
            alpha=shift if family=='COUPLING_SHIFT' else 0.
            vec=tuple(round((proportional[j]*(1-alpha)+d[j]*alpha)*scale[j],3) for j in range(3))
            pp.append(Profile(vec,k))
        profiles[name]=tuple(pp)
        jitter=rng.uniform(-.025,.025)
        utilities[name]=tuple(round(u+jitter,5) for u in utils)
        reservation[name]=rng.uniform(.72,.80)
        aspiration_start[name]=rng.uniform(1.04,1.13)+jitter
        deadlines[name]=round({'A':10,'B':12,'C':8,'D':6}[name]*f*rng.uniform(.93,1.07),3)
    return Instance(seed,family,strength,tightness,cap,profiles,utilities,deadlines,reservation,aspiration_start)

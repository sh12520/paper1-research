import math

def coupling_score(p, q, capacity, deadline1, deadline2, time=0):
    # Capacity-normalized weighted cosine, multiplied by overlap and pressure.
    a=[x/c for x,c in zip(p.demand,capacity)]
    b=[x/c for x,c in zip(q.demand,capacity)]
    dot=sum(x*y for x,y in zip(a,b))
    cosine=dot/(math.sqrt(sum(x*x for x in a)*sum(y*y for y in b)) or 1)
    overlap=max(0,min(deadline1,deadline2)-time)/(max(deadline1,deadline2)-time) if max(deadline1,deadline2)>time else 0
    pressure=max((x+y for x,y in zip(a,b)), default=0)
    return cosine*pressure*overlap

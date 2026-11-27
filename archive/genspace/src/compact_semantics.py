"""Exact compact encoding for the fixed finite public engineering domain.

Encoding compares signatures only *within* one unchanged public instance.
Role descriptors, predicate names, cell order and scalar profile values are
fixed by that public record; cross-instance equality is not meaningful.
"""
from dataclasses import dataclass
from .instances import registry_from_public
from .registry import default_registry
from .state_machine import semantic_key, _signature

SCOPES = ('static','conditional','phased','delayed','validity','offload')

@dataclass
class CompactEncoder:
    public: object

    def __post_init__(self):
        self.roles = tuple(sorted(default_registry()))
        self.role_index = {r:i for i,r in enumerate(self.roles)}
        self.reg = registry_from_public(self.public)
        self.profiles = {(p.quality,p.deadline,p.rate):i for i,p in enumerate(self.public.b2_profiles)}
        if len(self.profiles)!=len(self.public.b2_profiles) or len(self.profiles)>254:
            raise ValueError('duplicate profiles or profile count exceeds byte domain')
        if len(self.roles)>16:
            raise ValueError('role mask overflow')
        self.scope_bits = {x:1<<i for i,x in enumerate(SCOPES)}
        for r in self.roles:
            if r not in self.reg: raise ValueError('canonical role declaration missing')
            if len(self.reg[r].preconditions)>7: raise ValueError('predicate mask overflow')
        from .models import Static
        from .state_machine import _predicate
        dummy=Static(self.public.b2_profiles[0])
        self.all_predicates_true = all(_predicate(pred,dummy,self.public) for role in self.roles for pred in self.reg[role].preconditions)

    def pack(self, key):
        """Encode semantic_key injectively given this fixed public registry."""
        footprint,valid,cells=key
        out=bytearray([1 if valid else 0]); entries={entry[0]:entry for entry in footprint}
        if not set(entries)<=set(self.roles): raise ValueError('unknown role')
        for role in self.roles:
            if role not in entries:
                out.extend((255,0)); continue
            _,descriptor,scopes,preds=entries[role]
            if descriptor != _signature(self.reg[role]): raise ValueError('descriptor mismatch')
            mask=0
            for scope in scopes: mask |= self.scope_bits[scope]
            expected=tuple(sorted(self.reg[role].preconditions))
            if tuple(p for p,_ in preds)!=expected: raise ValueError('predicate mismatch')
            predicates=sum((1<<i) for i,(_,value) in enumerate(preds) if value)
            out.extend((mask,predicates))
        if valid:
            expected=[(t,s) for t in range(self.public.horizon) for s in self.public.states]
            if [(t,s) for t,s,_ in cells]!=expected: raise ValueError('guard order mismatch')
            for _,_,resolved in cells:
                if resolved is None:
                    out.extend((255,0,0,0)); continue
                q,d,r,level,roles,costs=resolved
                ix=self.profiles[(q,d,r)]
                if level not in ('none','edge'): raise ValueError('unknown level')
                role_mask=sum(1<<self.role_index[x] for x in roles)
                # Costs are deterministic from roles and fixed registry; check.
                from .state_machine import _role_costs
                if costs != _role_costs(roles,self.reg): raise ValueError('cost mismatch')
                out.extend((ix, 1 if level=='edge' else 0, role_mask>>8, role_mask & 255))
        return bytes(out)

    def encode(self,node):
        return self.pack(semantic_key(node,self.public))

    def combine(self, operation, value, left, right=None):
        """Compose compact signatures in the fixed, valid 3x2 benchmark domain.

        This restricted transfer accepts only grammar parameters documented in
        the public instance. It does not handle invalid V3 children. All role
        predicates in this grammar must be positive for its public instance.
        """
        from .engine import BASE, STRUCTURAL
        from .models import If, Sequence, Delay, ValidFor, Offload, Static
        from .state_machine import _predicate
        classes={'If':If,'Sequence':Sequence,'Delay':Delay,'ValidFor':ValidFor,'Offload':Offload}
        domains={'If':self.public.conditions,'Sequence':self.public.durations,
                 'Delay':self.public.offsets,'ValidFor':self.public.intervals,'Offload':self.public.offload_levels}
        if operation not in classes or value not in domains[operation]: raise ValueError('outside configured grammar')
        if self.public.horizon!=3 or self.public.states!=('still','moving'): raise ValueError('only fixed 3x2 domain supported')
        if left[0]!=1 or (right is not None and right[0]!=1): raise ValueError('invalid child')
        if operation in ('If','Sequence') and right is None: raise ValueError('missing right child')
        if operation=='If' and left==right: return left
        cls=classes[operation]
        scope={'If':'conditional','Sequence':'phased','Delay':'delayed','ValidFor':'validity','Offload':'offload'}[operation]
        sb=self.scope_bits[scope]
        child_list=(left,) if right is None else (left,right)
        if not self.all_predicates_true:
            raise ValueError('transfer currently requires all public role predicates true')
        out=bytearray([1]+[255,0]*len(self.roles))
        structural=set(STRUCTURAL[cls])
        for i,role in enumerate(self.roles):
            masks=[c[1+2*i] for c in child_list if c[1+2*i]!=255]
            if role in structural: masks.append(sb)
            if not masks: continue
            mask=0
            for x in masks: mask |= x
            if role in BASE: mask=(mask & ~self.scope_bits['static']) | sb
            preds=(1<<len(self.reg[role].preconditions))-1
            out[1+2*i]=mask; out[2+2*i]=preds
        offset=1+2*len(self.roles)
        rolebits=sum(1<<self.role_index[r] for r in structural)
        for t in range(3):
            for si,state in enumerate(self.public.states):
                source=left; local=t
                if operation=='If': source=left if state=='moving' else right
                elif operation=='Sequence':
                    if t>=value: source=right; local=t-value
                elif operation=='Delay':
                    if t<value: out.extend((255,0,0,0)); continue
                    local=t-value
                elif operation=='ValidFor':
                    if not value[0]<=t<value[1]: out.extend((255,0,0,0)); continue
                    local=t-value[0]
                idx=offset+4*(local*2+si)
                cell=source[idx:idx+4]
                if cell[0]==255: out.extend((255,0,0,0)); continue
                bits=(cell[2]<<8)|cell[3]; bits |= rolebits
                level=1 if operation=='Offload' else cell[1]
                out.extend((cell[0],level,bits>>8,bits&255))
        return bytes(out)

    def apply_if(self, condition, left, right):
        return self.combine('If',condition,left,right)

    def apply_sequence(self, duration, left, right):
        return self.combine('Sequence',duration,left,right)

    def apply_delay(self, offset, child):
        return self.combine('Delay',offset,child)

    def apply_valid_for(self, interval, child):
        return self.combine('ValidFor',interval,child)

    def apply_offload(self, level, child):
        return self.combine('Offload',level,child)

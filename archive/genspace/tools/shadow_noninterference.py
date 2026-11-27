"""Post-main SHADOW private-preference noninterference; no seeds are generated."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from src.process_lifecycle import prelaunch_guard, emergency_guard
from src.fast_exact import FastLibrary, FastEvaluator
from src.enumeration import candidates, syntax_key
from src.instances import deserialize_instance, PrivatePreferences
from src.smoke_authorization import verify_authorization
from src.shadow_plans import validate_plan, SHADOW_NAMESPACE

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results'/'smoke02_shadow'

def digest_set(values):
    return sha256(json.dumps(sorted(values),separators=(',',':')).encode()).hexdigest()

def main():
    if not prelaunch_guard()['pass']:raise RuntimeError('PAUSED_MEMORY prelaunch')
    snap=verify_authorization()['snapshot_sha256']
    plan=json.loads((ROOT/'SMOKE02_SHADOW_PLAN.json').read_text(encoding='utf8'))
    validate_plan(plan,'shadow')
    if not all((OUT/'main'/s['instance_id']/'COMPLETE.json').is_file() for s in plan['instances']):
        raise ValueError('requires all 16 complete markers')
    lib=FastLibrary.from_graph(scope='shadow');results=[]
    for slot in plan['instances']:
        if not emergency_guard()['pass']:raise RuntimeError('PAUSED_MEMORY emergency')
        iid=slot['instance_id'];raw=(OUT/'instances'/f'{iid}.json').read_text(encoding='utf8')
        original=deserialize_instance(raw)
        if original.namespace!=SHADOW_NAMESPACE:raise ValueError('unexpected namespace')
        def change(p):
            return {k:(.1234 if v != .1234 else .8765) for k,v in p.items()}
        modified=replace(original,private=PrivatePreferences(change(original.private.application),change(original.private.network)))
        if modified.public_hash!=original.public_hash or modified.private_hash==original.private_hash:
            raise ValueError('invalid preference perturbation')
        fingerprints=[]
        for inst in (original,modified):
            p=inst.public;depth=p.configuration['composition_depth'];item={}
            for method in ('B0','B1','B2'):
                item[method]=digest_set({syntax_key(c) for c in candidates(method,p,depth)})
            evaluator=FastEvaluator(inst,lib)
            mask=lib.availability.for_evaluator(evaluator).mask(depth)
            item['O1']=sha256(mask.tobytes()).hexdigest();fingerprints.append(item)
        results.append({'instance_id':iid,'equal':fingerprints[0]==fingerprints[1],
                        'public_hash':original.public_hash,'original_private_hash':original.private_hash,
                        'changed_private_hash':modified.private_hash,'semantic_set_hashes':fingerprints})
    if verify_authorization()['snapshot_sha256']!=snap:raise ValueError('snapshot mismatch')
    report={'snapshot_sha256':snap,'results':results,'pass':len(results)==16 and all(x['equal'] for x in results)}
    dest=OUT/'private_noninterference.json'
    if dest.exists():raise FileExistsError('refusing overwrite')
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PRIVATE NONINTERFERENCE', 'PASS' if report['pass'] else 'FAIL')
    if not report['pass']:raise SystemExit(1)

if __name__=='__main__':main()

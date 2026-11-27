"""Check sealed depth-three output certificates and report the frozen gate."""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import product
import json
from math import isfinite
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

from audit_common import (HERE,ROOT,digest,distribution,markdown_table,read_json,sealed_payloads,
                          write_csv,write_json,write_report)

KS=(10,100,500)
STATUSES=('EXACT_TOPK_CERTIFIED','NOT_CERTIFIED_WITHIN_BUDGET','UNSOUND')
WORK=('partial_generated','partial_expanded','frontier_peak','unique_semantics','scores','duplicates',
      'witness_asts_materialized','witness_recipe_evaluations','template_count','symbolic_shapes',
      'symbolic_cases','template_build_s','template_payload_bytes','peak_working_set_bytes',
      'shape_nodes_generated','shape_nodes_expanded','assignment_nodes_expanded','symbolic_shapes_compiled',
      'partition_probes','merged_template_states','duplicate_states_eliminated','max_observed_profile_slots',
      'lower_bound_evaluations','buffered_complete','template_recipes','exact_state_keys')


def depth3_slots():
    slots=read_json(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
    chosen={s['instance_id']:s for s in slots if s['seed_index']==0
            and s['configuration']['composition_depth']==2
            and s['configuration']['preference_conflict']=='high'}
    expected=set(product(('F1','F2','F3','F4'),('sparse','rich'),('low','medium','high')))
    observed={(s['family'],s['configuration']['capability_richness'],s['configuration']['resource_pressure'])
              for s in chosen.values()}
    if len(chosen)!=24 or observed!=expected:
        raise ValueError('frozen depth-three grid differs from original identities')
    return chosen


def public_input(iid, manifest):
    """Keep only the public projection of the existing serialized fixture."""
    from src.instances import PublicInstance,digest as instance_digest
    from src.models import Profile

    raw=(ROOT/'results/pilot/instances'/(iid+'.json')).read_bytes()
    identity=digest(raw)
    if identity!=manifest[iid]['sha256']:
        raise ValueError(f'serialized fixture hash mismatch: {iid}')
    p=json.loads(raw)['public']
    if instance_digest(p)!=manifest[iid]['public_hash']:
        raise ValueError(f'public projection hash mismatch: {iid}')
    for field in ('m0_profiles','mr_profiles','b2_profiles'):
        p[field]=tuple(Profile(**v) for v in p[field])
    for field in ('states','capabilities','conditions','durations','offsets','offload_levels'):
        p[field]=tuple(p[field])
    for field in ('capacity','intervals'):
        p[field]=tuple(map(tuple,p[field]))
    return PublicInstance(**p),identity


def legal_witness(node, public):
    from src.engine import ast_depth,required_capabilities
    from src.models import Delay,If,Offload,Sequence,Static,ValidFor

    def typed(n):
        if type(n) is Static:
            return n.profile in public.b2_profiles
        if type(n) is If:
            return n.condition in public.conditions and typed(n.then_clause) and typed(n.else_clause)
        if type(n) is Sequence:
            return n.duration in public.durations and typed(n.first) and typed(n.second)
        if type(n) is Delay:
            return n.offset in public.offsets and typed(n.clause)
        if type(n) is ValidFor:
            return n.interval in public.intervals and typed(n.clause)
        if type(n) is Offload:
            return n.level in public.offload_levels and typed(n.clause)
        return False

    return (ast_depth(node)<=3 and required_capabilities(node)<=set(public.capabilities) and typed(node))


def prefix_records(case,public):
    """Independently check legal witnesses, score bits and ordered unique signatures."""
    import numpy as np
    from grammar_search import decode_witness
    from public_search import (_proxy,COST_WEIGHT,GROUP_COMPLEXITY_WEIGHT,MARGIN_WEIGHT,
                               QUALITY_WEIGHT,group_bits,sanitize_public)
    from src.compact_semantics import CompactEncoder
    from src.enumeration import syntax_key
    from src.instances import registry_from_public
    from src.state_machine import normalize

    encoder=CompactEncoder(public)
    rows=[]
    seen=set()
    for rank,entry in enumerate(case.get('topk',[]),1):
        key=bytes.fromhex(entry['key'])
        if len(key)!=49 or key[0]!=1 or key in seen:
            raise ValueError(f'rank {rank}: malformed or repeated compact key')
        seen.add(key)
        node=decode_witness(entry['witness'])
        if not legal_witness(node,public):
            raise ValueError(f'rank {rank}: emitted witness outside frozen public grammar')
        normal=normalize(node,public)
        if syntax_key(normal)!=entry['witness'] or encoder.encode(normal)!=key:
            raise ValueError(f'rank {rank}: normalized witness differs from signature or witness text')
        claimed=float(entry['score'])
        if not isfinite(claimed):
            raise ValueError(f'rank {rank}: nonfinite exact public score')
        if rows and (claimed,key)<=rows[-1]:
            raise ValueError(f'rank {rank}: score and signature order violation')
        rows.append((claimed,key))
    if len(rows)>KS[-1]:
        raise ValueError('query emitted beyond requested largest K')
    if not rows:
        return rows
    keys=np.frombuffer(b''.join(key for _,key in rows),dtype=np.uint8).reshape(-1,49)
    cells=keys[:,25:].reshape(-1,6,4)
    groups=np.asarray([int(value).bit_count() for value in group_bits(SimpleNamespace(keys=keys))],dtype=np.uint8)
    reg=registry_from_public(public)
    roles=encoder.roles
    execution=np.empty(1<<len(roles),dtype=np.float64)
    costs=np.empty((len(execution),3),dtype=np.float64)
    for mask in range(len(execution)):
        chosen=tuple(reg[role] for i,role in enumerate(roles) if mask & (1<<i))
        execution[mask]=sum(cap.execution_cost for cap in chosen)
        costs[mask]=[sum(cap.resource_cost.get(resource,0.) for cap in chosen) for resource in ('RAN','FH','EDGE')]
    packed=SimpleNamespace(profiles=cells[:,:,0],level=cells[:,:,1],
                           role_masks=(cells[:,:,2].astype(np.uint16)<<8)|cells[:,:,3],
                           role_costs=costs,execution_costs=execution)
    violation,margin,quality,cost=_proxy(sanitize_public(public),packed,np.arange(len(rows),dtype=np.int64))
    scores=violation-MARGIN_WEIGHT*margin+COST_WEIGHT*cost+QUALITY_WEIGHT*(1.-quality)
    scores+=GROUP_COMPLEXITY_WEIGHT*groups
    for rank,((claimed,_),group,accurate) in enumerate(zip(rows,groups,scores),1):
        if not 1<=group<=4:
            raise ValueError(f'rank {rank}: outside structural group range')
        if struct.pack('>d',claimed)!=struct.pack('>d',accurate):
            raise ValueError(f'rank {rank}: exact FLAT score bit mismatch')
    return rows


def validate_cut(cut,k,records):
    status=cut.get('status')
    if status not in STATUSES:
        return 'UNSOUND','unknown certificate status'
    if status=='UNSOUND':
        return status,cut.get('reason',cut.get('limit_reason','online witness or frontier audit failed'))
    emitted=cut.get('returned')
    if type(emitted) is not int or emitted<0 or emitted>min(k,len(records)):
        return 'UNSOUND','certificate prefix length differs from the sealed stream'
    prefix=records[:emitted]
    expected_sha=digest(b''.join(struct.pack('>d',s)+key for s,key in prefix))
    if cut.get('prefix_sha256') not in (None,expected_sha) or (
            status=='EXACT_TOPK_CERTIFIED' and cut.get('prefix_sha256')!=expected_sha):
        return 'UNSOUND','prefix digest mismatch'
    elapsed=cut.get('elapsed_s')
    if not isinstance(elapsed,(float,int)) or not isfinite(elapsed) or elapsed<0.:
        return 'UNSOUND','invalid certificate elapsed time'
    if status=='NOT_CERTIFIED_WITHIN_BUDGET':
        if emitted==k:
            return 'UNSOUND','complete certified prefix was mislabeled as incomplete'
        return status,cut.get('reason',cut.get('limit_reason','limit or exhaustion before requested K'))
    remaining=cut.get('frontier_remaining')
    lb=cut.get('frontier_min_lb')
    if type(remaining) is not int or remaining<0:
        return 'UNSOUND','invalid certificate open frontier count'
    score,key=cut.get('buffered_best_score'),cut.get('buffered_best_key')
    if (score is None)!=(key is None):
        return 'UNSOUND','buffered candidate key and score must both be present or absent'
    snapshot=cut.get('metrics') or {}
    for field,claimed in (('frontier_remaining',remaining),('frontier_min_lb',lb),
                          ('buffered_best_score',score),('buffered_best_key',key)):
        if field in snapshot and snapshot[field]!=claimed:
            return 'UNSOUND',f'checkpoint disagrees with recorded heap snapshot: {field}'
    buffered=snapshot.get('buffered_complete')
    if buffered is not None and (type(buffered) is not int or buffered<0 or (buffered==0)!=(score is None)):
        return 'UNSOUND','buffered complete count disagrees with its best candidate'
    if cut.get('full_domain_exhausted') and (remaining>0 or score is not None or lb is not None
                                            or cut.get('in_flight_count',0)!=0):
        return 'UNSOUND','empty full domain contradicts the cutoff frontier'
    if emitted!=k and (not cut.get('full_domain_exhausted') or len(records)!=emitted):
        return 'UNSOUND','short exact certificate does not show total domain exhaustion'
    if not prefix:
        if cut.get('boundary_key') is not None or cut.get('boundary_score') is not None:
            return 'UNSOUND','empty certified domain cannot have a boundary candidate'
        return status,''
    kth_score,kth_key=prefix[-1]
    if cut.get('boundary_key')!=kth_key.hex() or cut.get('boundary_score') is None:
        return 'UNSOUND','certificate boundary candidate key is missing or differs'
    if struct.pack('>d',cut['boundary_score'])!=struct.pack('>d',kth_score):
        return 'UNSOUND','certificate boundary score bits differ'
    if (remaining==0 and lb is not None) or (remaining>0 and (
            not isinstance(lb,(float,int)) or not isfinite(lb) or not lb>kth_score)):
        return 'UNSOUND','certificate does not separate all pending lower bounds from the cutoff'
    if score is not None and (not isfinite(score) or len(bytes.fromhex(key))!=49
                              or (score,bytes.fromhex(key))<=(kth_score,kth_key)):
        return 'UNSOUND','a buffered candidate can precede or duplicate the cutoff'
    return status,''


def fmt(value):
    return 'NA' if value is None else f'{value:,.6g}'


def work_distribution(rows,metrics):
    return {field:distribution(row.get(field) for row in rows) for field in metrics}


def summarize(seal_path):
    regression=read_json(HERE/'depth2_regression.json')
    seal,cases,seal_sha=sealed_payloads(seal_path)
    if (seal['manifest'].get('effective_depth')!=3
            or seal['manifest'].get('tie_rule')!='score_then_unsigned_lexicographic_compact_key'
            or seal['manifest'].get('prefix_digest')!='sha256_concat_binary64_be_then_key'):
        raise ValueError('depth-three report requires the declared depth-three phase')
    known=depth3_slots()
    if set(cases)!=set(known):
        raise ValueError('development seal differs from the 24 original fixed public queries')
    derived=seal.get('derived_inputs',{})
    if set(derived)!=set(cases):
        raise ValueError('derived input copies differ from sealed development cases')
    manifest=read_json(ROOT/'results/pilot/instances_manifest.json')
    sys.path[:0]=[str(ROOT),str(ROOT/'results/grammar_gate'),str(ROOT/'results/method_dev_v1')]
    rows=[]
    for iid,case in cases.items():
        slot=known[iid]
        public,sha=public_input(iid,manifest)
        copy=(HERE/derived[iid]['path']).resolve()
        if (not copy.is_relative_to(seal_path.resolve().parent/'derived_inputs')
                or digest(copy.read_bytes())!=derived[iid]['sha256']
                or case.get('derived_input_sha256')!=derived[iid]['sha256']):
            raise ValueError(f'derived query audit copy differs from seal: {iid}')
        envelope=read_json(copy)
        if (case['serialized_sha256']!=sha or case['configuration']!=slot['configuration']
                or envelope['source_instance_id']!=iid or envelope['source_identity']!=manifest[iid]
                or envelope.get('effective_depth')!=3 or envelope.get('derived_query_id')!=case.get('derived_query_id')):
            raise ValueError(f'sealed public development case changed: {iid}')
        error=''
        try:
            records=prefix_records(case,public)
        except (AssertionError,KeyError,OverflowError,TypeError,ValueError) as exc:
            error=str(exc)
            records=[]
        cuts=case.get('k_certificates',{})
        if set(cuts)!={str(k) for k in KS}:
            error='certificate checkpoint coverage differs from frozen K values'
        for k in KS:
            cut=dict(cuts.get(str(k),{}))
            if cut.get('status')=='NOT_CERTIFIED_WITHIN_BUDGET' and cut.get('elapsed_s') is None:
                cut['elapsed_s']=case.get('elapsed_s')
            try:
                status,reason=('UNSOUND',error) if error else validate_cut(cut,k,records)
            except (TypeError,OverflowError,ValueError) as exc:
                status,reason='UNSOUND',str(exc)
            values={key:cut.get(key) for key in WORK}
            if isinstance(cut.get('metrics'),dict):
                values={key:cut['metrics'].get(key,values[key]) for key in WORK}
            rows.append(dict(instance_id=iid,family=slot['family'],
                             derived_query_id=case.get('derived_query_id'),
                             pressure=public.configuration['resource_pressure'],
                             richness=public.configuration['capability_richness'],K=k,
                             status=status,reason=reason,returned=cut.get('returned'),
                             full_length=int(status=='EXACT_TOPK_CERTIFIED' and cut.get('returned')==k),
                             elapsed_s=cut.get('elapsed_s'),cursor_elapsed_s=(cut.get('metrics') or {}).get('wall_s'),
                             query_elapsed_s=cut.get('query_elapsed_s'),
                             final_query_elapsed_s=case.get('elapsed_s'),
                             final_query_peak_working_set_bytes=case.get('peak_working_set_bytes'),
                             final_verifier_calls=case.get('verification_calls'),final_proposal_rounds=case.get('proposal_rounds'),
                             boundary_score=cut.get('boundary_score'),
                             boundary_key=cut.get('boundary_key'),frontier_min_lb=cut.get('frontier_min_lb'),
                             frontier_remaining=cut.get('frontier_remaining'),
                             buffered_best_score=cut.get('buffered_best_score'),buffered_best_key=cut.get('buffered_best_key'),
                             full_domain_exhausted=cut.get('full_domain_exhausted'),prefix_sha256=cut.get('prefix_sha256'),
                             **values))
    if len(rows)!=72 or len({(r['instance_id'],r['K']) for r in rows})!=72:
        raise ValueError('depth-three adjudication requires 72 distinct case/K rows')
    write_csv(HERE/'per_query.csv',tuple(rows[0]),rows)
    scores={k:sum(row['K']==k and row['status']=='EXACT_TOPK_CERTIFIED' for row in rows) for k in KS}
    full={k:sum(row['K']==k and row['full_length'] for row in rows) for k in KS}
    unsound=sum(row['status']=='UNSOUND' for row in rows)
    omitted=sum(row['status']=='NOT_CERTIFIED_WITHIN_BUDGET' for row in rows)
    short_k500=[(row['instance_id'],row['returned']) for row in rows
                if row['K']==500 and row['status']=='EXACT_TOPK_CERTIFIED' and not row['full_length']]
    cells={(f,r):set() for f,r in product(('F1','F2','F3','F4'),('sparse','rich'))}
    for row in rows:
        if row['K']==500 and row['full_length']:
            cells[row['family'],row['richness']].add(row['pressure'])
    if regression['status']!='PASS' or unsound or scores[10]==0:
        tag='DEPTH3_INFEASIBLE'
    elif full[500]>=20 and all(len(pressures)>=2 for pressures in cells.values()):
        tag='DEPTH3_FEASIBLE'
    else:
        tag='DEPTH3_PARTIAL'
    work={}
    for k in KS:
        selected=[r for r in rows if r['K']==k]
        good=[r for r in selected if r['status']=='EXACT_TOPK_CERTIFIED']
        work[str(k)]=dict(all_attempts=work_distribution(selected,('elapsed_s','cursor_elapsed_s','query_elapsed_s',*WORK)),
                         certified=work_distribution(good,('elapsed_s','cursor_elapsed_s','query_elapsed_s',*WORK)))
    final_work=work_distribution([r for r in rows if r['K']==500],('final_query_elapsed_s',
                                 'final_query_peak_working_set_bytes','final_verifier_calls','final_proposal_rounds'))
    limit_counts={str(k):dict(Counter(r['reason'] or 'recorded limit'
                  for r in rows if r['K']==k and r['status']=='NOT_CERTIFIED_WITHIN_BUDGET')) for k in KS}
    seen_cuts=sum(len(r.get('topk',[])) for r in cases.values())
    write_report(ROOT/'DEPTH3_EXACT_CERTIFICATES.md',[
        '# Depth-three exact frontier certificates', '',
        'The independent checker used the fixed public profiles, operators, registry and packed semantics. '
        'It re-encoded emitted normalized witnesses, recomputed their score bits using the original NumPy FLAT '
        '`_proxy` and checked unique '
        'ordered `(score, signature)` keys. The check used no depth-three graph or historical rank array.', '',
        'For each requested K, the certificate binds the emitted prefix by SHA-256 of successive big-endian '
        'binary64 scores and compact signature bytes. A nonempty frontier must have a strictly larger lower bound '
        'than the boundary score. A buffered complete candidate must sort strictly after the boundary key. '
        'A fully exhausted domain may certify a prefix shorter than K. These cases are counted separately from full-length certificates. '
        'This verifies the certificate against the documented admissible envelope. The lower-bound proof in the '
        'method documentation supplies the guarantee for subtrees the checker did not enumerate.', '',
        f'Validated {seen_cuts:,} emitted records and {len(rows)} checkpoint rows. Unsound checkpoints: **{unsound}**.', '',
        *markdown_table(('Instance','K','Status','Returned','Boundary score','Frontier min LB','Open frontier','Proof reason'),[
            (r['instance_id'],r['K'],r['status'],r['returned'],fmt(r['boundary_score']),fmt(r['frontier_min_lb']),
             r['frontier_remaining'],r['reason']) for r in rows]), '',
        'Machine-readable keys, digests and work counters are in `results/depth3/per_query.csv`.',
    ])
    write_report(ROOT/'DEPTH3_SEARCH_COST_REPORT.md',[
        '# Depth-three search work and measured cost', '',
        'All attempts include capped cases. Time at a cap is elapsed work and can only lower-bound time to '
        'a future certification. The certified-only lane excludes capped cases. Missing telemetry remains NA. '
        'Peak working set measures the whole process and is sampled. All rows are the fixed existing public fixtures. '
        'The cursor clock can include verifier and protocol work interleaved after cursor creation. '
        'A certified checkpoint uses the cursor clock, while an incomplete checkpoint records the whole query clock '
        'at its cutoff. Final-query rows below all use the same end-to-end clock.', '',
        *markdown_table(('K','Scope','Metric','n','Median','p95','Max'),[
            (k,scope,field,m['n'],fmt(m['median']),fmt(m['p95']),fmt(m['maximum']))
            for k,scopes in work.items() for scope,fields in scopes.items() for field,m in fields.items()
            if m['n']]), '',
        'Shape expansions, profile-assignment expansions and symbolic equality partition probes are counted '
        'distinctly. The aggregate partial expansion counter includes all three. A merged symbolic template '
        'does not produce another complete semantic score. Frontier peak includes buffered complete candidates, '
        'pending lower-bound states and any in-flight expansion represented by its predecessor bound.', '',
        *markdown_table(('K','Cutoff reason','Count'),[(k,why,n)
                        for k,reasons in limit_counts.items() for why,n in sorted(reasons.items())]), '',
        'Each final-query measurement covers the full combined negotiation and prefix-search attempt.', '',
        *markdown_table(('Metric','n','Median','p95','Max'),[(name,m['n'],fmt(m['median']),fmt(m['p95']),fmt(m['maximum']))
                        for name,m in final_work.items() if m['n']]), '',
        f'Sealed engineering limits: `{json.dumps(seal["manifest"].get("limits",{}),sort_keys=True)}`.',
    ])
    write_report(HERE/'DEPTH3_FEASIBILITY_REPORT.md',[
        '# DEPTH3-FEASIBILITY-01', '',f'**{tag}**', '',
        f'Depth≤2 regression seal: **{regression["status"]}** across {regression["query_count"]} existing fixed queries. '
        f'The depth-three online seal covers 24 existing public fixtures, with clean guard counters and '
        f'{unsound} unsound certificate checkpoints.', '',
        *markdown_table(('K','Exact certified','Full length','Exhausted short','Requested','Exact rate'),[
            (k,scores[k],full[k],scores[k]-full[k],24,f'{scores[k]/24:.2%}') for k in KS]), '',
        *(['Every requested checkpoint was certified as an exact finite-domain prefix. The run recorded zero '
           'resource-limited checkpoints.', ''] if not omitted and not unsound else []),
        *(['The following K500 queries exhausted their entire domains. Their exact prefixes are shorter than '
           'the requested K because that many distinct eligible contracts exist for those public capabilities.', '',
           *markdown_table(('Instance','Exact domain size'),short_k500),''] if short_k500 else []),
        *markdown_table(('Family','Richness','Certified K500 pressure levels','Covered / 3'),[
            (f,r,', '.join(sorted(p)) or '—',len(p)) for (f,r),p in sorted(cells.items())]), '',
        'FEASIBLE requires at least 20 of 24 full-length K500 certificates, at least two pressure levels per family and '
        'richness pair, a passing depth-two regression and zero unsound checkpoints. PARTIAL requires one or more '
        'certified K10 results with a passing regression and no unsound checkpoints. Other outcomes are INFEASIBLE.', '',
        'Depth-three uses the fixed public six-cell DSL with up to four structural groups. The sealed trials '
        'are an engineering feasibility gate on existing fixtures. Exact prefixes are not a full depth-three enumeration.',
    ])
    result=dict(status=tag,depth2_regression=regression['status'],online_seal_sha256=seal_sha,
                graph_independence='PASS',case_count=24,certificate_rows=72,unsound=unsound,certified=scores,
                full_length_certified=full,
                k500_coverage={f'{f}/{r}':sorted(p) for (f,r),p in cells.items()},work=work,
                final_query_work=final_work,limit_counts=limit_counts,
                incomplete_certificate_rows=omitted,exhausted_short_k500=dict(short_k500))
    write_json(HERE/'gate_summary.json',result)
    print(dict(status=tag,certified=scores,full_length_certified=full,unsound=unsound),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',type=Path,required=True)
    args=parser.parse_args()
    result=summarize(args.seal)
    return 0 if result['status']=='DEPTH3_FEASIBLE' else 2


if __name__=='__main__':
    raise SystemExit(main())

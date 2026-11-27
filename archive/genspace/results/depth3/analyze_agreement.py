"""Offline-only verification, depth-two membership and agreement comparison."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'results/grammar_gate'), str(ROOT/'results/method_dev_v1')]

from grammar_search import FlatPublicScore
from runtime import choose_variant, verification_public
from src.compact_semantics import CompactEncoder
from src.engine import ast_depth, required_capabilities
from src.enumeration import syntax_key
from src.fast_exact import FastLibrary
from src.fast_runner import _decode_witness
from src.instances import deserialize_instance
from src.state_machine import _nodes, normalize, verify_instance
from tools.smoke_01 import memory_status
from audit_common import csv_rows, digest as sha, read_json, sealed_payloads, write_csv, write_report
from certificate_report import depth3_slots, legal_witness, validate_cut


K_VALUES = (10,100,500)
BUDGETS = (100,500,1000,5000)
NOVEL = {'DEPTH3_ONLY_GLOBAL','DEPTH3_ONLY_CAPABILITY_CONDITIONED'}


def same_float(left, right):
    return struct.pack('>d',left)==struct.pack('>d',right)


def sealed_cases(path):
    path = path.resolve()
    if path.name!='search_seal.json' or path.parent.parent!=HERE:
        raise ValueError('expected a sealed depth3 online run directory')
    seal, cases, seal_sha = sealed_payloads(path)
    manifest, guard = seal['manifest'], seal['guard']
    counts = guard['forbidden_call_counts']
    guarded = {'semantic_graph_file','index_gate_artifact','availability_index_artifact',
               'FastLibrary.from_graph','graph_library','generate_instance','derive_seed'}
    if (seal.get('complete_batch') is not True or manifest['effective_depth']!=3 or
            guard.get('pass') is not True or guard.get('blocked')!=[] or not guarded<=counts.keys() or
            not all(type(n) is int and n==0 for n in counts.values())):
        raise ValueError('a clean depth-3 online seal is required before loading the frozen depth-2 reference')
    if manifest['phase']!='development' or manifest!=read_json(path.parent/'online_manifest.json'):
        raise ValueError('development seal and recorded online scope differ')
    for name, expected in manifest['sources'].items():
        origin = (ROOT/name).resolve()
        if not origin.is_relative_to(ROOT) or sha(origin.read_bytes())!=expected:
            raise ValueError(f'online source differs from frozen seal: {name}')
    derived = seal['derived_inputs']
    if set(derived)!=set(cases):
        raise ValueError('the derived-input files do not cover the sealed case set')
    copies = {}
    for iid, case in cases.items():
        if (HERE/seal['cases'][iid]['path']).resolve()!=(path.parent/(iid+'.json')).resolve():
            raise ValueError(f'wrong location for sealed case {iid}')
        qid = iid+'__METHOD_D3'
        if case['instance_id']!=iid or case.get('derived_query_id')!=qid or case['effective_depth']!=3:
            raise ValueError(f'wrong case identity {iid}')
        derived_path = (HERE/derived[iid]['path']).resolve()
        if derived_path!=(path.parent/'derived_inputs'/(qid+'.json')).resolve():
            raise ValueError(f'wrong location for derived input copy {iid}')
        raw_copy = derived_path.read_bytes()
        if sha(raw_copy)!=derived[iid]['sha256'] or case['derived_input_sha256']!=derived[iid]['sha256']:
            raise ValueError(f'derived input digest mismatch {iid}')
        copies[iid] = json.loads(raw_copy)
    if len(cases)!=24:
        raise ValueError('expected 24 sealed depth-3 development queries')
    return cases, copies, seal_sha


def frozen_instance(iid, case, copied, instances):
    raw = (ROOT/'results/pilot/instances'/(iid+'.json')).read_bytes()
    inst = deserialize_instance(raw.decode('utf-8'))
    expected = instances[iid]
    identity = dict(sha256=sha(raw),instance_hash=inst.instance_hash,
                    public_hash=inst.public_hash,private_hash=inst.private_hash)
    if (identity!=expected or inst.instance_hash!=case['instance_hash'] or
            identity['sha256']!=case['serialized_sha256'] or identity['sha256']!=case['source_sha256'] or
            inst.namespace!='GENSPACE-FAIL-01-PILOT' or case['configuration']!=inst.public.configuration):
        raise ValueError(f'original serialized instance mismatch {iid}')
    expected_copy = dict(derived_query_id=case['derived_query_id'],source_instance_id=iid,source_identity=identity,
                         effective_depth=3,scope='development_method_extension',source_record=json.loads(raw))
    if copied!=expected_copy:
        raise ValueError(f'derived depth-3 input differs from its unchanged original {iid}')
    return inst, identity


def frozen_outcomes(iid, identity):
    lane = ROOT/'results/pilot/main'/iid
    marker = read_json(lane/'COMPLETE.json')
    raw = (lane/'result.json').read_bytes()
    payload = json.loads(raw)
    if (sha(raw)!=marker.get('result_sha256') or marker.get('instance_sha256')!=identity['sha256'] or
            payload.get('instance_id')!=iid or not payload.get('ok') or
            payload.get('snapshot_pre_verified') is not True or payload.get('snapshot_post_verified') is not True or
            payload.get('snapshot_hash')!=marker.get('snapshot_hash') or
            payload.get('instance_hash')!=identity['instance_hash']):
        raise ValueError(f'frozen PILOT result provenance mismatch {iid}')
    rows = {row['method']:row for row in payload['rows']}
    b2, o1 = rows['B2'], rows['O1']
    if o1['oracle_status']!='DIAGNOSTIC_EXISTENCE_ORACLE' or (b2['agreement'] and not o1['agreement']):
        raise ValueError(f'frozen exact baseline inconsistent {iid}')
    return b2, o1


def lookup_class(rich_keys, key):
    """Search the frozen sorted depth-two signatures without a new index."""
    low, high = 0, len(rich_keys)
    while low<high:
        mid = (low+high)//2
        if rich_keys[mid].tobytes()<key:
            low = mid+1
        else:
            high = mid
    return low if low<len(rich_keys) and rich_keys[low].tobytes()==key else None


def compare_case(iid, case, instance, library, b2, o1):
    public = verification_public(instance.public)
    availability = choose_variant(public,library)
    depth2_mask = availability.mask(2)
    encoder = CompactEncoder(public)
    scorer = FlatPublicScore(public)
    verified_cache = {}

    for archived in (b2,o1):
        if not archived['agreement']:
            continue
        node = _decode_witness(json.loads(archived['representative']))
        old_verified = verify_instance(node,instance,2)
        old_id = lookup_class(library.keys,encoder.encode(node))
        if (not old_verified.verified or old_id is None or not depth2_mask[old_id] or
                not same_float(old_verified.application_utility,archived['application_utility']) or
                not same_float(old_verified.network_utility,archived['network_utility']) or
                not same_float(old_verified.application_utility*old_verified.network_utility,archived['nash_welfare'])):
            raise ValueError(f'original winner failed frozen depth≤2 validation {iid} {archived["method"]}')

    def characterize(signature, witness, score=None):
        key = bytes.fromhex(signature)
        if len(key)!=49 or key[0]!=1 or not isinstance(witness,str):
            raise ValueError(f'invalid sealed candidate {iid}')
        if signature not in verified_cache:
            node = _decode_witness(json.loads(witness))
            normalized = normalize(node,public)
            if not legal_witness(node,public) or encoder.encode(normalized)!=key or syntax_key(normalized)!=witness:
                raise ValueError(f'candidate signature, canonical witness or depth mismatch {iid}')
            cid = lookup_class(library.keys,key)
            if cid is None:
                membership = 'DEPTH3_ONLY_GLOBAL'
            elif depth2_mask[cid]:
                membership = 'IN_CONDITIONED_DEPTH2'
            else:
                membership = 'DEPTH3_ONLY_CAPABILITY_CONDITIONED'
            if membership in NOVEL and ast_depth(normalized)<=2:
                raise ValueError(f'novelty conflicts with its own depth<=2 witness {iid}')
            result = verify_instance(normalized,instance,3)
            groups = scorer.group_count(key)
            exact_score = scorer.score(key,groups)
            if not math.isfinite(exact_score):
                raise ValueError(f'nonfinite frozen public score {iid}')
            if result.verified and membership=='IN_CONDITIONED_DEPTH2' and not o1['agreement']:
                raise ValueError(f'independent depth2 acceptance contradicts frozen O1 existence {iid}')
            u_a,u_n = (result.application_utility,result.network_utility) if result.verified else (None,None)
            nash = u_a*u_n if result.verified else None
            verified_cache[signature] = (witness,dict(signature=signature,representative=witness,
                actual_depth=ast_depth(normalized),mechanism_group_count=groups,exact_public_score=exact_score,
                global_depth2_class_id=cid,globally_in_depth2=cid is not None,
                conditioned_depth2_membership=membership,depth3_only=membership in NOVEL,
                independently_verified=result.verified,verification_failed_layer=result.failed_layer,
                uA=u_a,uN=u_n,nash=nash))
        known_witness, row = verified_cache[signature]
        if known_witness!=witness or (score is not None and not same_float(score,row['exact_public_score'])):
            raise ValueError(f'signature witness or bitwise score mismatch {iid}')
        return row

    common = dict(instance_id=iid,derived_query_id=case['derived_query_id'],family=instance.public.family,
                  pressure=instance.public.configuration['resource_pressure'],
                  richness=instance.public.configuration['capability_richness'],
                  availability_pattern=availability.header['pattern'],old_B2_agreement=b2['agreement'],
                  old_O1_agreement=o1['agreement'],old_O1_nash=o1['nash_welfare'])
    candidates = []
    for rank, entry in enumerate(case['topk'],1):
        row = characterize(entry['key'],entry['witness'],entry['score'])
        candidates.append(dict(common,rank=rank,**row))
    keys = [(r['exact_public_score'],bytes.fromhex(r['signature'])) for r in candidates]
    if keys!=sorted(keys) or len({r['signature'] for r in candidates})!=len(candidates):
        raise ValueError(f'candidate prefix is unsorted or duplicated {iid}')
    cuts = case['k_certificates']
    if set(cuts)!={str(k) for k in K_VALUES}:
        raise ValueError(f'depth3 certificate checkpoints differ {iid}')
    for k in K_VALUES:
        status, reason = validate_cut(cuts[str(k)], k, keys)
        if status=='UNSOUND':
            raise ValueError(f'unsound sealed K={k} prefix {iid}: {reason}')
        for row in candidates:
            row[f'K{k}_status'] = status
    agreements = []
    history = case.get('history',[])
    for budget in BUDGETS:
        checkpoint = case.get('protocol',{}).get(str(budget))
        if checkpoint is None:
            agreements.append(dict(common,budget=budget,status='UNKNOWN',verification_calls=None,
                                   observed_case_verification_calls=case.get('verification_calls'),
                                   derived_protocol_status=case['protocol_status']))
            continue
        count = checkpoint['verification_calls']
        if not 27<=count<=budget or checkpoint['b2_agreement']!=b2['agreement']:
            raise ValueError(f'budget or stage B2 mismatch {iid} {budget}')
        status = ('AGREEMENT' if checkpoint['agreement'] else
                  'EXHAUSTED_NO_AGREEMENT' if case.get('agreement_status')=='EXHAUSTED_NO_AGREEMENT' and
                  count==case.get('verification_calls') else 'UNKNOWN')
        row = dict(common,budget=budget,status=status,checkpoint_agreement=checkpoint['agreement'],
                   verification_calls=count,observed_case_verification_calls=case.get('verification_calls'),
                   derived_protocol_status=case['protocol_status'])
        if checkpoint['agreement']:
            winner = characterize(checkpoint['signature'],checkpoint['representative'])
            if (not winner['independently_verified'] or not history or
                    history[-1]['message']!='ACCEPT' or history[-1]['candidate_id']!=winner['signature']):
                raise ValueError(f'agreement failed legacy reference verification {iid} {budget}')
            for field in ('uA','uN','nash'):
                if field in checkpoint and not same_float(checkpoint[field],winner[field]):
                    raise ValueError(f'depth3 agreement utility mismatch {iid} {budget} {field}')
            row.update(winner)
            row.update(new_agreement_over_O1=(winner['depth3_only'] and not o1['agreement']),
                       signed_delta_uA=(winner['uA']-o1['application_utility']) if o1['agreement'] else None,
                       signed_delta_uN=(winner['uN']-o1['network_utility']) if o1['agreement'] else None,
                       signed_delta_Nash=(winner['nash']-o1['nash_welfare']) if o1['agreement'] else None)
        agreements.append(row)
    return candidates, agreements


def write_analysis_report(cases, candidate_rows, agreements, seal_sha):
    lines = ['# Depth-3 novelty and agreement analysis','',
             'The comparator opened the frozen **depth≤2** semantic graph only after the 24 graph-free '
             'development queries were sealed. It searched sorted depth-two signatures and used the exact '
             'capability-conditioned depth≤2 availability mask, without building a depth-three graph. '
             'The mask uses all exact O1 structures; the narrower historical FLAT one/two-group ranking '
             'does not define novelty. Each emitted witness and protocol winner was independently normalized, '
             'encoded and checked by the original V1–V5 state machine at effective depth 3.', '',
             f'Online seal SHA256 `{seal_sha}`.', '',
             'The table counts candidate occurrences across queries, so a signature seen in different '
             'queries can count more than once. Novelty includes signatures missing globally and those '
             'present globally but absent under the query’s frozen capability availability. Only certified '
             'emissions are counted. An incomplete prefix cannot establish the full Top-K result. A proven '
             'exhausted domain is reported separately when shorter than K.','',
             '| K | Full-length certified queries | Short exhausted certificates | Emitted prefix candidates | Globally absent | Absent after capability conditioning only | Independently verified novel |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for k in K_VALUES:
        rows = [r for r in candidate_rows if r['rank']<=k]
        complete = sum(case['k_certificates'][str(k)]['status']=='EXACT_TOPK_CERTIFIED' and
                       case['k_certificates'][str(k)]['returned']==k for case in cases.values())
        exhausted = sum(case['k_certificates'][str(k)]['status']=='EXACT_TOPK_CERTIFIED' and
                        case['k_certificates'][str(k)]['returned']<k for case in cases.values())
        membership = Counter(r['conditioned_depth2_membership'] for r in rows)
        both = sum(r['depth3_only'] and r['independently_verified'] for r in rows)
        lines.append(f'| {k} | {complete}/24 | {exhausted}/24 | {len(rows)} | {membership["DEPTH3_ONLY_GLOBAL"]} | '
                     f'{membership["DEPTH3_ONLY_CAPABILITY_CONDITIONED"]} | {both} |')
    novel_accepted = [r for r in candidate_rows if r['depth3_only'] and r['independently_verified']]
    novel_where_old_failed = [r for r in novel_accepted if not r['old_O1_agreement']]
    lines.extend(['',f'The emitted prefixes contain {len(novel_accepted)} independently verified depth3-only '
                  f'candidate occurrences across {len({r["instance_id"] for r in novel_accepted})} queries. '
                  f'Among cases where old O1 had no agreement, they contain {len(novel_where_old_failed)} '
                  f'such candidates across {len({r["instance_id"] for r in novel_where_old_failed})} queries. '
                  'This is evidence of existence on the tested query only. The table below requires a '
                  'selected agreement from the actual bilateral protocol.', '',
                  'A capped case remains **UNKNOWN** for agreement existence. This includes a '
                  'verification-budget stop with no agreement and no proof of domain exhaustion. “New agreement over O1” '
                  'requires a verified selected depth3-only witness on an instance where the original exact '
                  'depth≤2 O1 reported no agreement. A novel winner on a case already solved by O1 shows '
                  'a different available contract. The signed Nash difference is computed only for two verified agreements.', '',
                  '| Exact verification budget | Agreements | Exhausted with no agreement | Unknown | Depth3-only winners | New over O1 |',
                  '|---:|---:|---:|---:|---:|---:|'])
    for budget in BUDGETS:
        rows = [r for r in agreements if r['budget']==budget]
        status = Counter(r['status'] for r in rows)
        novel = sum(r.get('depth3_only',False) for r in rows)
        new = sum(r.get('new_agreement_over_O1',False) for r in rows)
        lines.append(f'| {budget} | {status["AGREEMENT"]} | {status["EXHAUSTED_NO_AGREEMENT"]} | {status["UNKNOWN"]} | {novel} | {new} |')
    lines.extend(['','| Instance | B=5000 outcome | Original B2 / O1 | Winner depth≤2 membership | Signed Nash difference vs old O1 |',
                  '|---|---|---|---|---:|'])
    for r in agreements:
        if r['budget']!=5000:
            continue
        delta = r.get('signed_delta_Nash')
        shown = '—' if delta is None else f'{delta:+.9f}'
        membership = r.get('conditioned_depth2_membership','—')
        lines.append(f"| `{r['instance_id']}` | {r['status']} | {r['old_B2_agreement']} / {r['old_O1_agreement']} | "
                     f'{membership} | {shown} |')
    lines.extend(['','Machine-readable candidate and agreement details are saved in '
                  '`results/depth3/new_contract_candidates.csv` and `results/depth3/new_contract_agreements.csv`. '
                  'This is a fixed development fixture study. The certified prefix and bounded protocol '
                  'results do not enumerate all depth-three agreements.',''])
    write_report(ROOT/'DEPTH3_NEW_CONTRACT_ANALYSIS.md',lines)


def footprint(witness):
    node = _decode_witness(json.loads(witness))
    roles = required_capabilities(node)
    codes = '+'.join(code for code, keys in (
        ('C', {'apply_conditional_policy'}), ('D', {'schedule_start'}),
        ('P', {'apply_phased_policy','set_validity_interval'}), ('O', {'enable_edge_offload'}),
    ) if roles & keys) or 'STATIC'
    constructors = '+'.join(sorted({type(x).__name__ for x in _nodes(node)}-{'Static'})) or 'Static'
    return codes, constructors, sorted(roles)


def enrich_agreements(cases):
    path = HERE/'new_contract_agreements.csv'
    rows = csv_rows(path)
    positions = {(r['instance_id'],int(r['budget'])) for r in rows}
    if positions!={(iid,budget) for iid in cases for budget in BUDGETS} or len(rows)!=len(positions):
        raise ValueError('offline agreement rows do not match the sealed case/checkpoint pairs')
    for row in rows:
        case = cases[row['instance_id']]
        checkpoint = case['protocol'].get(row['budget'])
        observed_rounds = case['proposal_rounds']
        rounds = None if checkpoint is None else checkpoint['proposals']
        if (type(observed_rounds) is not int or observed_rounds<0 or
                (rounds is not None and (type(rounds) is not int or not 0<=rounds<=observed_rounds))):
            raise ValueError('invalid or inconsistent sealed proposal-round tally')
        if case['protocol_status']=='COMPLETE' and observed_rounds!=sum(e['message']=='PROPOSE' for e in case['history']):
            raise ValueError('sealed proposal-round total differs from the completed history')
        row.update(checkpoint_proposal_rounds=rounds, observed_case_proposal_rounds=observed_rounds,
                   mechanism_groups=None, normalized_constructors=None, required_capabilities=None)
        if row['status']=='AGREEMENT':
            if (checkpoint is None or checkpoint['agreement'] is not True or
                    checkpoint['representative']!=row['representative'] or checkpoint['signature']!=row['signature']):
                raise ValueError('offline verified witness differs from the sealed protocol result')
            codes, constructors, roles = footprint(row['representative'])
            num_groups = 0 if codes=='STATIC' else len(codes.split('+'))
            if num_groups!=int(row['mechanism_group_count']):
                raise ValueError('normalized witness groups differ from its verified signature groups')
            row.update(mechanism_groups=codes,normalized_constructors=constructors,
                       required_capabilities=json.dumps(roles,separators=(',',':')))
    write_csv(path,tuple(rows[0]),rows)


def mechanism_sections():
    """Derive public footprint summaries from completed, checked CSV rows."""
    novel_candidates = [r for r in csv_rows(HERE/'new_contract_candidates.csv') if r['depth3_only']=='True']
    accepted_candidates = [r for r in novel_candidates if r['independently_verified']=='True']
    new_candidates = [r for r in accepted_candidates if r['old_O1_agreement']=='False']
    winners = [r for r in csv_rows(HERE/'new_contract_agreements.csv')
               if r['budget']=='5000' and r['status']=='AGREEMENT' and r['depth3_only']=='True']
    counts = Counter(footprint(r['representative'])[0] for r in accepted_candidates)
    old_failed_counts = Counter(footprint(r['representative'])[0] for r in new_candidates)
    winner_counts = Counter(r['mechanism_groups'] for r in winners)
    lines = ['## Public footprint of novel verified contracts','',
             f'The emitted depth3-only occurrences comprise {len({r["signature"] for r in novel_candidates}):,} '
             f'distinct compact signatures across the grid. Of these, '
             f'{len({r["signature"] for r in accepted_candidates}):,} were independently verified on at least one queried instance.', '',
             'C denotes If, D denotes Delay, P denotes Sequence or ValidFor, and O denotes Offload. '
             'The counts use the normalized whole-contract capability footprint. They do not attribute '
             'acceptance causally to an individual constructor. Independently verified candidates in '
             'the captured prefix and selected bilateral agreements use separate columns.','',
             '| Group footprint | Verified novel emitted candidates | Verified novel emitted candidates where old O1 failed | Selected novel agreements at B=5000 |',
             '|---|---:|---:|---:|']
    for code in sorted(counts.keys()|winner_counts.keys()):
        lines.append(f'| {code} | {counts[code]} | {old_failed_counts[code]} | {winner_counts[code]} |')
    lines.extend(['','| Instance | Depth | Group footprint | Constructors | Verification calls | Proposal rounds | Old O1 agreement | Signed Nash difference |',
                  '|---|---:|---|---|---:|---:|---|---:|'])
    for r in winners:
        delta = r['signed_delta_Nash']
        delta_text = '—' if delta=='' else f'{float(delta):+.9f}'
        lines.append(f"| `{r['instance_id']}` | {r['actual_depth']} | {r['mechanism_groups']} | "
                     f"{r['normalized_constructors']} | {r['verification_calls']} | {r['checkpoint_proposal_rounds']} | "
                     f"{r['old_O1_agreement']} | {delta_text} |")
    for r in winners:
        cap = ', '.join(f'`{x}`' for x in json.loads(r['required_capabilities']))
        lines.extend(['',f"### Verified depth3-only agreement on `{r['instance_id']}`",'',
                      f"Normalized witness `{r['representative']}`.",'',f'Required capabilities were {cap}.','',
                      f"At B=5000 the selected witness had uA {float(r['uA']):.9f}, uN {float(r['uN']):.9f}, "
                      f"and Nash {float(r['nash']):.9f}. Its acceptance followed {r['checkpoint_proposal_rounds']} "
                      f"proposal rounds and {r['verification_calls']} exact verifier calls."])
    lines.extend(['','The agreement CSV gives the checkpoint proposal rounds, total rounds observed in '
                  'the sealed case, and mechanism groups, constructors, and required capabilities for '
                  'each verified winner. Missing checkpoint results have no completed round counter. '
                  'The case-level observed counter is still retained.'])
    return lines


def append_mechanisms(cases):
    enrich_agreements(cases)
    report_file = ROOT/'DEPTH3_NEW_CONTRACT_ANALYSIS.md'
    previous = report_file.read_text(encoding='utf-8').split('\n## Public footprint of novel verified contracts',1)[0]
    write_report(report_file,[previous.rstrip(),'',*mechanism_sections()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',default=HERE/'development/search_seal.json',type=Path)
    parser.add_argument('--mechanisms-only',action='store_true',
                        help='append a footprint report from the checked offline CSVs without loading any graph')
    args = parser.parse_args()
    if args.mechanisms_only:
        cases, _, _ = sealed_cases(args.seal)
        append_mechanisms(cases)
        return
    cases, copies, seal_sha = sealed_cases(args.seal)
    auth = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    if ((ROOT/'FROZEN_CONFIG.yaml').exists() or
            auth['namespace_authorizations']['CONFIRM']['allowed'] is not False):
        raise ValueError('unexpected confirmation state')
    instances = read_json(ROOT/'results/pilot/instances_manifest.json')
    required = set(depth3_slots())
    if set(cases)!=required or len(required)!=24:
        raise ValueError('unexpected sealed fixed depth-3 query scope')
    if memory_status()[1] < 2048*(1<<20):
        raise MemoryError('PAUSED_MEMORY: frozen depth≤2 comparator needs at least 2 GiB available')
    # This is the first frozen graph load in this offline executable.
    library = FastLibrary.from_graph(scope='pilot-execution')
    all_candidates, all_agreements = [], []
    for iid,case in cases.items():
        inst, identity = frozen_instance(iid,case,copies[iid],instances)
        b2,o1 = frozen_outcomes(iid,identity)
        candidates, agreements = compare_case(iid,case,inst,library,b2,o1)
        all_candidates.extend(candidates)
        all_agreements.extend(agreements)
        print(f'{iid}: {len(candidates)} certified emitted, '
              f'{sum(r["depth3_only"] for r in candidates)} novel, '
              f'B5000={agreements[-1]["status"]}',flush=True)
    candidate_fields = tuple(dict.fromkeys(k for row in all_candidates for k in row)) or ('instance_id','rank','signature')
    agreement_fields = tuple(dict.fromkeys(k for row in all_agreements for k in row))
    write_csv(HERE/'new_contract_candidates.csv',candidate_fields,all_candidates)
    write_csv(HERE/'new_contract_agreements.csv',agreement_fields,all_agreements)
    write_analysis_report(cases,all_candidates,all_agreements,seal_sha)
    append_mechanisms(cases)


if __name__=='__main__':
    main()

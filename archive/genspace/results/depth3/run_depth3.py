"""Locked development runner for derived depth-three and depth-two regression queries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from time import perf_counter
from types import ModuleType

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = ROOT/'results/grammar_gate'
DEDUP = ROOT/'results/grammar_dedup'
sys.path[:0] = [str(ROOT),str(LEGACY),str(DEDUP),str(ROOT/'results/method_dev_v1')]

from depth_search import DepthCursor
from grammar_search import Limits, SearchLimit
import protocol_adapter
from run_search import MemoryProbe, atomic_json
from runtime import verification_public
from src.instances import deserialize_instance
from tools.smoke_01 import memory_status

MIB = 1 << 20
K3 = (10,100,500)
K2 = (10,50,100,500)
LIMITS = dict(wall_seconds=120.,worker_rss_mib=2048,partial_expanded=2_000_000,frontier_size=260_000,
              prelaunch_available_mib=1280,emergency_available_mib=768)
CERTIFIED = 'EXACT_TOPK_CERTIFIED'
CAPPED = 'NOT_CERTIFIED_WITHIN_BUDGET'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def guard_factory():
    path = LEGACY/'guard.py'
    guard = ModuleType('depth3_online_guard')
    sys.modules[guard.__name__] = guard
    guard.__file__ = str(path)
    old = "scope = root/'results'/'grammar_gate'"
    source = path.read_text(encoding='utf8')
    if source.count(old)!=1:
        raise ValueError('guard scope mismatch')
    source = source.replace(old,"scope = root/'results'/'depth3'")
    exec(compile(source,str(path)+' [depth3 output scope]','exec'),guard.__dict__)
    return guard.graph_guard


def source_hashes():
    paths = [HERE/'run_depth3.py',HERE/'depth_search.py',HERE/'check_reduced_depth3.py',
             DEDUP/'dedup_search.py',LEGACY/'grammar_search.py',LEGACY/'abstract_semantics.py',
             LEGACY/'guard.py',LEGACY/'protocol_adapter.py']
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}


def select_slots(phase):
    slots = read(ROOT/'PILOT01_PLAN_TEMPLATE.json')['instances']
    slots = [s for s in slots if s['seed_index']==0]
    if len(slots)!=96:
        raise ValueError('pre-existing fixed grid does not have 96 cases')
    if phase=='regression':
        return slots
    slots = [s for s in slots if s['configuration']['preference_conflict']=='high'
             and s['configuration']['composition_depth']==2]
    unique = {(s['family'],s['configuration']['resource_pressure'],s['configuration']['capability_richness']) for s in slots}
    if len(slots)!=24 or len(unique)!=24:
        raise ValueError('pre-existing depth3 query grid does not have 24 cases')
    return slots


class ObservedStream:
    def __init__(self, factory, top_k):
        self.factory = factory
        self.cursor = None
        self.ks = top_k
        self.prefix = []
        self.certificates = {}
        self.hasher = hashlib.sha256()

    def _snapshot(self, k, exhausted=False):
        m = self.cursor.metrics()
        boundary = self.prefix[-1] if self.prefix else None
        self.certificates[str(k)] = dict(status=CERTIFIED,returned=len(self.prefix),
            boundary_score=boundary['score'] if boundary else None,boundary_key=boundary['key'] if boundary else None,
            frontier_min_lb=m['frontier_min_lb'],frontier_remaining=m['frontier_remaining'],
            buffered_best_score=m['buffered_best_score'],buffered_best_key=m['buffered_best_key'],
            full_domain_exhausted=exhausted,elapsed_s=m['wall_s'],prefix_sha256=self.hasher.hexdigest(),metrics=m)

    def next_contract(self):
        if self.cursor is None:
            self.cursor = self.factory()
        entry = self.cursor.next_contract()
        if entry is None:
            if not self.cursor.exhausted:
                raise AssertionError('uncertified exhaustion')
            for k in self.ks:
                if str(k) not in self.certificates:
                    self._snapshot(k,exhausted=True)
            return None
        if len(self.prefix)<max(self.ks):
            self.hasher.update(struct.pack('>d',entry.score))
            self.hasher.update(entry.key)
            self.prefix.append(dict(key=entry.key.hex(),score=entry.score,witness=entry.witness))
            if len(self.prefix) in self.ks:
                self._snapshot(len(self.prefix))
        return entry


def run_case(instance, slot, phase):
    start = perf_counter()
    deadline = start+LIMITS['wall_seconds']
    public = verification_public(instance.public)
    effective_depth = 3 if phase=='development' else int(instance.public.configuration['composition_depth'])
    limits = Limits(LIMITS['wall_seconds'],LIMITS['partial_expanded'],LIMITS['frontier_size'])
    probe = MemoryProbe(LIMITS['worker_rss_mib']*MIB)
    stream = ObservedStream(lambda:DepthCursor(public,effective_depth,limits,probe,deadline=deadline),
                            K3 if phase=='development' else K2)
    prior_batch = protocol_adapter._BatchVerifier
    observed = dict(verification_calls=0,proposal_rounds=0,peak_working_set_bytes=probe())

    class BatchObserver(prior_batch):
        def check(self, candidates):
            if perf_counter()>=deadline:
                raise SearchLimit('wall_time_limit')
            results = super().check(candidates)
            observed['verification_calls'] = self.native.calls
            observed['peak_working_set_bytes'] = max(observed['peak_working_set_bytes'],probe())
            return results

    prior_negotiate = protocol_adapter.negotiate

    def observed_negotiate(*args, **kwargs):
        if perf_counter()>=deadline:
            raise SearchLimit('wall_time_limit')
        winner,history = prior_negotiate(*args,**kwargs)
        observed['proposal_rounds'] = sum(row['message']=='PROPOSE' for row in history)
        return winner,history

    result = dict(instance_id=slot['instance_id'],instance_hash=instance.instance_hash,
                  configuration=dict(instance.public.configuration),family=instance.public.family,
                  effective_depth=effective_depth,topk_status='NOT_RUN',protocol_status='NOT_RUN',
                  agreement_status='NOT_RUN',protocol={},history=[])
    if phase=='development':
        result['derived_query_id'] = slot['instance_id']+'__METHOD_D3'
    terminal_limit = None
    try:
        if phase=='development':
            protocol_adapter._BatchVerifier = BatchObserver
            protocol_adapter.negotiate = observed_negotiate
            try:
                outcomes,history,metrics = protocol_adapter.run_protocol(stream,public,instance.private,max_depth=3)
                result.update(protocol={str(k):v for k,v in outcomes.items()},history=history,protocol_timing=metrics,
                              protocol_status='COMPLETE')
                if outcomes[5000]['agreement']:
                    result['agreement_status'] = 'VERIFIED_AGREEMENT_PENDING_OFFLINE_CHECK'
                elif stream.cursor is not None and stream.cursor.exhausted:
                    result['agreement_status'] = 'EXHAUSTED_NO_AGREEMENT'
                else:
                    result['agreement_status'] = 'UNKNOWN'
            except SearchLimit as exc:
                result.update(protocol_status='LIMIT',protocol_limit=str(exc),agreement_status='UNKNOWN')
                terminal_limit = str(exc)
            finally:
                protocol_adapter._BatchVerifier,protocol_adapter.negotiate = prior_batch,prior_negotiate
        if terminal_limit is None:
            while len(stream.prefix)<max(stream.ks) and stream.next_contract() is not None:
                pass
    except SearchLimit as exc:
        terminal_limit = str(exc)
    except (AssertionError,ValueError) as exc:
        result['unsound_reason'] = str(exc) or type(exc).__name__
        result['topk_status'] = 'UNSOUND'
        result['agreement_status'] = 'UNKNOWN' if phase=='development' else 'NOT_RUN'

    unsafe = result['topk_status']=='UNSOUND'
    final_metrics = stream.cursor.metrics() if stream.cursor else {}
    for k in stream.ks:
        if unsafe or str(k) not in stream.certificates:
            prefix = stream.prefix[:k]
            cut_digest = hashlib.sha256()
            for entry in prefix:
                cut_digest.update(struct.pack('>d',entry['score']))
                cut_digest.update(bytes.fromhex(entry['key']))
            stream.certificates[str(k)] = dict(status='UNSOUND' if unsafe else CAPPED,
                returned=len(prefix),limit_reason=result.get('unsound_reason',terminal_limit or 'unresolved'),
                elapsed_s=perf_counter()-start,prefix_sha256=cut_digest.hexdigest(),
                frontier_min_lb=final_metrics.get('frontier_min_lb'),frontier_remaining=final_metrics.get('frontier_remaining'),
                buffered_best_score=final_metrics.get('buffered_best_score'),buffered_best_key=final_metrics.get('buffered_best_key'),
                full_domain_exhausted=bool(final_metrics.get('full_domain_exhausted')),metrics=final_metrics)
    result['topk'] = stream.prefix
    result['k_certificates'] = stream.certificates
    if not unsafe:
        result['topk_status'] = 'COMPLETE' if all(c['status']==CERTIFIED for c in stream.certificates.values()) else 'LIMIT'
        result['limit_reason'] = terminal_limit
    result['topk_metrics'] = final_metrics
    result['search_metrics'] = dict(result['topk_metrics'])
    result['verification_calls'] = observed['verification_calls']
    result['proposal_rounds'] = observed['proposal_rounds']
    result['peak_working_set_bytes'] = max(observed['peak_working_set_bytes'],result['topk_metrics'].get('peak_working_set_bytes',0))
    result['elapsed_s'] = perf_counter()-start
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('development','regression'),required=True)
    parser.add_argument('--reduced-evidence',type=Path,required=True)
    args = parser.parse_args()
    if memory_status()[1]<LIMITS['prelaunch_available_mib']*MIB:
        raise RuntimeError('PAUSED_MEMORY before online launch')
    auth = read(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    if (ROOT/'FROZEN_CONFIG.yaml').exists() or auth['namespace_authorizations']['CONFIRM']['allowed'] is not False:
        raise ValueError('unexpected confirmation state')
    sources = source_hashes()
    reduced = read(args.reduced_evidence)
    if reduced.get('status')!='PASS' or reduced.get('depth_search_sha256')!=sources['results/depth3/depth_search.py']:
        raise ValueError('independent reduced correctness no longer binds this cursor')
    slots = select_slots(args.phase)
    input_dir = ROOT/'results/pilot/instances'
    input_manifest = read(ROOT/'results/pilot/instances_manifest.json')
    sources_paths = [input_dir/(s['instance_id']+'.json') for s in slots]
    output = HERE/args.phase
    output.mkdir(exist_ok=True)
    seal_path = output/'search_seal.json'
    if seal_path.exists():
        raise FileExistsError('online batch already sealed')
    manifest = dict(phase=args.phase,instance_ids=[s['instance_id'] for s in slots],sources=sources,
                    effective_depth=3 if args.phase=='development' else 'original',limits=LIMITS,
                    python=sys.version, reduced_evidence_sha256=sha(args.reduced_evidence.read_bytes()),
                    tie_rule='score_then_unsigned_lexicographic_compact_key',
                    prefix_digest='sha256_concat_binary64_be_then_key',
                    selection_rule='all F1-F4, pressure and richness; conflict high and original depth 2; existing seed index 0' if args.phase=='development' else 'original seed index 0, all 96 configurations')
    plan_path = output/'online_manifest.json'
    if plan_path.exists() and manifest!=read(plan_path):
        raise ValueError('checkpoint manifest differs')
    if not plan_path.exists():
        atomic_json(plan_path,manifest)
    copied = output/'derived_inputs'
    if args.phase=='development':
        copied.mkdir(exist_ok=True)
    sealed = {}
    derived = {}
    with guard_factory()(ROOT,allowed_inputs=sources_paths,output_dir=output) as guard:
        for n,(slot,source) in enumerate(zip(slots,sources_paths),1):
            iid = slot['instance_id']
            raw = source.read_bytes()
            instance = deserialize_instance(raw.decode('utf8'))
            origin = dict(sha256=sha(raw),instance_hash=instance.instance_hash,
                          public_hash=instance.public_hash,private_hash=instance.private_hash)
            if origin!=input_manifest[iid] or instance.namespace!='GENSPACE-FAIL-01-PILOT':
                raise ValueError('existing input identity differs')
            if args.phase=='development':
                source_copy = copied/(iid+'__METHOD_D3.json')
                record = dict(derived_query_id=iid+'__METHOD_D3',source_instance_id=iid,
                              source_identity=origin,effective_depth=3,scope='development_method_extension',
                              source_record=json.loads(raw))
                if source_copy.exists() and read(source_copy)!=record:
                    raise ValueError('derived copy differs from original')
                if not source_copy.exists():
                    atomic_json(source_copy,record)
                derived[iid] = dict(path=source_copy.relative_to(HERE).as_posix(),sha256=sha(source_copy.read_bytes()))
            target = output/(iid+'.json')
            if target.exists():
                row = read(target)
                if row['instance_hash']!=origin['instance_hash'] or row['serialized_sha256']!=origin['sha256']:
                    raise ValueError('existing checkpoint has another source')
            else:
                row = run_case(instance,slot,args.phase)
                row['serialized_sha256'] = origin['sha256']
                row['source_sha256'] = origin['sha256']
                if args.phase=='development':
                    row['derived_input_sha256'] = derived[iid]['sha256']
                atomic_json(target,row)
            sealed[iid] = dict(path=target.relative_to(HERE).as_posix(),sha256=sha(target.read_bytes()))
            print(f'{n}/{len(slots)} {iid} topk={row["topk_status"]}:{len(row["topk"])} '
                  f'protocol={row["protocol_status"]} time={row["elapsed_s"]:.3f}s '
                  f'states={row["search_metrics"].get("exact_state_keys",0)}',flush=True)
        atomic_json(seal_path,dict(complete_batch=True,cases=sealed,manifest=manifest,
                                   guard=guard.snapshot(),derived_inputs=derived))


if __name__=='__main__':
    main()

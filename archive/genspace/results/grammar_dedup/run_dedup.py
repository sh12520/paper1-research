"""Graph-free validation worker for the one contextual deduplication design."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = ROOT/'results/grammar_gate'
sys.path[:0] = [str(ROOT), str(LEGACY), str(ROOT/'results/method_dev_v1')]

import run_search as original
from grammar_search import Limits
from dedup_search import DedupCursor
from src.instances import deserialize_instance
from tools.smoke_01 import memory_status

MIB = 1 << 20
G4_P95_LIMIT = 0.9683405700066942
G4_COHORT_N = 340


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


def guard_factory():
    """Reuse the audited hook, changing its writable directory for this worker."""
    path = LEGACY/'guard.py'
    guard = ModuleType('dedup_online_guard')
    sys.modules[guard.__name__] = guard
    guard.__file__ = str(path)
    old = "scope = root/'results'/'grammar_gate'"
    source = path.read_text(encoding='utf8')
    if source.count(old)!=1:
        raise ValueError('guard scope not found exactly once')
    source = source.replace(old, "scope = root/'results'/'grammar_dedup'")
    exec(compile(source,str(path)+' [output-scope adapter]','exec'),guard.__dict__)
    return guard.graph_guard


def source_hashes():
    own = ('run_dedup.py','dedup_search.py')
    old = ('run_search.py','grammar_search.py','abstract_semantics.py','guard.py','protocol_adapter.py')
    sources = [*(HERE/name for name in own),*(LEGACY/name for name in old)]
    return {p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sources}


def demand_correctness(path, sources):
    """Gate performance before the worker reads any serialized instance."""
    if path is None:
        raise ValueError('independent 96/96 correctness evidence is required')
    evidence = read_json(path)
    if (evidence['performance_allowed'] is not True or evidence['correctness_status']!='PASS'
            or evidence['instance_count']!=96 or evidence['online_sources']!=sources):
        raise ValueError('independent correctness evidence is incomplete or incompatible')
    budgets = {'topk':{'10','50','100','500'},'protocol':{'100','500','5000'}}
    for section,required in budgets.items():
        if (set(evidence[section])!=required or
                any(row!={'exact':96,'mismatch':0,'incomplete':0} for row in evidence[section].values())):
            raise ValueError('correctness budgets do not all agree')
    for key,name in (('topk','topk_correctness.csv'),('protocol','agreement_correctness.csv')):
        if digest((path.parent/name).read_bytes())!=evidence['files_sha256'][key]:
            raise ValueError('correctness comparison bytes have changed')
    if digest((path.parent.parent/'search_seal.json').read_bytes())!=evidence['seal_sha256']:
        raise ValueError('correctness input seal has changed')
    return digest(path.read_bytes())


def p95_lower(measured_times):
    """Nonnegative lower bounds for all unmeasured members of the fixed cohort."""
    rows = sorted([0.]*(G4_COHORT_N-len(measured_times))+measured_times)
    offset = (G4_COHORT_N-1)*.95
    low = int(offset)
    return rows[low]+(rows[low+1]-rows[low])*(offset-low)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('correctness','diagnostic','performance'),required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--selection-file',type=Path)
    parser.add_argument('--correctness-evidence',type=Path)
    parser.add_argument('--stop-on-proven-g4-failure',action='store_true')
    args = parser.parse_args()
    if not args.output.replace('_','').isalnum():
        raise ValueError('invalid output name')
    if args.stop_on_proven_g4_failure and args.phase!='performance':
        raise ValueError('only the formal performance cohort can stop on proven G4 failure')
    if memory_status()[1] < 1280*MIB:
        raise RuntimeError('PAUSED_MEMORY below prior engineering prelaunch floor')
    auth = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    if (ROOT/'FROZEN_CONFIG.yaml').exists() or auth['namespace_authorizations']['CONFIRM']['allowed'] is not False:
        raise ValueError('unexpected confirmation state')
    sources = source_hashes()
    plan = read_json(original.PLAN_PATH)['instances']
    fixed = {s['instance_id'] for s in plan if s['seed_index']==0}
    certainty = None
    if args.phase=='correctness':
        chosen = fixed
        if args.selection_file is not None:
            raise ValueError('mandatory correctness uses the entire original fixed grid')
        limits, mode = Limits(60.,500000,260000),'both'
    else:
        certainty = demand_correctness(args.correctness_evidence,sources)
        chosen = set(read_json(args.selection_file))
        if args.phase=='performance' and len(chosen)!=G4_COHORT_N:
            raise ValueError('formal performance requires the original 340 high-cost instances')
        limits, mode = Limits(12.,300000,180000),'topk'
    slots = [s for s in plan if s['instance_id'] in chosen]
    if not slots or len(slots)!=len(chosen):
        raise ValueError('unknown or empty fixture scope')
    paths = [original.INSTANCE_DIR/(slot['instance_id']+'.json') for slot in slots]
    instance_manifest = read_json(original.INSTANCE_MANIFEST)
    output = HERE/args.output
    output.mkdir(exist_ok=True)
    seal_path = output/'search_seal.json'
    if seal_path.exists():
        raise FileExistsError('already sealed')
    expected = dict(requested_ids=[s['instance_id'] for s in slots], sources=sources,
                    phase=args.phase,mode=mode, python=sys.version,
                    limits=dict(wall_seconds_per_cursor=limits.wall_seconds,expanded=limits.expanded,
                                frontier=limits.frontier,working_set_mib=768),
                    correctness_sha256=certainty,early_g4_stop=args.stop_on_proven_g4_failure)
    online_manifest = output/'online_manifest.json'
    if online_manifest.exists() and read_json(online_manifest)!=expected:
        raise ValueError('checkpoint manifest differs')
    if not online_manifest.exists():
        original.atomic_json(online_manifest,expected)

    graph_guard = guard_factory()
    sealed, times = {}, []
    original.Cursor = DedupCursor
    with graph_guard(ROOT,allowed_inputs=paths,output_dir=output) as guard:
        for n,(slot,source) in enumerate(zip(slots,paths),1):
            iid = slot['instance_id']
            target = output/(iid+'.json')
            if target.exists():
                case = read_json(target)
                if case['instance_id']!=iid or case['serialized_sha256']!=instance_manifest[iid]['sha256']:
                    raise ValueError('wrong fixture in checkpoint')
            else:
                raw = source.read_bytes()
                inst = deserialize_instance(raw.decode('utf8'))
                identity = dict(sha256=digest(raw),instance_hash=inst.instance_hash,
                                public_hash=inst.public_hash,private_hash=inst.private_hash)
                if identity!=instance_manifest[iid] or inst.namespace!='GENSPACE-FAIL-01-PILOT':
                    raise ValueError('serialized fixture mismatch')
                case = original.search_case(inst,iid,limits,mode,768*MIB)
                case['fixed_config'] = iid in fixed
                case['serialized_sha256'] = identity['sha256']
                original.atomic_json(target,case)
            sealed[iid] = dict(path=target.relative_to(HERE).as_posix(),sha256=digest(target.read_bytes()))
            times.append(case['topk_metrics']['wall_s'])
            if n<=4 or n%10==0 or case['topk_status']!='COMPLETE' or (mode=='both' and case['protocol_status']!='COMPLETE'):
                print(f'{n}/{len(slots)} {iid} K={len(case["topk"])} topk={case["topk_status"]} '
                      f'protocol={case["protocol_status"]} public_search_s={times[-1]:.4f}',flush=True)
            if args.stop_on_proven_g4_failure and p95_lower(times)>G4_P95_LIMIT:
                print(f'G4 proven lower bound {p95_lower(times):.6f}s after {n}/{len(slots)} trials',flush=True)
                break
        stop_proof = None
        if len(sealed)<len(slots):
            stop_proof = dict(rule='p95_lower_bound_on_full_original_cohort',cohort_n=G4_COHORT_N,
                              observed=len(times),lower_bound=p95_lower(times),limit=G4_P95_LIMIT)
        manifest = dict(expected,instance_ids=list(sealed),stop_proof=stop_proof)
        original.atomic_json(seal_path,dict(complete_batch=True,cases=sealed,manifest=manifest,guard=guard.snapshot()))


if __name__=='__main__':
    main()

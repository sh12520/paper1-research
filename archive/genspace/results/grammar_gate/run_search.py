"""Isolated grammar-search worker over existing serialized development queries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'results/method_dev_v1')]

from grammar_search import Cursor, Limits, SearchLimit
from guard import graph_guard
from protocol_adapter import run_protocol
from runtime import verification_public
from src.instances import deserialize_instance
from tools.smoke_01 import memory_status, process_memory

MIB = 1 << 20
TOP_K = (10,50,100,500)
PLAN_PATH = ROOT/'PILOT01_PLAN_TEMPLATE.json'
INSTANCE_DIR = ROOT/'results/pilot/instances'
INSTANCE_MANIFEST = ROOT/'results/pilot/instances_manifest.json'


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    scratch = path.with_suffix('.pending')
    scratch.write_text(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n',encoding='utf8')
    scratch.replace(path)


class MemoryProbe:
    def __init__(self, ceiling_bytes):
        import os
        self.pid = os.getpid()
        self.ceiling = ceiling_bytes

    def __call__(self):
        if memory_status()[1] < 768*MIB:
            raise SearchLimit('system_available_memory_limit')
        used = process_memory(self.pid)[0]
        if used > self.ceiling:
            raise SearchLimit('worker_working_set_limit')
        return used


def search_case(instance, iid, limits, mode, working_set_ceiling):
    public = verification_public(instance.public)
    depth = int(instance.public.configuration['composition_depth'])
    sample = MemoryProbe(working_set_ceiling)
    result = {'instance_id':iid, 'family':instance.public.family,
              'configuration':dict(instance.public.configuration),
              'instance_hash':instance.instance_hash, 'topk':[], 'k_certificates':{},
              'topk_status':'NOT_RUN', 'protocol_status':'NOT_RUN'}
    if mode in ('both','topk'):
        cursor = Cursor(public,depth,limits,sample)
        complete = False
        try:
            for k in TOP_K:
                while len(result['topk']) < k and not complete:
                    entry = cursor.next_contract()
                    if entry is None:
                        complete = True
                        break
                    result['topk'].append(dict(key=entry.key.hex(),score=entry.score,witness=entry.witness))
                result['k_certificates'][str(k)] = cursor.metrics()
            result['topk_status'] = 'COMPLETE'
        except SearchLimit as exc:
            result['topk_status'] = 'LIMIT'
            result['topk_limit'] = str(exc)
        result['topk_metrics'] = cursor.metrics()
        del cursor

    if mode in ('both','protocol'):
        state = {}

        def factory():
            state['cursor'] = Cursor(public,depth,limits,sample)
            return state['cursor']

        started = perf_counter()
        try:
            outcomes, history, timings = run_protocol(factory,public,instance.private,max_depth=depth)
            result.update(protocol_status='COMPLETE',protocol=outcomes, history=history, protocol_timing=timings)
        except SearchLimit as exc:
            result['protocol_status'] = 'LIMIT'
            result['protocol_limit'] = str(exc)
        result['protocol_metrics'] = state['cursor'].metrics() if 'cursor' in state else dict(emitted=0)
        result['protocol_total_elapsed_s'] = perf_counter()-started
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--only', nargs='*')
    parser.add_argument('--selection-file', type=Path)
    parser.add_argument('--mode', choices=('both','topk','protocol'), default='both')
    parser.add_argument('--wall', type=float, required=True)
    parser.add_argument('--expanded', type=int, required=True)
    parser.add_argument('--frontier', type=int, required=True)
    parser.add_argument('--memory-mib', type=int, default=768)
    args = parser.parse_args()
    if not args.output.replace('_','').isalnum() or min(args.wall,args.expanded,args.frontier,args.memory_mib)<=0:
        raise ValueError('invalid run output name or limits')
    if args.only and args.selection_file:
        raise ValueError('only one query selection input is allowed')
    auth = read_json(ROOT/'PILOT_AUTHORIZATION_STATE.json')
    if (ROOT/'FROZEN_CONFIG.yaml').exists() or auth['namespace_authorizations']['CONFIRM']['allowed'] is not False:
        raise ValueError('unexpected confirmation state')
    if memory_status()[1] < 1280*MIB:
        raise RuntimeError('PAUSED_MEMORY below engineering prelaunch floor of 1,280 MiB')

    plan = read_json(PLAN_PATH)['instances']
    fixed = {slot['instance_id'] for slot in plan if slot['seed_index']==0}
    selected = set(args.only or (read_json(args.selection_file) if args.selection_file else fixed))
    slots = [slot for slot in plan if slot['instance_id'] in selected]
    if not slots or len(slots)!=len(selected):
        raise ValueError('query IDs must belong to the immutable serialized instance plan')
    inputs = [INSTANCE_DIR/(slot['instance_id']+'.json') for slot in slots]
    manifest = read_json(INSTANCE_MANIFEST)
    output = OUT/args.output
    output.mkdir(exist_ok=True)
    seal_path = output/'search_seal.json'
    if seal_path.exists():
        raise FileExistsError('online batch has already been sealed')
    source_names = ('run_search.py','grammar_search.py','abstract_semantics.py','guard.py','protocol_adapter.py')
    run_manifest = dict(instance_ids=[s['instance_id'] for s in slots],
                        fixed_config_coverage=len(selected & fixed),
                        sources={name:hash_file(OUT/name) for name in source_names},
                        limits=dict(wall_seconds_per_cursor=args.wall,expanded=args.expanded,frontier=args.frontier,
                                    working_set_mib=args.memory_mib),
                        mode=args.mode, python=sys.version)
    path = output/'online_manifest.json'
    if path.exists() and read_json(path)!=run_manifest:
        raise ValueError('existing online checkpoint uses other sources/limits/queries')
    if not path.exists():
        atomic_json(path,run_manifest)
    limits = Limits(args.wall,args.expanded,args.frontier)
    sealed = {}
    with graph_guard(ROOT,allowed_inputs=inputs,output_dir=output) as guard:
        for n,(slot,source) in enumerate(zip(slots,inputs),1):
            iid = slot['instance_id']
            target = output/(iid+'.json')
            if target.exists():
                case = read_json(target)
            else:
                raw = source.read_bytes()
                inst = deserialize_instance(raw.decode('utf8'))
                identity = dict(sha256=hashlib.sha256(raw).hexdigest(),instance_hash=inst.instance_hash,
                                public_hash=inst.public_hash,private_hash=inst.private_hash)
                if identity != manifest[iid] or inst.namespace != 'GENSPACE-FAIL-01-PILOT':
                    raise ValueError(f'invalid serialized input {iid}')
                case = search_case(inst,iid,limits,args.mode,args.memory_mib*MIB)
                case['fixed_config'] = slot['seed_index']==0
                case['serialized_sha256'] = identity['sha256']
                atomic_json(target,case)
            sealed[iid] = {'path':target.relative_to(OUT).as_posix(),'sha256':hash_file(target)}
            print(f'{n}/{len(slots)} {iid} topk={case["topk_status"]}:{len(case["topk"])} '
                  f'protocol={case["protocol_status"]} {case.get("topk_metrics",{})}',flush=True)
        evidence = guard.snapshot()
        atomic_json(seal_path,dict(complete_batch=True,cases=sealed,guard=evidence,manifest=run_manifest))


if __name__ == '__main__':
    main()

"""Full independent syntax reference vs serialized compact graph.

This evaluates the AST interpreter for every syntactic tree. It NEVER invokes
compact transfer or DP generation. Reference records are complete 49-byte
signatures encoded as hex, externally deduplicated; graph signatures are read
from their deterministic sorted stream. Equality is exact, not hash-based.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import heapq
import json
import os
from pathlib import Path
import struct
import time
from itertools import zip_longest
from src.compact_semantics import CompactEncoder
from src.engine import Domain, enumerate_compositions
from src.enumeration import exact_syntax_count
from src.fingerprints import fingerprint
from tools.audit_external_reference import fixture
from tools.external_reference import external_unique, _iter_gzip, _unique_sorted


def graph_keys(path):
    with gzip.open(path, 'rb') as inp:
        if inp.read(4) != b'GSG1': raise ValueError('invalid graph magic')
        length = inp.read(4)
        if len(length) != 4: raise ValueError('incomplete graph header')
        size = struct.unpack('>I',length)[0]
        if size > 100_000_000: raise ValueError('implausible graph header')
        header = json.loads(inp.read(size))
        if header.get('format') != 'GENSPACE-GRAPH-v1' or header.get('key_bytes') != 49:
            raise ValueError('unsupported graph format')
        previous = None
        while True:
            record=inp.read(56)
            if not record: break
            if len(record)!=56: raise ValueError('truncated graph record')
            key=record[:49]
            if previous is not None and key <= previous: raise ValueError('graph keys not strictly sorted')
            previous=key
            yield key.hex().encode('ascii')+b'\n'


def worker(part, workers, output, profile_count, depth):
    p=fixture(profile_count)
    domain=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
    enc=CompactEncoder(p)
    count=0; start=time.perf_counter()
    def records():
        nonlocal count
        for index,node in enumerate(enumerate_compositions(domain,depth,p.capabilities)):
            if index % workers != part: continue
            key=enc.encode(node)
            if len(key)!=49: raise ValueError('unexpected key length; graph representation incompatible')
            count+=1
            if count % 50000 == 0:
                print('worker',part,'syntax',count,'seconds',round(time.perf_counter()-start,2),flush=True)
            yield key.hex().encode('ascii')+b'\n'
    info=external_unique(records(),output,workspace=output.parent,chunk_size=20000,merge_width=32)
    info.update(worker=part, seconds=time.perf_counter()-start)
    return info


def compare(reference_paths, graph_path):
    left = _unique_sorted(heapq.merge(*(_iter_gzip(p) for p in reference_paths)))
    right = graph_keys(graph_path)
    sentinel=object(); left_count=right_count=0; first_mismatch=None
    for left_key,right_key in zip_longest(left,right,fillvalue=sentinel):
        if left_key is not sentinel: left_count+=1
        if right_key is not sentinel: right_count+=1
        if first_mismatch is None and left_key != right_key:
            first_mismatch=(None if left_key is sentinel else left_key.decode('ascii').strip(),
                            None if right_key is sentinel else right_key.decode('ascii').strip())
    return {'reference_unique_count':left_count,'graph_unique_count':right_count,
            'exact_bytewise_sets_equal':first_mismatch is None,'first_mismatch':first_mismatch}


def run(output, graph, workers, profiles, depth):
    output=Path(output); graph=Path(graph)
    output.mkdir(parents=True,exist_ok=True)
    report=output/'report.json'; reference=[output/f'reference-{i}.gz' for i in range(workers)]
    if report.exists() or any(x.exists() for x in reference): raise FileExistsError('Refusing to overwrite audit')
    if workers not in range(1,9): raise ValueError('workers must be 1..8')
    before=fingerprint(); p=fixture(profiles)
    domain=Domain(p.b2_profiles,p.conditions,p.durations,p.offsets,p.intervals,p.offload_levels)
    expected=exact_syntax_count(domain,depth,p.capabilities)
    start=time.perf_counter(); results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(worker,i,workers,reference[i],profiles,depth) for i in range(workers)]
        for future in as_completed(futures):
            info=future.result(); results.append(info); print('completed',info,flush=True)
    if sum(x['input_count'] for x in results)!=expected: raise RuntimeError('incomplete syntax stream')
    if not graph.exists(): raise FileNotFoundError(graph)
    comparison=compare(reference,graph)
    after=fingerprint()
    if before != after: raise RuntimeError('source/config/dependencies changed during audit')
    result={'fixture':'synthetic public-only; no seed', 'profiles':profiles,'depth':depth,
            'workers':workers,'expected_syntax_count':expected,'partitions':sorted(results,key=lambda x:x['worker']),
            'comparison':comparison,'wall_seconds':time.perf_counter()-start, 'fingerprint':before,
            'scope':'full compact bytes; no hash-only comparison'}
    report.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--graph',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--profiles',type=int,choices=(2,27),default=27)
    parser.add_argument('--depth',type=int,choices=(1,2),default=2)
    args=parser.parse_args()
    result=run(args.output_dir,args.graph,args.workers,args.profiles,args.depth)
    print(json.dumps({k:v for k,v in result.items() if k!='fingerprint'},indent=2),flush=True)
    if not result['comparison']['exact_bytewise_sets_equal']: raise SystemExit(1)

if __name__=='__main__': main()

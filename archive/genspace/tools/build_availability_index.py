"""Build availability-conditioned, class-aligned exact witness indices.

Engineering-only public precomputation; no research seeds or private utilities.
Unmodelled availability patterns must fail closed. This does not run an experiment.
"""
from __future__ import annotations
import gzip, hashlib, json, struct, time, ctypes
from ctypes import wintypes
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
from src.compact_dp import compact_library
from src.compact_graph import graph_library
from src.instances import generate_instance
from src.registry import default_registry
from src.fingerprints import fingerprint
from src.engineering_depth2 import read_graph
from src.engine import Domain, enumerate_compositions
from src.compact_semantics import CompactEncoder
from src.enumeration import syntax_key

GROUPS=(('observe_motion_state','apply_conditional_policy'),('apply_phased_policy',),('schedule_start',),('enable_edge_offload','reserve_edge_compute'),('set_validity_interval',))
# Four random structural groups, validity always present, plus negative control.
PATTERNS=tuple(range(16,32))+(0,)
OUT=Path('results/engineering/availability_indices')
GRAPH=Path('results/engineering/semantic_library.graph.gz')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


class _Memory(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t),('PrivateUsage',ctypes.c_size_t)]

def memory():
    obj=_Memory(); obj.cb=ctypes.sizeof(obj)
    getproc=ctypes.windll.kernel32.GetCurrentProcess; getproc.restype=wintypes.HANDLE
    getinfo=ctypes.windll.psapi.GetProcessMemoryInfo
    getinfo.argtypes=(wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD)
    if not getinfo(getproc(),ctypes.byref(obj),obj.cb): raise OSError('process memory unavailable')
    return obj


def main():
    started=time.perf_counter(); OUT.mkdir(parents=True,exist_ok=True)
    original=fingerprint(); graph_hash=sha(GRAPH)
    cfg={'resource_pressure':'low','preference_conflict':'medium','capability_richness':'rich','composition_depth':2}
    instance=generate_instance('F1',cfg,'availability-index-basis',namespace='GENSPACE-FAIL-01-ENGINEERING')
    base=instance.public; roles=tuple(sorted(default_registry()))
    header,rich=read_graph(GRAPH)
    keys=[key for key,_ in rich]; del rich
    if len(keys)!=1394064 or keys!=sorted(keys) or len(set(keys))!=len(keys): raise ValueError('invalid rich graph')
    lookup={key:i for i,key in enumerate(keys)}
    raw=np.frombuffer(b''.join(keys),dtype=np.uint8).reshape(-1,49)
    required=np.zeros(len(keys),dtype=np.uint16)
    for i in range(len(roles)): required |= (raw[:,1+2*i]!=255).astype(np.uint16)<<i
    entries=[]
    for pattern in PATTERNS:
        t=time.perf_counter(); available=set(roles)
        for i,group in enumerate(GROUPS):
            if not pattern & (1<<i): available.difference_update(group)
        public=replace(base,capabilities=tuple(sorted(available)))
        def progress(pairs,n):
            rss=memory()
            if max(rss.WorkingSetSize,rss.PrivateUsage)>3500*1024*1024: raise MemoryError('availability build memory guard')
            if time.perf_counter()-started>1800: raise TimeoutError('availability build 30-minute guard')
        graph=graph_library(public,progress)
        d1=compact_library(public,1)
        # Independent legacy syntax enumeration: exact d1 set and lexical witness.
        domain=Domain(public.b2_profiles,public.conditions,public.durations,public.offsets,public.intervals,public.offload_levels)
        encoder=CompactEncoder(public); legacy={}
        for node in enumerate_compositions(domain,1,available):
            key=encoder.encode(node); witness=syntax_key(node)
            if key not in legacy or witness<legacy[key]: legacy[key]=witness
        if d1!=legacy: raise ValueError(f'depth1 legacy discrepancy: pattern {pattern}')
        if any(k not in lookup for k in graph.entries): raise ValueError('variant has unexpected signature')
        allowed=sum(1<<i for i,r in enumerate(roles) if r in available)
        expected=(required & np.uint16((~allowed)&0xFFF))==0
        actual=np.zeros(len(keys),dtype=bool)
        for key in graph.entries: actual[lookup[key]]=True
        mismatch=int(np.count_nonzero(actual!=expected))
        if mismatch: raise ValueError(f'variant {pattern} has {mismatch} class-set discrepancies')
        ops=sorted({v[0] for v in graph.entries.values()}); params=sorted({v[1] for v in graph.entries.values()})
        opid={v:i for i,v in enumerate(ops)}; parid={v:i for i,v in enumerate(params)}
        if len(ops)>255 or len(params)>65535 or len(graph.pool)>65534: raise ValueError('index field overflow')
        tokens=bytearray(b'\xff'*(len(keys)*7))
        for key,(op,param,l,r) in graph.entries.items():
            ix=lookup[key]; struct.pack_into('>BHHH',tokens,7*ix,opid[op],parid[param],l if l>=0 else 65535,r if r>=0 else 65535)
        depth1=sorted((lookup[key],witness) for key,witness in d1.items())
        meta={'format':'GENSPACE-AVAILABILITY-v1','pattern':pattern,'groups':GROUPS,'pool':graph.pool,'operators':ops,'parameters':params,'depth1_witness':depth1,'rich_graph_sha256':graph_hash,'record_count':len(keys),'present_count':len(graph.entries),'source_hash':original['source_hash'],'config_hash':original['config_hash']}
        encoded=json.dumps(meta,separators=(',',':')).encode('utf8')
        target=OUT/f'availability_{pattern:02d}.bin.gz'
        with target.open('wb') as f:
            with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as gz: gz.write(b'GSA1'+struct.pack('>I',len(encoded))+encoded+tokens)
        item={'pattern':pattern,'sha256':sha(target),'bytes':target.stat().st_size,'semantic_count':len(graph.entries),'depth1_count':len(depth1),'class_set_mismatches':mismatch,'seconds':round(time.perf_counter()-t,3),'peak_rss_bytes':memory().PeakWorkingSetSize}
        entries.append(item)
        print('COMPLETED',json.dumps(item),flush=True)
        del graph,d1,actual,tokens
    end=fingerprint()
    if end!=original: raise ValueError('source/config fingerprint changed during index build; discard all outputs')
    manifest={'format':'GENSPACE-AVAILABILITY-MANIFEST-v1','rich_graph_sha256':graph_hash,'source_fingerprint':original,'patterns':entries,'total_seconds':round(time.perf_counter()-started,3),'namespace':'ENGINEERING-only precomputation'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('COMPLETE',len(entries),'seconds',manifest['total_seconds'],flush=True)

if __name__=='__main__': main()

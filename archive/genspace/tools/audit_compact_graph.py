"""Standalone compact-library audit; deterministic public grammar, no seeds."""
import argparse,time,ctypes
from ctypes import wintypes
from itertools import product
from types import SimpleNamespace
from dataclasses import asdict
from src.registry import default_registry
from src.models import Profile
from src.compact_graph import graph_library

class Memory(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t),('PrivateUsage',ctypes.c_size_t)]
def memory():
    obj=Memory(); obj.cb=ctypes.sizeof(obj)
    getproc=ctypes.windll.kernel32.GetCurrentProcess
    getproc.restype=wintypes.HANDLE
    process=getproc()
    getinfo=ctypes.windll.psapi.GetProcessMemoryInfo
    getinfo.argtypes=(wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD)
    if not getinfo(process,ctypes.byref(obj),obj.cb): raise OSError('GetProcessMemoryInfo failed')
    return obj

parser=argparse.ArgumentParser()
parser.add_argument('--seconds',type=int,default=1500)
parser.add_argument('--memory-mib',type=int,default=3500)
args=parser.parse_args()
reg=default_registry(); profiles=tuple(Profile(q,d,r) for q,d,r in product((.4,.6,.8),(1.,1.5,2.),(.5,.75,1.)))
p=SimpleNamespace(b2_profiles=profiles,conditions=('moving',),durations=(1,),offsets=(1,),intervals=((0,2),),offload_levels=('edge',),capabilities=tuple(reg),registry={k:asdict(v) for k,v in reg.items()},horizon=3,states=('still','moving'),public_constraints={'reservation_supported':True})
start=time.perf_counter()
def progress(i,n):
    elapsed=time.perf_counter()-start; m=memory()
    if i%100000==0: print('progress',i,'unique_partial',n,'seconds',round(elapsed,2),'rss_bytes',m.WorkingSetSize,'private_bytes',m.PrivateUsage,flush=True)
    if elapsed>args.seconds: raise TimeoutError('engineering time budget reached')
    if max(m.WorkingSetSize,m.PrivateUsage)>args.memory_mib*1024*1024: raise MemoryError('engineering memory guard reached')
try:
    library=graph_library(p,progress)
    m=memory()
    print('status complete','unique',len(library.entries),'precompute_seconds',round(time.perf_counter()-start,3),'peak_rss',m.PeakWorkingSetSize,'private_bytes',m.PrivateUsage,flush=True)
    import gzip,hashlib,json,struct
    from collections import Counter
    from pathlib import Path
    output=Path('results/engineering'); output.mkdir(parents=True,exist_ok=True)
    target=output/'semantic_library.graph.gz'
    ops=sorted({token[0] for token in library.entries.values()}); params=sorted({token[1] for token in library.entries.values()})
    op_id={v:i for i,v in enumerate(ops)}; param_id={v:i for i,v in enumerate(params)}
    if len(ops)>255 or len(params)>65535 or len(library.pool)>65534: raise ValueError('library serialization overflow')
    header=json.dumps({'format':'GENSPACE-GRAPH-v1','pool':library.pool,'operators':ops,'parameters':params,'key_bytes':49},separators=(',',':')).encode('utf8')
    serialize_start=time.perf_counter()
    with target.open('wb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as gz:
            gz.write(b'GSG1'+struct.pack('>I',len(header))+header)
            for key,tok in sorted(library.entries.items()):
                if len(key)!=49: raise ValueError('unexpected compact key size')
                op,param,l,r=tok
                gz.write(key+struct.pack('>BHHH',op_id[op],param_id[param],l if l>=0 else 65535,r if r>=0 else 65535))
    sha=hashlib.sha256()
    with target.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''): sha.update(part)
    from src.engine import ast_depth
    def tree_depth(n):
        if n[0]=='Static': return 0
        if n[0] in ('If','Sequence'): return 1+max(tree_depth(n[2]),tree_depth(n[3]))
        return 1+tree_depth(n[2])
    pooldepth=[tree_depth(json.loads(x)) for x in library.pool]
    depths=Counter(); roots=Counter()
    for op,param,l,r in library.entries.values():
        roots[op]+=1
        depths[0 if op=='Static' else 1+max(pooldepth[l],pooldepth[r] if r>=0 else 0)]+=1
    print('serialization_seconds',round(time.perf_counter()-serialize_start,3),'file_bytes',target.stat().st_size,'sha256',sha.hexdigest(),'roots',dict(roots),'depths',dict(depths),flush=True)
except (TimeoutError,MemoryError) as ex:
    print('status incomplete',str(ex),'seconds',round(time.perf_counter()-start,3),flush=True)

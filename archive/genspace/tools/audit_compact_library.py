"""Standalone compact-library audit; deterministic public grammar, no seeds."""
import argparse,time,ctypes
from ctypes import wintypes
from itertools import product
from types import SimpleNamespace
from dataclasses import asdict
from src.registry import default_registry
from src.models import Profile
from src.compact_dp import compact_library

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
    library=compact_library(p,2,progress)
    m=memory()
    print('status complete','unique',len(library),'seconds',round(time.perf_counter()-start,3),'peak_rss',m.PeakWorkingSetSize,'private_bytes',m.PrivateUsage,flush=True)
except (TimeoutError,MemoryError) as ex:
    print('status incomplete',str(ex),'seconds',round(time.perf_counter()-start,3),flush=True)

"""Windows process identity, descendant tracking, and memory safety guards.

Polling descendant enumeration cannot prove that a child which was born and
exited between observations did not exist; callers must record this limitation.
No benchmark data or preferences are read by this module.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import time
import uuid

PRELAUNCH_FLOOR = 2048 * 1024**2
EMERGENCY_FLOOR = 768 * 1024**2
K = ctypes.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
K.OpenProcess.restype = wintypes.HANDLE
K.CloseHandle.argtypes = [wintypes.HANDLE]
K.CloseHandle.restype = wintypes.BOOL
K.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
K.GetProcessTimes.restype = wintypes.BOOL

class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [('TotalUserTime',ctypes.c_longlong),('TotalKernelTime',ctypes.c_longlong),
                ('ThisPeriodTotalUserTime',ctypes.c_longlong),('ThisPeriodTotalKernelTime',ctypes.c_longlong),
                ('TotalPageFaultCount',wintypes.DWORD),('TotalProcesses',wintypes.DWORD),
                ('ActiveProcesses',wintypes.DWORD),('TotalTerminatedProcesses',wintypes.DWORD)]

K.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
K.CreateJobObjectW.restype=wintypes.HANDLE
K.OpenJobObjectW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR]
K.OpenJobObjectW.restype=wintypes.HANDLE
K.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
K.AssignProcessToJobObject.restype=wintypes.BOOL
K.GetCurrentProcess.restype=wintypes.HANDLE
K.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]
K.QueryInformationJobObject.restype=wintypes.BOOL

def create_job():
    name='Local\\GENSPACE_ENGINEERING_'+uuid.uuid4().hex
    handle=K.CreateJobObjectW(None,name)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    return handle,name

def join_job(name):
    """Bind the calling child and its future ordinary descendants to a job."""
    handle=K.OpenJobObjectW(0x0001 | 0x0004,False,name)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not K.AssignProcessToJobObject(handle,K.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        K.CloseHandle(handle)

def job_active(handle):
    info=JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
    if not K.QueryInformationJobObject(handle,1,ctypes.byref(info),ctypes.sizeof(info),None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'active_processes':int(info.ActiveProcesses),'total_processes':int(info.TotalProcesses),
            'terminated_processes':int(info.TotalTerminatedProcesses)}

def close_job(handle):
    if not K.CloseHandle(handle): raise ctypes.WinError(ctypes.get_last_error())

def identity(pid):
    """Return PID and 64-bit creation FILETIME, or None if PID is absent.

    Access denied and all other errors are failures, never absence.
    """
    handle = K.OpenProcess(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in (87, 1168):
            return None
        raise ctypes.WinError(error)
    try:
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not K.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'pid': int(pid), 'creation_time': (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)}
    finally:
        if not K.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

def classify(original):
    current = identity(original['pid'])
    if current is None:
        return {'status':'ABSENT', 'pass':True, 'original':original, 'current':None}
    if current != original:
        return {'status':'PID_REUSED', 'pass':True, 'original':original, 'current':current}
    return {'status':'ORIGINAL_PROCESS_OBJECT_STILL_ACCESSIBLE', 'pass':False, 'original':original, 'current':current}

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize',wintypes.DWORD), ('cntUsage',wintypes.DWORD), ('th32ProcessID',wintypes.DWORD), ('th32DefaultHeapID',ctypes.c_size_t), ('th32ModuleID',wintypes.DWORD), ('cntThreads',wintypes.DWORD), ('th32ParentProcessID',wintypes.DWORD), ('pcPriClassBase',ctypes.c_long), ('dwFlags',wintypes.DWORD), ('szExeFile',wintypes.WCHAR * 260)]

K.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
K.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
K.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
K.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
K.Process32FirstW.restype = K.Process32NextW.restype = wintypes.BOOL

def process_parents():
    snap = K.CreateToolhelp32Snapshot(2, 0)
    if snap == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry=PROCESSENTRY32W(); entry.dwSize=ctypes.sizeof(entry)
        parents={}
        ok=K.Process32FirstW(snap, ctypes.byref(entry))
        if not ok: raise ctypes.WinError(ctypes.get_last_error())
        while ok:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            ok=K.Process32NextW(snap, ctypes.byref(entry))
        error=ctypes.get_last_error()
        if error != 18: raise ctypes.WinError(error)
        return parents
    finally:
        K.CloseHandle(snap)

class LifecycleTracker:
    """Track child and observed descendants using stable process identities."""
    def __init__(self, process):
        self.process=process
        self.original=identity(process.pid)
        if self.original is None: raise RuntimeError('child exited before identity capture')
        self.handle_identity=int(process._handle)
        self.tracked={}
        self.observe()
    def observe(self):
        parents=process_parents(); frontier={self.original['pid']}; found=[]
        identities={self.original['pid']: self.original}
        identities.update({v['identity']['pid']:v['identity'] for v in self.tracked.values()})
        while frontier:
            children={pid for pid,parent in parents.items() if parent in frontier and pid not in frontier}
            children -= {x['pid'] for x in found}
            if not children: break
            for pid in children:
                child=identity(pid)
                if child is not None:
                    item={'identity':child, 'parent_pid':parents[pid],
                          'parent_identity':identities.get(parents[pid])}
                    self.tracked[(pid, child['creation_time'])]=item; found.append(child)
                    identities[pid]=child
            frontier=children
        return list(self.tracked.values())
    def finish(self, timeout=3.0, interval=0.2):
        p=self.process
        if p.poll() is None: raise RuntimeError('child has not terminated')
        code=p.wait()
        for stream in (p.stdin,p.stdout,p.stderr):
            if stream is not None and not stream.closed: stream.close()
        p._handle.Close()
        # A terminated Windows process object can remain briefly accessible
        # after our handle is closed. Record the time sequence and wait for
        # the *same identity* to disappear; never equate exit with absence.
        history=[]; deadline=time.monotonic()+timeout
        while True:
            root=classify(self.original)
            history.append({'timestamp':time.time(), **root})
            if root['pass'] or time.monotonic() >= deadline: break
            time.sleep(interval)
        descendants=[]
        for item in self.tracked.values():
            descendants.append({**item, 'exit_classification':classify(item['identity'])})
        return {'original':self.original,'handle_identity':self.handle_identity,'returncode':code,
                'root':root,'root_history':history,'descendants':descendants,
                'pass':code == 0 and root['pass'] and all(d['exit_classification']['pass'] for d in descendants),
                'limitation':'Process snapshots can miss descendants born and exited between polls.'}

def memory_sample():
    from tools.smoke_01 import memory_status
    total,available=memory_status()
    return {'timestamp':time.time(),'used':total-available,'available':available}

def prelaunch_guard(sampler=memory_sample, interval=0.2):
    samples=[]
    for _ in range(3):
        samples.append(sampler())
        if samples[-1]['available'] < PRELAUNCH_FLOOR: return {'pass':False,'samples':samples}
        time.sleep(interval)
    return {'pass':True,'samples':samples}

def emergency_guard(sampler=memory_sample):
    sample=sampler()
    return {'pass':sample['available'] >= EMERGENCY_FLOOR,'sample':sample}

"""Parent-owned suspended Windows Job launcher; never accesses research data."""
from __future__ import annotations
import ctypes, os, subprocess, time, uuid
from ctypes import wintypes as w
from .process_lifecycle import K, identity, job_active

class BASIC(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IO(ctypes.Structure):
    _fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class EXTENDED(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
class SECURITY(ctypes.Structure):
    _fields_=[('nLength',w.DWORD),('lpSecurityDescriptor',ctypes.c_void_p),('bInheritHandle',w.BOOL)]
class STARTUP(ctypes.Structure):
    _fields_=[('cb',w.DWORD),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),('dwX',w.DWORD),('dwY',w.DWORD),('dwXSize',w.DWORD),('dwYSize',w.DWORD),('dwXCountChars',w.DWORD),('dwYCountChars',w.DWORD),('dwFillAttribute',w.DWORD),('dwFlags',w.DWORD),('wShowWindow',w.WORD),('cbReserved2',w.WORD),('lpReserved2',ctypes.POINTER(ctypes.c_ubyte)),('hStdInput',w.HANDLE),('hStdOutput',w.HANDLE),('hStdError',w.HANDLE)]
class PROCESS(ctypes.Structure):
    _fields_=[('hProcess',w.HANDLE),('hThread',w.HANDLE),('dwProcessId',w.DWORD),('dwThreadId',w.DWORD)]

K.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];K.SetInformationJobObject.restype=w.BOOL
K.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)];K.IsProcessInJob.restype=w.BOOL
K.CreateProcessW.argtypes=[w.LPCWSTR,w.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,w.BOOL,w.DWORD,ctypes.c_void_p,w.LPCWSTR,ctypes.POINTER(STARTUP),ctypes.POINTER(PROCESS)];K.CreateProcessW.restype=w.BOOL
K.ResumeThread.argtypes=[w.HANDLE];K.ResumeThread.restype=w.DWORD
K.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];K.WaitForSingleObject.restype=w.DWORD
K.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];K.GetExitCodeProcess.restype=w.BOOL
K.TerminateProcess.argtypes=[w.HANDLE,w.UINT];K.TerminateProcess.restype=w.BOOL
K.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.POINTER(SECURITY),w.DWORD,w.DWORD,w.HANDLE];K.CreateFileW.restype=w.HANDLE
INVALID=ctypes.c_void_p(-1).value
KILL=0x2000; BREAKAWAY=0x800 | 0x1000

def _check(ok):
    if not ok:raise ctypes.WinError(ctypes.get_last_error())

def _close(h):
    if h:_check(K.CloseHandle(h))

def _file(path,access,disposition):
    sa=SECURITY(ctypes.sizeof(SECURITY),None,True)
    h=K.CreateFileW(str(path),access,3,ctypes.byref(sa),disposition,0x80,None)
    if h==INVALID:raise ctypes.WinError(ctypes.get_last_error())
    return h

class SuspendedJob:
    def __init__(self, process, thread, job, info):
        self.process_handle=process;self.thread_handle=thread;self.job_handle=job
        self.pid=info['pid'];self.identity=info['identity'];self.info=info;self.assignment_verified=True;self.resume_result=info['resume_result'];self._closed=False
    def poll(self):
        code=w.DWORD();_check(K.GetExitCodeProcess(self.process_handle,ctypes.byref(code)))
        return None if code.value==259 else int(code.value)
    def status(self):
        if self.poll() is None:return 'RUNNING'
        from .process_lifecycle import classify
        c=classify(self.identity)['status']
        return 'TERMINATED_OBJECT_QUERYABLE' if c=='ORIGINAL_PROCESS_OBJECT_STILL_ACCESSIBLE' else c
    def wait(self, timeout=None):
        ms=0xffffffff if timeout is None else min(int(timeout*1000),0xfffffffe)
        result=K.WaitForSingleObject(self.process_handle,ms)
        if result==258:raise TimeoutError('process wait timed out')
        if result!=0:raise ctypes.WinError(ctypes.get_last_error())
        return self.poll()
    def terminate(self):
        if self.poll() is None:_check(K.TerminateProcess(self.process_handle,1))
    def finish(self, expected_exit=0, lifecycle_observer=None):
        code=self.wait(); history=[];deadline=time.monotonic()+5
        while True:
            account=job_active(self.job_handle);history.append({'time':time.time(),**account})
            if account['active_processes']==0 or time.monotonic()>=deadline:break
            time.sleep(.1)
        from .process_lifecycle import classify
        same=classify(self.identity)
        # While our handle is open, queryability is expected after termination.
        status=('TERMINATED_OBJECT_QUERYABLE' if same['status']=='ORIGINAL_PROCESS_OBJECT_STILL_ACCESSIBLE' else same['status'])
        result={**self.info,'returncode':code,'job_accounting':account,'accounting_history':history,'classification':status,
                'pass':code==expected_exit and account['active_processes']==0 and self.assignment_verified and not(self.info['job_limit_flags'] & BREAKAWAY)}
        if lifecycle_observer is not None:
            try:lifecycle_observer('JOB_COMPLETE', self.pid, result)
            except Exception:pass
        self.close()
        started=time.monotonic(); observations=[]
        while True:
            try:later=classify(self.identity)
            except OSError as exc:
                observations.append({'elapsed_seconds':time.monotonic()-started,'classification':'QUERY_ERROR','error':str(exc)})
                later={'pass':False};elapsed=time.monotonic()-started;break
            elapsed=time.monotonic()-started
            observations.append({'elapsed_seconds':elapsed,'classification':later['status']})
            if later['pass'] or elapsed>=0.5:break
            time.sleep(.05)
        result['post_close_identity_observations']=observations
        result['disappearance_seconds']=elapsed if later['pass'] else None
        result['disappearance_right_censored']=not later['pass']
        return result
    def close(self):
        if not self._closed:
            _close(self.thread_handle);_close(self.process_handle);_close(self.job_handle);self._closed=True

def launch(argv, env=None, cwd=None, stdout_path=None, lifecycle_observer=None):
    """Create suspended, bind Job and validate it, then and only then resume."""
    job=process=thread=stdin=out=None
    try:
        name='Local\\GENSPACE_SUSPENDED_'+uuid.uuid4().hex
        job=K.CreateJobObjectW(None,name);_check(job)
        limit=EXTENDED();limit.BasicLimitInformation.LimitFlags=KILL
        _check(K.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)))
        actual=EXTENDED();_check(K.QueryInformationJobObject(job,9,ctypes.byref(actual),ctypes.sizeof(actual),None))
        flags=actual.BasicLimitInformation.LimitFlags
        if not(flags & KILL) or flags & BREAKAWAY:raise RuntimeError('unsafe Job limits')
        stdin=_file('NUL',0x80000000,3);out=_file(stdout_path if stdout_path else 'NUL',0x40000000,2 if stdout_path else 3)
        si=STARTUP();si.cb=ctypes.sizeof(si);si.dwFlags=0x100;si.hStdInput=stdin;si.hStdOutput=out;si.hStdError=out
        pi=PROCESS();cmd=ctypes.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in argv]))
        vals=os.environ.copy() if env is None else env
        block=ctypes.create_unicode_buffer('\0'.join(f'{k}={v}' for k,v in sorted(vals.items(),key=lambda item:item[0].upper()))+'\0\0')
        _check(K.CreateProcessW(None,cmd,None,None,True,0x4|0x400|0x08000000,ctypes.cast(block,ctypes.c_void_p),str(cwd) if cwd else None,ctypes.byref(si),ctypes.byref(pi)))
        process,thread=pi.hProcess,pi.hThread
        ident=identity(pi.dwProcessId)
        if not ident:raise RuntimeError('cannot identify suspended child')
        _check(K.AssignProcessToJobObject(job,process))
        inside=w.BOOL();_check(K.IsProcessInJob(process,job,ctypes.byref(inside)))
        if not inside.value:raise RuntimeError('assignment not verified')
        if lifecycle_observer is not None:
            try:lifecycle_observer('JOB_ASSIGNMENT', int(pi.dwProcessId),
                                   {'assignment_verified':True,'job_identity':name,'job_limit_flags':int(flags),'create_suspended':True})
            except Exception:pass
        resumed=K.ResumeThread(thread)
        if resumed==0xffffffff:raise ctypes.WinError(ctypes.get_last_error())
        if resumed!=1:raise RuntimeError('unexpected suspend count')
        info={'pid':int(pi.dwProcessId),'identity':ident,'process_handle':int(process),'thread_handle':int(thread),'job_identity':name,'job_limit_flags':int(flags),'assignment_verified':True,'resume_result':int(resumed),'create_suspended':True,'assignment_before_resume':True}
        obj=SuspendedJob(process,thread,job,info);process=thread=job=None
        return obj
    except BaseException:
        if process:
            K.TerminateProcess(process,1);K.WaitForSingleObject(process,5000)
        raise
    finally:
        for h in (stdin,out,thread,process,job):
            if h:K.CloseHandle(h)

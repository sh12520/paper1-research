"""Observed, per-clock event records. No cross-clock subtraction or fake ticks."""
import json
import threading
import time
from contracts import MAX, jcs


class ClockError(ValueError): pass


class Clock:
    def __init__(self,boot,clock_id,source=time.monotonic_ns):
        if not boot or not clock_id:raise ValueError("explicit boot/origin required")
        self.boot=boot;self.clock_id=clock_id;self.source=source;self.last=None;self.lock=threading.Lock()
    def now(self):
        with self.lock:
            n=self.source()
            if type(n) is not int or not 0<=n<=MAX or self.last is not None and n<self.last:raise ClockError("clock regression/range")
            self.last=n;return n


class Trace:
    def __init__(self,role,clock,path=None):
        self.role=role;self.clock=clock;self.events=[];self.lock=threading.RLock();self.path=path
        if path:
            with open(path,"xb"):pass
    def emit(self,event,request=None,ns=None,**details):
        with self.lock:
            error=None
            try:record_ns=self.clock.now()
            except ClockError as e:record_ns=None;error=str(e)
            row={"ordinal":len(self.events),"event":event,"role":self.role,"boot":self.clock.boot,"clockId":self.clock.clock_id,"unit":"NANOSECONDS","ns":record_ns,"observedNs":ns,"clockError":error}
            if request:row.update({k:request[k] for k in ("negotiationId","intentId","phase","attempt")})
            row.update(details);self.events.append(row)
            if self.path:
                with open(self.path,"ab") as f:f.write(jcs(row)+b"\n")
            return row

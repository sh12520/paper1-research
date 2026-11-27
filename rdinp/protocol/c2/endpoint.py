"""Actual loopback HTTP responder; test hooks never selected by wire input."""
import http.client
import json
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contracts import parse, jcs, sha
from crypto import b64, response


class Responder:
    def __init__(self,authority,identity,trust,trace,response_policy=None):
        self.authority=authority;self.identity=identity;self.trust=trust;self.trace=trace;self.response_policy=response_policy
        if identity.principal!=authority.authority_id or identity.role!="responder":raise ValueError("server identity")
        if trust.pins.get(identity.kid,(None,None))[0]!=identity.pin():raise ValueError("server key not pinned")
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version="HTTP/1.1"
            def log_message(self,*args):pass
            def send_bytes(self,status,raw):
                self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.send_header("Connection","close");self.end_headers();self.wfile.write(raw);self.wfile.flush();self.close_connection=True
            def do_POST(self):
                m=None;raw=b"";arrival=uuid.uuid4().hex
                try:
                    if self.path not in ("/rdinp/intent","/rdinp/commit"):self.send_bytes(404,b'{"authoritative":false}');return
                    lengths=self.headers.get_all("Content-Length") or []
                    if len(lengths)!=1 or not lengths[0].isascii() or not lengths[0].isdigit() or self.headers.get("Transfer-Encoding") or self.headers.get_content_type()!="application/json":raise ValueError("framing")
                    n=int(lengths[0])
                    if not 0<n<=65536:raise ValueError("body cap")
                    self.connection.settimeout(2)
                    raw=self.rfile.read(n)
                    if len(raw)!=n:raise ValueError("truncated body")
                    owner.trace.emit("INGRESS",rawSha256=sha(raw),rawBase64=b64(raw),arrivalId=arrival)
                    try:m=owner.trust.verify(raw,owner.authority.contract,owner.authority.initiator_id,"initiator")
                    except Exception:
                        owner.trace.emit("AUTH_REJECT",rawSha256=sha(raw));self.send_bytes(403,b'{"authoritative":false}');return
                    if m["recipient"]!=owner.identity.principal or m["kind"]!=("INTENT" if self.path=="/rdinp/intent" else "COMMIT"):raise ValueError("route/recipient")
                    owner.trace.emit("AUTHORIZED",m,rawSha256=sha(raw),jcsSha256=sha(jcs(m)),trustDigest=owner.trust.digest,arrivalId=arrival)
                    try:kind,body=owner.authority.process(m,raw,arrival)
                    except Exception as e:
                        owner.trace.emit("PROCESS_UNKNOWN",m,rawSha256=sha(raw),detail=type(e).__name__)
                        kind,body="PROBLEM",{"code":"INTERNAL_UNKNOWN","authoritative":False}
                    answer=response(owner.identity,owner.authority.contract,m,raw,kind,body)
                    status=200 if kind!="PROBLEM" else (410 if body["code"]=="EXPIRED" else 503 if body["code"]=="INTERNAL_UNKNOWN" else 409)
                    action=owner.response_policy(m,kind,body) if owner.response_policy else {}
                    if action.get("delay",0):time.sleep(action["delay"])
                    if action.get("drop",False):
                        owner.trace.emit("TEST_RESPONSE_SUPPRESSED",m,rawSha256=sha(answer),rawBase64=b64(answer),arrivalId=arrival);self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);return
                    self.send_bytes(status,answer)
                    owner.trace.emit("RESPONSE_EGRESS",m,rawSha256=sha(answer),requestRawSha256=sha(raw),rawBase64=b64(answer),httpStatus=status,arrivalId=arrival)
                except (BrokenPipeError,ConnectionError,OSError) as e:
                    owner.trace.emit("EGRESS_ERROR",m,rawSha256=sha(raw),detail=type(e).__name__)
                except Exception as e:
                    owner.trace.emit("INPUT_REJECT",m,rawSha256=sha(raw),detail=type(e).__name__)
                    try:self.send_bytes(400,b'{"authoritative":false}')
                    except OSError:pass
        class Server(ThreadingHTTPServer):daemon_threads=True
        self.http=Server(("127.0.0.1",0),Handler);self.host,self.port=self.http.server_address
        self.thread=threading.Thread(target=lambda:self.http.serve_forever(poll_interval=0.02),daemon=True)
    def start(self):self.authority.start_cleanup();self.thread.start();return self
    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join(2);self.authority.close()
    def __enter__(self):return self.start()
    def __exit__(self,*_):self.close()


def post(host,port,path,raw,timeout=2):
    if host!="127.0.0.1":raise ValueError("A local runner forbids nonloopback destinations")
    conn=http.client.HTTPConnection(host,port,timeout=timeout)
    try:
        conn.request("POST",path,body=raw,headers={"Content-Type":"application/json","Connection":"close"})
        reply=conn.getresponse();data=reply.read(65537)
        if len(data)>65536:raise ValueError("response cap")
        return reply.status,data
    finally:conn.close()

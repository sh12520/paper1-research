"""Local process-crash fixture. No remote host, original program, or production key."""
import json
import os
from pathlib import Path
import sys
import threading
from cryptography.hazmat.primitives import serialization
from authority import Authority
from contracts import Contract, jcs
from crypto import Identity, Trust
from endpoint import Responder
from events import Clock, Trace


if __name__=="__main__":
    data=json.loads(sys.stdin.readline());root=Path(sys.argv[1])
    contract=Contract(jcs(data["plan"]),data["policy"],data["timing"])
    key=serialization.load_pem_private_key(data["privateKeyPem"].encode("ascii"),password=None)
    identity=Identity("authority","responder",key);trust=Trust(data["pins"])
    clock=Clock(data["boot"],"server-monotonic");trace=Trace("responder",clock,root/"crash-server.events.jsonl")
    authority=Authority(root/"crash-authority.sqlite",contract,clock,trace)
    def policy(m,kind,body):
        if m["phase"]=="COMMIT_INITIAL" and kind=="RECEIPT" and body["status"]=="COMMITTED":os._exit(17)
        return {}
    server=Responder(authority,identity,trust,trace,policy).start()
    print(json.dumps({"host":server.host,"port":server.port}),flush=True)
    threading.Event().wait()

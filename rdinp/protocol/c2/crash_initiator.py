"""Process-crash fixtures at durable client checkpoints, not a new protocol path."""
import json
import os
from pathlib import Path
import sys
from cryptography.hazmat.primitives import serialization
from contracts import Contract, jcs
from crypto import Identity, Trust
from events import Clock, Trace
from initiator import Initiator


if __name__=="__main__":
    data=json.loads(sys.stdin.readline());root=Path(sys.argv[1])
    contract=Contract(jcs(data["plan"]),data["policy"],data["timing"])
    identity=Identity("initiator","initiator",serialization.load_pem_private_key(data["privateKeyPem"].encode("ascii"),None))
    clock=Clock("LOCAL-NONPRODUCTION-BOOT","client-monotonic");trace=Trace("initiator",clock,root/"crash-client.events.jsonl")
    class CrashClient(Initiator):
        def persist(self):
            super().persist()
            if data["mode"]=="BEFORE_COMMIT_SEND" and self.state["commitPossible"] and not self.state["receipt"]:os._exit(23)
            if data["mode"]=="AFTER_FIRST_RECEIPT" and self.state["receipt"] and not self.state["terminal"]:os._exit(24)
    def provisional_exit(request,candidate):
        if data["mode"]=="PROVISIONAL_COMMIT" and request["phase"]=="COMMIT_INITIAL":os._exit(25)
    client=CrashClient(root/"crash-client.sqlite",contract,identity,Trust(data["pins"]),clock,trace,after_latch_store=provisional_exit)
    client.run("127.0.0.1",data["port"],"client-crash","intent-client-crash",10)

"""Standalone actual local dual-endpoint demo. New output directory only, no B."""
import json
from pathlib import Path
import sys
from authority import Authority
from contracts import ROOT, REVISION, example_contract, jcs, sha
from crypto import Identity, Trust
from endpoint import Responder
from events import Clock, Trace
from initiator import Initiator


def demo(output):
    output=Path(output).resolve()
    allowed=ROOT.parent if ROOT.name=="source" and (ROOT.parent/"identity.json").is_file() else ROOT
    if output==allowed or not output.is_relative_to(allowed):raise ValueError("new candidate/run descendant directory required")
    output.mkdir(parents=True,exist_ok=False)
    entries=[{"path":name,"bytes":(ROOT/name).stat().st_size,"sha256":sha((ROOT/name).read_bytes())} for name in sorted(json.loads((ROOT/"SOURCE-FILES.json").read_text())["files"])]
    (output/"demo-identity.json").write_bytes(jcs({"revision":REVISION,"sourceSnapshotId":"sha256:"+sha(jcs(entries)),"gitHead":None,"scope":"LOCAL_NONPRODUCTION_LOOPBACK_NOT_B","source":entries}))
    c=example_contract();i=Identity("initiator","initiator");r=Identity("authority","responder");pins=[i.pin(),r.pin()];trust=Trust(pins)
    (output/"inputs.json").write_bytes(jcs({"plan":c.plan,"policy":c.policy,"timing":c.timing,"trust":pins,"scope":"NONPRODUCTION_LOCAL_MECHANISMS_ONLY"}))
    sc=Clock("EXPLICIT-UNQUALIFIED-LOCAL-BOOT","server-monotonic");st=Trace("responder",sc,output/"server.events.jsonl")
    cc=Clock("EXPLICIT-UNQUALIFIED-LOCAL-BOOT","client-monotonic");ct=Trace("initiator",cc,output/"client.events.jsonl")
    authority=Authority(output/"authority.sqlite",c,sc,st)
    client=Initiator(output/"client.sqlite",c,i,trust,cc,ct)
    try:
        with Responder(authority,r,trust,st) as server:result=client.run(server.host,server.port,"local-demo","intent-local-demo",10);client.drain()
        (output/"result.json").write_bytes(jcs(result));(output/"observations.json").write_bytes(jcs(authority.snapshot()))
        return result
    finally:client.close()


if __name__=="__main__":print(json.dumps(demo(sys.argv[1]),indent=2))

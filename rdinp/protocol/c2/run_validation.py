"""Identity first, then bounded local conformance. Preserve all failures and bytes."""
import base64
import datetime
import json
import importlib.metadata
import os
from pathlib import Path
import platform
import subprocess
import sys
import sqlite3
import ssl
import uuid
from contracts import ROOT, REVISION, jcs, sha


def main():
    run=ROOT/"runs"/(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]);run.mkdir(parents=True,exist_ok=False)
    declared=json.loads((ROOT/"SOURCE-FILES.json").read_text(encoding="utf-8"))["files"]
    files=sorted(ROOT/name for name in declared)
    entries=[]
    for p in files:
        raw=p.read_bytes();dest=run/"source"/p.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
        entries.append({"path":p.name,"bytes":len(raw),"sha256":sha(raw)})
    source="sha256:"+sha(jcs(entries))
    dependencies={name:importlib.metadata.version(name) for name in ("cryptography","jsonschema","referencing","jsonschema-specifications","attrs","rpds-py","cffi","pycparser")}
    modules=["test_minimal_fixes"] if "--targeted" in sys.argv[1:] else ["test_candidate","test_minimal_fixes"]
    identity={"revision":REVISION,"sourceSnapshotId":source,"gitHead":None,"runId":run.name,"scope":"LOCAL_LOOPBACK_CONFORMANCE_NOT_B","suite":"TARGETED" if len(modules)==1 else "FULL_39_PLUS_MINIMAL_FIXES","argv":[sys.executable,"-m","unittest","-v",*modules],"python":sys.version,"pythonExecutableSha256":sha(Path(sys.executable).read_bytes()),"sqlite":sqlite3.sqlite_version,"openssl":ssl.OPENSSL_VERSION,"dependencies":dependencies,"platform":platform.platform(),"qualification":False,"source":entries}
    (run/"identity.json").write_bytes(jcs(identity))
    env=dict(os.environ);env["RDINP_EVIDENCE_DIR"]=str(run/"cases");env["PYTHONDONTWRITEBYTECODE"]="1"
    # Execute immutable captured source, not live working files.
    result=subprocess.run(identity["argv"],cwd=run/"source",env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    output={"exitCode":result.returncode,"stdoutBase64":base64.b64encode(result.stdout).decode(),"stderrBase64":base64.b64encode(result.stderr).decode(),"stdoutSha256":sha(result.stdout),"stderrSha256":sha(result.stderr)}
    (run/"execution.json").write_bytes(jcs(output))
    artifacts=[{"path":p.relative_to(run).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p.read_bytes())} for p in sorted(run.rglob("*")) if p.is_file()]
    manifest={"sourceSnapshotId":source,"runId":run.name,"exitCode":result.returncode,"artifacts":artifacts,"qualified":False}
    raw=jcs(manifest);(run/"run-manifest.json").write_bytes(raw)
    receipt={"runArtifactId":"sha256:"+sha(raw),"sourceSnapshotId":source,"run":str(run),"exitCode":result.returncode,"qualified":False}
    (run/"run-receipt.json").write_bytes(jcs(receipt));print(json.dumps(receipt,indent=2));print(result.stderr.decode("utf-8",errors="replace"))
    return result.returncode


if __name__=="__main__":sys.exit(main())

"""Detached, supervised proof supply for the prepared holdout parent."""

from dataclasses import asdict
from hashlib import file_digest, sha256
import gzip
import hmac
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from symbolic_format import ROOT, dump
from cover_verifier import MAX_PROOF_BYTES, read_proof
from holdout_transactions import IntegrityError, decode, sync_write
from method_proof_bridge import (QueryBinding, _ISSUER, _VerifiedPublicProof, authenticate_shared_proof,
                                 require)
from run_depth3_proofs import EMERGENCY, MAX_RSS, MIN_AVAILABLE, PROOF_WALL, load_public, sample
from src.windows_suspended_job import launch
from tools.smoke_01 import memory_status, process_memory
from unseen_verifier import FULL, SHORT, prefix_digest


SERVICE_FORMAT = "depth3-detached-proof-cache-v1"


def file_sha(path):
    with path.open("rb") as stream:
        return file_digest(stream,"sha256").hexdigest()


def sign(value,key):
    return {"value":value,"hmac_sha256":hmac.digest(key,dump(value),"sha256").hex()}


def check_signed(envelope,key):
    value = envelope["value"]
    require(hmac.compare_digest(envelope["hmac_sha256"],sign(value,key)["hmac_sha256"]),
            "Proof publication or checker report MAC mismatch")
    return value


def claims(proof):
    """Translate replayed observational claims before independent adjudication."""
    prefix = []
    cuts = {}
    for k, group in sorted(proof["checkpoints"].items(),key=lambda pair:int(pair[0])):
        prefix = [proof["nodes"][key][1] for key in group["prefix"]]
        boundary = prefix[-1] if prefix else {}
        cuts[k] = dict(status=SHORT if len(prefix)<int(k) else FULL,returned=len(prefix),
                       boundary_score=boundary.get("score"),boundary_key=boundary.get("key"),
                       full_domain_exhausted=group["exhausted"],
                       prefix_sha256=prefix_digest([(bytes.fromhex(r["key"]),r["score"],r["witness"])
                                                   for r in prefix]))
    return prefix,cuts


def bind_query(query, addendum_sha):
    return dict(instance_id=query.query_id, namespace=query.namespace,
                serialized_sha256=query.serialized_sha256,instance_hash=query.instance_hash,
                public_hash=query.public_hash,snapshot_sha256=query.snapshot_sha256,
                candidate_source_tree_sha256=query.candidate_source_tree_sha256,
                plan_sha256=query.plan_sha256,effective_depth=3,proof_addendum_sha256=addendum_sha)


def stage(folder, request_sha, mode, proof_sha):
    secret = bytes.fromhex(os.environ.pop("METHOD_PROOF_STAGE_KEY"))
    expected = folder/"request.json"
    raw = expected.read_bytes()
    require(sha256(raw).hexdigest() == request_sha,"Proof request bytes mismatch")
    request = decode(raw)
    query = QueryBinding(**request["query"])
    public = load_public(request["public"])
    binding = bind_query(query,request["addendum_sha256"])
    query.check_public(public)
    path = folder/"proof.json.gz"
    start = perf_counter()
    if mode == "emit":
        from native_symbolic_producer import produce_symbolic

        proof, work = produce_symbolic(public,binding,sample)
        if not proof["checkpoints"]:
            raise RuntimeError("BLOCKED_MISSING_INDEPENDENT_FRONTIER_PROOF: " + str(work["limit_reason"]))
        data = dump(proof)
        if len(data) > MAX_PROOF_BYTES:
            raise OverflowError("PROOF_TOO_LARGE")
        compressed = gzip.compress(data,mtime=0)
        if len(compressed) > MAX_PROOF_BYTES:
            raise OverflowError("PROOF_TOO_LARGE")
        sync_write(path,compressed)
        receipt = {"sha256":sha256(compressed).hexdigest(),"raw_bytes":len(data),
                   "compressed_bytes":len(compressed),"limit_reason":work["limit_reason"],
                   "nodes":work["proof_nodes"]}
    else:
        require(file_sha(path) == proof_sha,"Wrong proof supplied to independent worker")
        proof = read_proof(path)
        prefix,cuts = claims(proof)
        checked = authenticate_shared_proof(query,public,path,proof_sha,binding,prefix,cuts,sample)
        receipt = {"sha256":checked.compressed_sha256,
                   "prefix":[[key.hex(),score,witness] for key,score,witness in checked.prefix],
                   "cut_statuses":[list(pair) for pair in checked.cut_statuses],"exhausted":checked.exhausted}
    receipt.update(worker_seconds=perf_counter()-start,peak_rss=process_memory(os.getpid())[1],
                   request_sha256=request_sha)
    sync_write(folder/(mode+".json"),dump(sign(receipt,secret)))


class ProofUnavailable(RuntimeError):
    """A detached proof could not be produced or verified inside its budget."""


def supervised(folder, mode, request_sha, proof_sha="-"):
    for _ in range(3):
        while memory_status()[1]<MIN_AVAILABLE:
            sleep(5)
        sleep(.15)
    key = os.urandom(32)
    env = dict(os.environ,METHOD_PROOF_STAGE_KEY=key.hex())
    env.pop("METHOD_HOLDOUT_TRANSACTION_KEY_FILE",None)
    job = launch([sys.executable,"-B",__file__,mode,folder,request_sha,proof_sha],env=env,cwd=ROOT,
                 stdout_path=folder/(mode+".log"))
    start = perf_counter()
    peak = 0
    minimum_available = memory_status()[1]
    limit = None
    try:
        while job.poll() is None:
            try:
                peak = max(peak,process_memory(job.pid)[1])
            except OSError:
                if job.poll() is None:
                    raise
            minimum_available = min(minimum_available,memory_status()[1])
            if minimum_available<=EMERGENCY or peak>MAX_RSS:
                limit = "PROOF_MEMORY_LIMIT"
            elif perf_counter()-start>=PROOF_WALL:
                limit = "PROOF_GENERATION_TOO_SLOW" if mode=="emit" else "PROOF_VERIFICATION_TOO_SLOW"
            if limit:
                job.terminate()
                job.wait(5)
                break
            sleep(.045)
        status = job.poll()
        report = job.finish(expected_exit=status)
    finally:
        job.close()
    require(report["pass"],"Detached proof Job failed containment")
    if limit or status != 0:
        message = (folder/(mode+".log")).read_text(encoding="utf-8",errors="replace")[-1000:]
        if "RejectedEvidence" in message or "ProofRejected" in message:
            raise IntegrityError("PROOF_UNSOUND: " + message)
        raise ProofUnavailable(limit or message or "Detached proof abnormal exit")
    receipt = check_signed(decode((folder/(mode+".json")).read_bytes()),key)
    require(receipt["request_sha256"]==request_sha,"Checker response not bound to the request")
    receipt.update(parent_seconds=perf_counter()-start,minimum_available=minimum_available,
                   peak_rss=max(peak,receipt["peak_rss"]),
                   job_final_active=report["job_accounting"]["active_processes"])
    return receipt


class ProofCache:
    def __init__(self,root,signing_key,addendum_sha,assert_live):
        self.root = Path(root).resolve()
        self.key = signing_key
        self.live = assert_live
        self.addendum_sha = addendum_sha
        self.latest = None
        require(isinstance(signing_key,bytes) and len(signing_key)>=32,"Invalid proof custody key")
        self.root.mkdir(parents=True,exist_ok=True)

    def _request(self,query,public):
        require(self.live()==query.snapshot_sha256,"Snapshot changed before proof access")
        query.check_public(public)
        raw = dump(dict(format=SERVICE_FORMAT,query=asdict(query),public=asdict(public),
                        addendum_sha256=self.addendum_sha))
        sha = sha256(raw).hexdigest()
        return raw,sha,self.root/sha

    def _archive(self,folder,request_sha):
        expected = {"COMPLETE.json","request.json","proof.json.gz"}
        unsafe = lambda p:p.is_symlink() or getattr(p,"is_junction",lambda:False)()
        require(not unsafe(folder) and {p.name for p in folder.iterdir()}==expected and
                all((folder/name).is_file() and not unsafe(folder/name) for name in expected),
                "Unexpected proof archive contents")
        receipt = check_signed(decode((folder/"COMPLETE.json").read_bytes()),self.key)
        require(receipt["request_sha256"]==file_sha(folder/"request.json")==request_sha and
                receipt["proof_sha256"]==file_sha(folder/"proof.json.gz"),
                "Detached proof archive was changed")
        return receipt

    def _checker_receipt(self,query,check):
        return _VerifiedPublicProof(_ISSUER,query,check["sha256"],
               tuple((bytes.fromhex(key),score,witness) for key,score,witness in check["prefix"]),
               tuple(map(tuple,check["cut_statuses"])),check["exhausted"])

    def load_or_prove(self,query,public):
        raw,request_sha,folder = self._request(query,public)
        if folder.exists():
            published = self._archive(folder,request_sha)
            proof_sha = published["proof_sha256"]
            if self.latest is not None and self.latest.query==query and self.latest.compressed_sha256==proof_sha:
                return self.latest
            with TemporaryDirectory(prefix=".proof-recheck-",dir=self.root) as tmp:
                staging = Path(tmp)
                sync_write(staging/"request.json",raw)
                sync_write(staging/"proof.json.gz",(folder/"proof.json.gz").read_bytes())
                check = supervised(staging,"check",request_sha,proof_sha)
        else:
            with TemporaryDirectory(prefix=".proof-pending-",dir=self.root) as tmp:
                staging = Path(tmp)
                sync_write(staging/"request.json",raw)
                emitted = supervised(staging,"emit",request_sha)
                proof_sha = emitted["sha256"]
                require(file_sha(staging/"proof.json.gz")==proof_sha,"Emitter proof byte digest differs")
                check = supervised(staging,"check",request_sha,proof_sha)
                publication = dict(format=SERVICE_FORMAT,request_sha256=request_sha,proof_sha256=proof_sha,
                                   emitted=emitted,checker={k:v for k,v in check.items() if k!="prefix"})
                bundle = staging/"publish"
                bundle.mkdir()
                sync_write(bundle/"request.json",raw)
                (staging/"proof.json.gz").rename(bundle/"proof.json.gz")
                sync_write(bundle/"COMPLETE.json",dump(sign(publication,self.key)))
                require(self.live()==query.snapshot_sha256,"Snapshot changed before proof commit")
                bundle.rename(folder)
                self._archive(folder,request_sha)
        require(self.live()==query.snapshot_sha256 and check["sha256"]==proof_sha,
                "Snapshot or proof changed before independent receipt")
        self.latest = self._checker_receipt(query,check)
        return self.latest

    def verify_cached(self,query,public,compressed_sha256):
        _,request_sha,folder = self._request(query,public)
        require(folder.is_dir(),"Committed attempt references missing detached proof")
        published = self._archive(folder,request_sha)
        require(published["proof_sha256"]==compressed_sha256,"Committed attempt references different proof")
        return self.load_or_prove(query,public)


if __name__ == "__main__":
    mode,directory,request_sha,proof_sha = sys.argv[1:]
    if mode not in ("emit","check"):
        raise SystemExit("Unknown proof custody stage")
    stage(Path(directory),request_sha,mode,proof_sha)

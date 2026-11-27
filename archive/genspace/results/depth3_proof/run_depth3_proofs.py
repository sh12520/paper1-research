"""Regenerate and independently adjudicate the 24 sealed development proofs."""

import argparse
from dataclasses import asdict
import gzip
import json
import os
from pathlib import Path
import sys
from time import perf_counter, sleep

from symbolic_format import ARCHIVE, HERE, K_VALUES, ROOT, dump
from audit_common import digest, distribution, read_json, sealed_payloads, write_csv, write_json
from certificate_report import depth3_slots, public_input
from src.instances import PublicInstance, digest as public_digest
from src.models import Profile
from src.windows_suspended_job import launch
from tools.smoke_01 import memory_status, process_memory


MIB = 1 << 20
MAX_RSS = 2048 * MIB
MIN_AVAILABLE = 2048 * MIB
EMERGENCY = 768 * MIB
MAX_BYTES = 96 * MIB
PROOF_WALL = 180
SOURCES = ("symbolic_format.py", "native_symbolic_producer.py", "symbolic_verifier.py",
           "cover_verifier.py", "run_depth3_proofs.py")
SEAL = ARCHIVE / "depth3/development/search_seal.json"


def file_hash(path):
    return digest(path.read_bytes())


def pins():
    snap = ROOT / "METHOD_EXECUTION_SNAPSHOT_DRAFT.json"
    authorization = ROOT / "METHOD_AUTHORIZATION_STATE.json"
    auth = read_json(authorization)
    assert auth["namespace_authorizations"] == {"METHOD_HOLDOUT": False, "CONFIRM": False}
    assert file_hash(snap) == auth["required_snapshot_sha256"]
    assert not (ROOT / "FROZEN_CONFIG.yaml").exists()
    final = ROOT / "METHOD_FREEZE_MANIFEST_FINAL_DRAFT.json"
    snapshot, final_manifest = read_json(snap)["payload"], read_json(final)
    assert snapshot["candidate_source_tree_sha256"] == final_manifest["candidate_method_source_tree_sha256"]
    old_auth = read_json(ROOT / "PILOT_AUTHORIZATION_STATE.json")
    assert old_auth["namespace_authorizations"]["CONFIRM"]["allowed"] is False
    for entry, sha in snapshot["infrastructure_sha256_by_file"].items():
        if file_hash(ROOT / entry) != sha:
            raise ValueError(f"Prepared holdout infrastructure differs at {entry}")
    seal = read_json(SEAL)
    for entry, sha in seal["manifest"]["sources"].items():
        if file_hash(ROOT / entry) != sha:
            raise ValueError(f"Archived research source differs at {entry}")
    return {
        "snapshot_sha256": file_hash(snap),
        "candidate_source_tree_sha256": snapshot["candidate_source_tree_sha256"],
        "prior_readiness_sha256": file_hash(final),
        "auth_sha256": file_hash(authorization),
        "development_seal_sha256": file_hash(SEAL),
        "proof_sources_sha256": {name:file_hash(HERE/name) for name in SOURCES},
    }


def load_public(raw):
    for name in ("m0_profiles","mr_profiles","b2_profiles"):
        raw[name] = tuple(Profile(**v) for v in raw[name])
    for name in ("states","capabilities","conditions","durations","offsets","offload_levels"):
        raw[name] = tuple(raw[name])
    for name in ("capacity","intervals"):
        raw[name] = tuple(map(tuple,raw[name]))
    return PublicInstance(**raw)


def sample():
    rss, peak = process_memory(os.getpid())
    if peak > MAX_RSS or memory_status()[1] <= EMERGENCY:
        raise MemoryError("Proof worker memory limit")
    return rss


def paths(iid):
    return (HERE/"work"/iid, HERE/"proofs"/(iid+".json.gz"))


def worker(mode, iid):
    folder, proof_path = paths(iid)
    if mode == "protocol":
        from run_depth3 import run_case
        from src.instances import deserialize_instance
        path = ROOT/"results/pilot/instances"/(iid+".json")
        fixture = read_json(folder/"public.json")["binding"]
        raw = path.read_bytes()
        if digest(raw) != fixture["serialized_sha256"]:
            raise ValueError("Serialized protocol input differs")
        outcome = run_case(deserialize_instance(raw.decode("utf-8")),depth3_slots()[iid],"development")
        payload = {key:outcome.get(key) for key in (
            "topk","protocol_status","agreement_status","protocol","history","verification_calls","proposal_rounds")}
        write_json(folder/"protocol.json", payload)
        return
    fixture = read_json(folder/"public.json")
    public = load_public(fixture["public"])
    binding = fixture["binding"]
    if public_digest(asdict(public)) != binding["public_hash"] or iid != binding["instance_id"]:
        raise ValueError("Public fixture fingerprint differs")
    start = perf_counter()
    if mode == "emit":
        from native_symbolic_producer import produce_symbolic
        proof, metrics = produce_symbolic(public,binding,sample)
        encoding_start = perf_counter()
        raw = dump(proof)
        if len(raw) > MAX_BYTES:
            raise OverflowError("PROOF_TOO_LARGE")
        compressed = gzip.compress(raw,mtime=0)
        path = proof_path.with_suffix(".pending")
        path.write_bytes(compressed)
        path.replace(proof_path)
        metrics.update(serialization_s=perf_counter()-encoding_start,
                       raw_bytes=len(raw),compressed_bytes=len(compressed),
                       proof_sha256=digest(compressed))
    else:
        from cover_verifier import read_proof
        from symbolic_verifier import verify_symbolic
        target = read_json(folder/"target.json")
        proof = read_proof(proof_path)
        metrics = verify_symbolic(public,proof,binding,target["topk"],target["k_certificates"],sample)
    metrics.update(stage_s=perf_counter()-start,self_peak_rss=process_memory(os.getpid())[1])
    write_json(folder/(mode+".json"),metrics)


def execute(mode,iid):
    folder,_ = paths(iid)
    for _ in range(3):
        while memory_status()[1] < MIN_AVAILABLE:
            print(f"{iid} {mode} PAUSED_MEMORY",flush=True)
            sleep(5)
        sleep(.15)
    started = perf_counter()
    job = launch([sys.executable,"-B",__file__,"--worker",mode,iid],
                 cwd=ROOT,stdout_path=folder/(mode+".log"))
    minimum_available = memory_status()[1]
    peak = 0
    limit = None
    try:
        while job.poll() is None:
            try:
                _, seen = process_memory(job.pid)
                peak = max(peak,seen)
            except OSError:
                if job.poll() is None:
                    raise
            minimum_available = min(minimum_available,memory_status()[1])
            if minimum_available <= EMERGENCY:
                limit = "EMERGENCY_MEMORY"
            elif peak > MAX_RSS:
                limit = "PROCESS_RSS_LIMIT"
            elif perf_counter()-started >= PROOF_WALL:
                limit = "STAGE_WALL_LIMIT"
            if limit:
                job.terminate()
                job.wait(5)
                break
            sleep(.045)
        try:
            peak = max(peak,process_memory(job.pid)[1])
        except OSError:
            pass
        returned = job.poll()
        elapsed = perf_counter()-started
        report = job.finish(expected_exit=returned)
    finally:
        job.close()
    if not report["pass"]:
        raise RuntimeError("Suspended Job containment failed")
    receipt = dict(stage=mode,elapsed_parent_s=elapsed,peak_rss=peak,
                   minimum_available=minimum_available,limit=limit,returncode=returned,
                   job_final_active=report["job_accounting"]["active_processes"],
                   assignment_before_resume=report["assignment_before_resume"])
    write_json(folder/(mode+"_job.json"),receipt)
    return returned == 0 and not limit,receipt


def summarize(rows,bindings,free_bytes):
    measured = ("emission_s","replay_wall_s","observation_s","serialize_s","check_s","proof_nodes",
                "shared_nodes","raw_bytes","compressed_bytes","emit_peak_rss","check_peak_rss",
                "minimum_available","proof_steps")
    cohorts = {"all": rows, "rich": [r for r in rows if r["richness"]=="rich"],
               "short_domain": [r for r in rows if r["k500"]=="EXACT_DOMAIN_EXHAUSTED_SHORT"]}
    breakdown = {}
    for group, records in cohorts.items():
        breakdown[group] = {field:dict(distribution(values),total=sum(values))
            for field in measured
            if (values := [r[field] for r in records if r.get(field) is not None])}
    good = sum(r["status"]=="VERIFIED" for r in rows)
    projection = {}
    if good == 24:
        groups = breakdown["all"]
        projection = {field:groups[field]["total"]*20 for field in (
            "emission_s","check_s","raw_bytes","compressed_bytes")}
        projection.update(compressed_dual_copy_bytes=2*projection["compressed_bytes"],
                          checksum_and_full_recheck_s=projection["check_s"],
                          uncertainty="24 development fixtures, all high conflict and one index; arithmetic extrapolation only")
    fields = list(dict.fromkeys(k for row in rows for k in row))
    write_csv(HERE/"per_query.csv",fields,rows)
    write_json(HERE/"proof_cost_summary.json",dict(
        planned_queries=24, completed_queries=len(rows),verified_queries=good,
        exact_checkpoints=sum(str(r.get(f"k{k}","")).startswith("EXACT_") for r in rows for k in K_VALUES),
        sealed_protocol_replays=sum(r.get("protocol_exact") is True for r in rows),
        bindings=bindings,cohorts=breakdown,projected_480=projection,disk_free_bytes=free_bytes,
        offline_stage_limits=dict(wall_s=PROOF_WALL,rss_mib=2048,prelaunch_mib=2048,
                                  emergency_mib=768,serialized_mib=96,nodes=200000)))


def panel():
    import shutil

    bindings = pins()
    seal, cases, sealed_sha = sealed_payloads(SEAL)
    manifest = read_json(ARCHIVE/"pilot/instances_manifest.json")
    slots = depth3_slots()
    if set(slots) != set(cases) or sealed_sha != bindings["development_seal_sha256"]:
        raise ValueError("The sealed fixed query grid is required")
    (HERE/"proofs").mkdir(exist_ok=True)
    rows = []
    for iid,case in cases.items():
        public, archived_sha = public_input(iid,manifest)
        folder, proof_path = paths(iid)
        folder.mkdir(parents=True,exist_ok=True)
        binding = dict(bindings,instance_id=iid,public_hash=manifest[iid]["public_hash"],
                       serialized_sha256=archived_sha,effective_depth=3,
                       sealed_case_sha256=seal["cases"][iid]["sha256"])
        write_json(folder/"public.json",{"public":asdict(public),"binding":binding})
        write_json(folder/"target.json",{k:case[k] for k in ("topk","k_certificates")})
        row = dict(instance_id=iid,family=case["family"],
                   pressure=public.configuration["resource_pressure"],
                   richness=public.configuration["capability_richness"],
                   sealed_case_sha256=binding["sealed_case_sha256"],
                   status="BLOCKED_MISSING_INDEPENDENT_FRONTIER_PROOF",
                   k10=None,k100=None,k500=None)
        ok,emit_job = execute("emit",iid)
        row.update(emit_peak_rss=emit_job["peak_rss"],minimum_available=emit_job["minimum_available"])
        if ok:
            e = read_json(folder/"emit.json")
            if file_hash(proof_path)!=e["proof_sha256"]:
                raise ValueError("Archived compressed proof differs from emission receipt")
            row.update(emission_s=e["stage_s"],replay_wall_s=e["wall_s"],
                       observation_s=e["synchronous_observation_s"],serialize_s=e["serialization_s"],
                       proof_nodes=e["proof_nodes"],shared_references=e["shared_references"],
                       raw_bytes=e["raw_bytes"],compressed_bytes=e["compressed_bytes"],
                       emit_peak_rss=max(row["emit_peak_rss"],e["self_peak_rss"]),
                       limit_reason=e["limit_reason"],proof_sha256=e["proof_sha256"])
            ok,check_job = execute("check",iid)
            row["minimum_available"] = min(row["minimum_available"],check_job["minimum_available"])
            row["check_peak_rss"] = check_job["peak_rss"]
            if ok:
                c = read_json(folder/"check.json")
                row.update(status=c["status"],check_s=c["stage_s"],shared_nodes=c["shared_nodes"],
                           bounds_checked=c["lower_bounds_checked"],proof_steps=c["coverage_visits"],
                           check_peak_rss=max(row["check_peak_rss"],c["self_peak_rss"]))
                row.update({f"k{k}":c["checkpoints"].get(str(k)) for k in K_VALUES})
            else:
                row["failure_stage"] = "independent_check"
                row["failure_detail"] = check_job["limit"] or (folder/"check.log").read_text("utf-8",errors="replace")[-400:]
        else:
            row["failure_stage"] = "emission"
            row["failure_detail"] = emit_job["limit"] or (folder/"emit.log").read_text("utf-8",errors="replace")[-400:]
        rows.append(row)
        summarize(rows,bindings,shutil.disk_usage(ROOT).free)
        print(iid,row["status"],row.get("emission_s"),row.get("check_s"),row.get("failure_detail",""),flush=True)
    for row in rows:
        iid = row["instance_id"]
        folder,_ = paths(iid)
        ok,_ = execute("protocol",iid)
        if ok:
            archive = cases[iid]
            observed = read_json(folder/"protocol.json")
            row["protocol_exact"] = dump(observed) == dump({key:archive.get(key) for key in observed})
        else:
            row["protocol_exact"] = False
        summarize(rows,bindings,shutil.disk_usage(ROOT).free)
        print(iid,"protocol exact",row["protocol_exact"],flush=True)
    if pins() != bindings or sealed_payloads(SEAL)[2] != sealed_sha:
        raise ValueError("Authorization, frozen source or development archive changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",nargs=2,metavar=("MODE","ARCHIVED_ID"))
    args = parser.parse_args()
    if args.worker:
        mode,iid = args.worker
        if mode not in ("emit","check","protocol") or iid not in depth3_slots():
            parser.error("Only the 24 existing development IDs are admitted")
        worker(mode,iid)
    else:
        panel()

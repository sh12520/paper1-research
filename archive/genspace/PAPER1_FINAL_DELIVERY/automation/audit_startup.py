"""Read-only frozen-input and host audit for the manuscript workflow."""

from hashlib import sha256
import json
import shutil
import subprocess
import sys

from AUTO_PAPER_72H import ROOT, WORK, atomic, now, sha


def read(path):
    return json.loads((ROOT/path).read_bytes())


def main():
    path = "METHOD_FINAL_FREEZE_MANIFEST.json"
    candidate = read(path)
    frozen = candidate["payload"]
    canonical = json.dumps(frozen,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    if sha256(canonical.encode("utf-8")).hexdigest()!=candidate["payload_sha256"]:
        raise ValueError("Final candidate payload hash mismatch")
    keys = ("prior_review_sha256_by_file", "approval_documents_sha256_by_file",
            "reference_documents_sha256_by_file", "development_evidence_sha256_by_file",
            "proof_archive_development_sha256_by_file")
    for key in keys:
        if any(sha(ROOT/name)!=want for name,want in frozen[key].items()):
            raise ValueError("Frozen candidate record mismatch: " + key)
    app = ROOT/"results/depth3_proof/prepare_holdout_proof_entry.py"
    output = subprocess.check_output([sys.executable,"-B",str(app),"--validate-preparation"],cwd=ROOT,timeout=45)
    proof = json.loads(output)
    auth = read("METHOD_AUTHORIZATION_STATE.json")
    legacy = read("PILOT_AUTHORIZATION_STATE.json")["namespace_authorizations"]["CONFIRM"]["allowed"]
    launch_flags = auth["namespace_authorizations"]
    gate_files = ("METHOD_HOLDOUT_READINESS_ATTESTATION.json","results/method_holdout_release/release_manifest.json")
    flags = {name:(ROOT/name).exists() for name in gate_files}
    auth_closed = launch_flags=={"METHOD_HOLDOUT":False,"CONFIRM":False} and legacy is False
    backup = frozen["resources"]["independent_backup"]
    sys.path.insert(0,str(ROOT))
    from tools.smoke_01 import memory_status
    total,available = memory_status()
    files = tuple(frozen["approval_documents_sha256_by_file"]) + (path,"METHOD_HOLDOUT_FINAL_READINESS_REPORT.md",
        "PAPER_DEVELOPMENT_COMPARISON.md","PAPER_ABLATION_SPEC.md",
        "PAPER_CONTRIBUTION_BOUNDARIES.md","PAPER_OUTLINE_V1.md")
    report = dict(checked_at_asia_shanghai=now().isoformat(), freeze_manifest_sha256=sha(ROOT/path),
        candidate_status=candidate["status"],research_source_tree_sha256=frozen["research_binding"]["source_tree_sha256"],
        native_preparation_result=proof,requested_startup_files_sha256={p:sha(ROOT/p) for p in files},
        statistics=frozen["statistics"],identities=frozen["identity"],host_physical_total_bytes=total,
        host_physical_available_bytes=available,storage_free_bytes=shutil.disk_usage(ROOT).free,
        independent_backup_evidence=backup,actual_authorization=launch_flags,legacy_confirm_allowed=legacy,
        approval_receipts_present=flags,release_sha256_approved=auth["approved_release_sha256"],
        readiness_sha256_approved=auth["approved_readiness_sha256"],preflight_run_policy="DEVELOPMENT_EVIDENCE_ONLY"
        if auth_closed else "REQUIRES_SEPARATE_LIVE_APPROVAL_AUDIT",
        results_root_present=(ROOT/"results/method_confirmation").exists(),
        formal_frozen_config_present=(ROOT/"FROZEN_CONFIG.yaml").exists(),
        cli_version="0.169.0-alpha.11.1",
        cli_probe_pass=(WORK/"cli_probe_pass.json").is_file(),
        scheduler="Windows Schedule service present; bounded local Job watchdog")
    atomic(WORK/"startup_audit.json",json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps({k:report[k] for k in ("candidate_status","preflight_run_policy",
        "host_physical_available_bytes","storage_free_bytes","cli_probe_pass")},ensure_ascii=False))


if __name__=="__main__":
    main()

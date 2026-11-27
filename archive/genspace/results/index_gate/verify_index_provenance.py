"""Check preserved source inputs and record the reviewed public retrieval boundary."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HISTORICAL = ROOT / "results" / "flat_audit"
METHOD = ROOT / "results" / "method_dev_v1"
HISTORICAL_TREES = (
    "src", "schemas", "tests", "results/method_dev_v1", "results/pilot",
    "results/pilot_attribution", "results/pilot_attribution_work",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    historical = read(HISTORICAL / "baseline_hashes.json")
    audit_inputs = read(HERE / "audit_input_hashes.json")
    combined = {**historical, **audit_inputs}
    manifest_conflicts = sorted(
        name for name in historical.keys() & audit_inputs.keys()
        if historical[name] != audit_inputs[name]
    )
    missing = []
    changed = []
    for name, expected in combined.items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif file_sha(path) != expected:
            changed.append(name)
    actual = {
        path.relative_to(ROOT).as_posix()
        for root in HISTORICAL_TREES
        for path in (ROOT / root).rglob("*")
        if path.is_file()
    }
    added = sorted(actual.difference(combined))
    replay_manifest = HERE / "replay_manifest.json"
    replay_expected = read(replay_manifest)["inputs_sha256"]
    replay_paths = {
        **{name: HERE / name for name in ("run_index_gate.py", "index_tree.py", "index_query.py")},
        **{name: METHOD / name for name in ("runtime.py", "private_protocol.py", "public_search.py")},
        "manifest.json": HERE / "index" / "manifest.json",
        "PILOT01_PLAN_TEMPLATE.json": ROOT / "PILOT01_PLAN_TEMPLATE.json",
        "instances_manifest.json": ROOT / "results" / "pilot" / "instances_manifest.json",
        "per_instance.csv": HISTORICAL / "per_instance.csv",
        "PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json": ROOT / "PILOT_EXECUTABLE_SNAPSHOT_FINGERPRINT.json",
    }
    if set(replay_expected) != set(replay_paths):
        raise ValueError("Unexpected replay manifest path set")
    replay_changes = sorted(name for name, path in replay_paths.items()
                            if not path.is_file() or file_sha(path) != replay_expected[name])
    authorization = read(ROOT / "PILOT_AUTHORIZATION_STATE.json")
    confirm_denied = authorization["namespace_authorizations"]["CONFIRM"]["allowed"] is False
    frozen_exists = (ROOT / "FROZEN_CONFIG.yaml").exists()
    run = read(HERE / "run_metadata.json") if (HERE / "run_metadata.json").is_file() else {}
    generation_calls = run.get("generation_calls")
    generation_absent = generation_calls == {"derive_seed": 0, "generate_instance": 0}
    recorded_replay_manifest = run.get("replay_manifest_sha256")
    run_manifest_match = (
        recorded_replay_manifest == file_sha(replay_manifest) if run else None
    )
    preservation_ok = (
        not (manifest_conflicts or missing or changed or added or replay_changes)
        and confirm_denied and not frozen_exists and run_manifest_match is not False
    )
    metadata = dict(
        historical_manifest_count=len(historical),
        audit_input_manifest_count=len(audit_inputs),
        distinct_files_checked=len(combined),
        conflicting_expected_hashes=manifest_conflicts,
        missing=missing,
        changed=changed,
        additional_historical_inputs=added,
        replay_manifest_changes=replay_changes,
        run_manifest_match=run_manifest_match,
        confirm_denied=confirm_denied,
        frozen_config_exists=frozen_exists,
        generation_calls=generation_calls,
        preserved=preservation_ok,
        g5_status=("PASS" if generation_absent and preservation_ok else
                   "INCOMPLETE" if not run and preservation_ok else "FAIL"),
        g5_evidence=[
            "The builder reads the frozen semantic graph, public model and registry, "
            "original public scorer and existing availability masks. It does not open serialized PILOT cases or outcomes.",
            "The cursor receives FLAT's sanitized PublicView, the bound public library, and "
            "the availability entry derived from public capabilities. Complete feature records and node bounds "
            "contain structural features and public costs only.",
            "The audit harness selects the development cohort outside retrieval. It opens the historical "
            "FLAT outcome after the query and passes preferences only to the preserved bilateral protocol and offline witness verifier.",
            "The replay harness guards the instance and seed generators and records their call counters.",
        ],
        comparison_description=(
            "Both trees use deterministic range-based axis selection, median splitting, the same leaf limit "
            "and the same admissible FLAT score bound. The contract forest also groups equal depth-specific "
            "availability, active/offload masks and mechanism bits. Both variants apply the exact public "
            "eligibility check when needed."
        ),
        counting_description=(
            "For indexed prefixes, a candidate whose complete features were loaded for scoring is counted once. "
            "Bound-pruned candidates are eligible candidates left unscored at the returned cutoff. "
            "The count can fall for a longer prefix. FLAT metadata passes, leaf membership checks and "
            "internal-node pops have separate fields."
        ),
        correctness_description=(
            "The comparator calls the preserved FLAT make_plan and independently recomputes candidate scores "
            "with its original proxy. The indexed replay substitutes the B2 ID lookup and structural order provider "
            "in an in-memory copy of the V1 runner. The verifier, agent behavior and protocol come from V1."
        ),
        preservation=(
            f"Source and artifact preservation verified for {len(combined):,} distinct files. "
            "CONFIRM stayed disabled and FROZEN_CONFIG.yaml was absent."
            if preservation_ok else "See the recorded preservation differences in report_metadata.json."
        ),
    )
    (HERE / "report_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: metadata[key] for key in (
        "preserved", "distinct_files_checked", "g5_status", "generation_calls",
        "conflicting_expected_hashes", "missing", "changed", "additional_historical_inputs",
        "replay_manifest_changes", "run_manifest_match",
    )}, indent=2))
    if not preservation_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

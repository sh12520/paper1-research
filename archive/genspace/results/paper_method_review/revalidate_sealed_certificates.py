"""Recheck frozen Depth 3 certificates without executing a search."""

from collections import Counter
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
ARCHIVE = ROOT / "results" / "depth3"
sys.path[:0] = [
    str(ARCHIVE), str(ROOT), str(ROOT / "results" / "grammar_gate"),
    str(ROOT / "results" / "method_dev_v1"),
]

from audit_common import read_json, sealed_payloads
from certificate_report import KS, depth3_slots, prefix_records, public_input, validate_cut


def main():
    seal, cases, seal_sha = sealed_payloads(ARCHIVE / "development" / "search_seal.json")
    historic = read_json(ARCHIVE / "gate_summary.json")
    if (
        historic["status"] != "DEPTH3_PARTIAL"
        or historic["online_seal_sha256"] != seal_sha
        or set(cases) != set(depth3_slots())
        or seal["manifest"]["effective_depth"] != 3
    ):
        raise ValueError("Archived gate, scope or seal mismatch")

    originals = read_json(ROOT / "results" / "pilot" / "instances_manifest.json")
    short = read_json(AUDIT / "short_domain_verification.json")
    if short["status"] != "PASS" or short["development_seal_sha256"] != seal_sha:
        raise ValueError("Independent exhaustive audit does not bind to this seal")
    expected_short = {row["instance_id"]: row["semantic_structural"] for row in short["cases"]}

    rows = []
    tallies = {k: Counter({
        "EXACT_TOPK_FULL_LENGTH": 0, "EXACT_DOMAIN_EXHAUSTED_SHORT": 0,
        "NOT_CERTIFIED_RESOURCE_LIMIT": 0, "UNSOUND": 0,
    }) for k in KS}
    observed_short = {}
    for instance_id, case in cases.items():
        public, identity = public_input(instance_id, originals)
        if case["serialized_sha256"] != identity:
            raise ValueError(f"{instance_id}: original source identity mismatch")
        records = prefix_records(case, public)
        if set(case["k_certificates"]) != set(map(str, KS)):
            raise ValueError(f"{instance_id}: unexpected certificate checkpoints")
        for k in KS:
            cut = case["k_certificates"][str(k)]
            status, reason = validate_cut(cut, k, records)
            if status != "EXACT_TOPK_CERTIFIED":
                raise ValueError(f"{instance_id} at K={k}: {status} {reason}")
            count = cut["returned"]
            result = "EXACT_TOPK_FULL_LENGTH" if count == k else "EXACT_DOMAIN_EXHAUSTED_SHORT"
            if result == "EXACT_DOMAIN_EXHAUSTED_SHORT" and k == 500:
                observed_short[instance_id] = count
            tallies[k][result] += 1
            rows.append({
                "instance_id": instance_id, "K": k, "status": result,
                "returned": count, "prefix_sha256": cut["prefix_sha256"],
            })
    if len(rows) != 72 or observed_short != expected_short or expected_short != historic["exhausted_short_k500"]:
        raise ValueError("Short-domain identity, cardinality or checkpoint coverage mismatch")

    result = {
        "archived_gate_status": historic["status"], "development_seal_sha256": seal_sha,
        "status_counts": tallies, "checkpoints": rows,
    }
    with (AUDIT / "sealed_certificate_revalidation.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(tallies, sort_keys=True))


if __name__ == "__main__":
    main()

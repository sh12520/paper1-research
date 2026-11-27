"""Exercise detached proof publication and recovery on a sealed PILOT record."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from symbolic_format import HERE, ROOT
from audit_common import read_json, write_json
from method_proof_bridge import QueryBinding
from method_proof_cache import ProofCache, file_sha
from holdout_transactions import IntegrityError
from run_depth3_proofs import load_public


def must_refuse(action):
    try:
        action()
    except (IntegrityError,OSError):
        return True
    raise AssertionError("Tampered or wrong-snapshot proof was accepted")


def run(fixture, expected_count):
    view = read_json(HERE/"work"/fixture/"public.json")
    public = load_public(view["public"])
    origin = read_json(ROOT/"results/pilot/instances_manifest.json")[fixture]
    pinned = view["binding"]
    q = QueryBinding(fixture,"GENSPACE-FAIL-01-PILOT",pinned["serialized_sha256"],origin["instance_hash"],
                     pinned["public_hash"],pinned["snapshot_sha256"],pinned["candidate_source_tree_sha256"],
                     file_sha(ROOT/"METHOD_HOLDOUT_IDENTITY_PLAN_DRAFT.json"))
    # Test token and disposable key. This fixture is not assigned a holdout identity.
    addendum = "6"*64
    with TemporaryDirectory(prefix=".cache-test-",dir=HERE) as tmp:
        folder = Path(tmp)
        construct = lambda live:ProofCache(folder,b"e"*32,addendum,live)
        current = construct(lambda:q.snapshot_sha256)
        first = current.load_or_prove(q,public)
        assert len(first.prefix)==expected_count and first.exhausted==(expected_count<500)
        replay = construct(lambda:q.snapshot_sha256).verify_cached(q,public,first.compressed_sha256)
        assert replay==first
        cached = current.load_or_prove(q,public)
        assert cached is first
        mismatch = must_refuse(lambda:construct(lambda:"0"*64).load_or_prove(q,public))
        archive, = folder.glob("*/proof.json.gz")
        archived = read_json(archive.parent/"COMPLETE.json")["value"]
        original = archive.read_bytes()
        archive.write_bytes(original[:-1]+bytes((original[-1]^0xA5,)))
        tampering = must_refuse(lambda:current.verify_cached(q,public,first.compressed_sha256))
    state = read_json(ROOT/"METHOD_AUTHORIZATION_STATE.json")
    assert state["namespace_authorizations"]=={"METHOD_HOLDOUT":False,"CONFIRM":False}
    return dict(status="PASS",fixture=fixture,genesis_proof_sha256=first.compressed_sha256,
                returned=len(first.prefix),exhausted=first.exhausted,
                same_process_reuse=True,bounded_fresh_recheck=True,
                stale_snapshot_rejected=mismatch,tampered_compressed_file_rejected=tampering,
                job_emit_final_active=archived["emitted"]["job_final_active"],
                job_check_final_active=archived["checker"]["job_final_active"],
                production_authorization=state["namespace_authorizations"])


if __name__ == "__main__":
    result = {"status":"PASS","fixtures":[
        run("F4__medium__high__sparse__d2__s0",81),
        run("F2__medium__high__rich__d2__s0",500),
    ]}
    write_json(HERE/"method_proof_cache_checks.json",result)
    print(json.dumps(result))

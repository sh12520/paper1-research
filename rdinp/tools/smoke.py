"""Run bounded local checks against a fresh set of generated image fixtures."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from generate_fixtures import generate

ROOT = Path(__file__).resolve().parents[1]


def run(script: Path, *args, cwd=ROOT, env=None) -> None:
    print("Running", script.relative_to(ROOT), flush=True)
    subprocess.run(
        [sys.executable, "-B", str(script), *map(str, args)],
        cwd=cwd, env=env, check=True, timeout=90,
    )


def run_suite(caddy: str | None) -> None:
    binary = None
    if caddy:
        resolved = shutil.which(caddy)
        if not resolved:
            raise FileNotFoundError(f"Caddy executable unavailable: {caddy}")
        binary = Path(resolved).resolve()

    run_id = "smoke-" + uuid.uuid4().hex[:12]
    output = ROOT / "artifacts" / run_id
    assets = output / "fixtures"
    generate(assets)

    c2 = ROOT / "protocol" / "c2"
    c2_output = c2 / "runs" / run_id
    run(c2 / "local_demo.py", c2_output)
    demo = json.loads((c2_output / "result.json").read_text(encoding="utf-8"))
    if demo["status"] != "COMMITTED":
        raise RuntimeError(f"Unexpected scoped loopback result: {demo['status']}")

    test_env = {**os.environ, "RDINP_EVIDENCE_DIR": str(output / "conformance")}
    subprocess.run(
        [
            sys.executable, "-B", "-m", "unittest", "-v",
            "test_candidate.CandidateTests.test_v9_committed_response_loss_is_unknown_not_rejected",
            "test_candidate.CandidateTests.test_v9_first_success_receipt_survives_second_confirmation_loss",
            "test_candidate.CandidateTests.test_v10_active_cleanup_without_followup_request",
            "test_candidate.CandidateTests.test_v11_subprocess_durable_commit_crash_before_response",
            "test_candidate.CandidateTests.test_v12_client_recovery_no_new_timers_or_negotiation",
        ],
        cwd=c2, env=test_env, check=True, timeout=90,
    )

    experiments = ROOT / "experiments"
    for name in ("service-worker", "durable-worker", "effect-fencing", "proxy-execution"):
        (experiments / name / "runs").mkdir(exist_ok=True)

    worker = experiments / "service-worker"
    run(worker / "check_worker.py", "--out", worker / "runs" / (run_id + ".json"))
    durable = experiments / "durable-worker"
    run(durable / "run_checks.py", "--assets", assets, "--out", durable / "runs" / run_id)
    effect = experiments / "effect-fencing"
    run(effect / "run_effect_baseline.py", "--assets", assets, "--out", effect / "runs" / run_id)
    run(effect / "probe_commit_deadline.py", "--asset", assets / "camera.png",
        "--out", effect / "runs" / (run_id + "-deadline"))
    if binary:
        proxy = experiments / "proxy-execution"
        run(proxy / "run_proxy_effect.py", "--caddy", binary, "--assets", assets,
            "--out", proxy / "runs" / run_id)
        run(proxy / "probe_forward_delay.py", "--caddy", binary, "--assets", assets,
            "--out", proxy / "runs" / (run_id + "-forward"))
        run(proxy / "probe_inflight_route.py", "--caddy", binary, "--assets", assets,
            "--out", proxy / "runs" / (run_id + "-inflight"))
    print("PASS", run_id, "Caddy included" if binary else "Caddy optional checks skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy", help="optionally include checks with this verified Caddy executable")
    run_suite(parser.parse_args().caddy)


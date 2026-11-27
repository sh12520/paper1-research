# Reproduce the local checks

Run commands from the `rdinp` directory. Install `requirements.txt` as described in the [README](../README.md). The commands below create local artifacts. Choose fresh output names each time.

## Protocol

```sh
python -B protocol/c2/local_demo.py protocol/c2/runs/demo
python -B protocol/c2/run_validation.py --targeted
```

Both commands generate their own ephemeral fixture keys. The targeted validation captures its source bytes and records the scoped, local result. The full conformance runner uses the same command without `--targeted` and has tighter timing assumptions. Test outputs can include fixture identifiers, task results and database state. Treat all generated outputs as local evidence.

## Generate inputs and output roots

```sh
python -B tools/generate_fixtures.py artifacts/fixtures
python -c "from pathlib import Path; [p.joinpath('runs').mkdir(exist_ok=True) for p in Path('experiments').iterdir() if p.is_dir()]"
```

The generated sample files are for exercising the mechanism. The original studies used offline sample images already available in their experiment environment. Absolute latencies for this checkout depend on scheduling, storage and input properties.

## Worker and durable worker

```sh
python -B experiments/service-worker/check_worker.py --out experiments/service-worker/runs/checks.json
python -B experiments/service-worker/run_study.py --assets artifacts/fixtures --out experiments/service-worker/runs/worker-demo
python -B experiments/service-worker/audit_results.py experiments/service-worker/runs/worker-demo

python -B experiments/durable-worker/run_checks.py --assets artifacts/fixtures --out experiments/durable-worker/runs/checks
python -B experiments/durable-worker/run_pairs.py --assets artifacts/fixtures --out experiments/durable-worker/runs/pairs
python -B experiments/durable-worker/audit_pairs.py experiments/durable-worker/runs/pairs
python -B experiments/durable-worker/probe_inflight.py experiments/durable-worker/runs/inflight artifacts/fixtures/camera.png
python -B experiments/durable-worker/probe_supervised_reclaim.py experiments/durable-worker/runs/reclaim artifacts/fixtures/camera.png
```

The interruption probes terminate only child processes they started. They model controlled fault conditions and do not alter OS networking.

## Effect fencing and deadline

```sh
python -B experiments/effect-fencing/run_effect_baseline.py --assets artifacts/fixtures --out experiments/effect-fencing/runs/effect-demo
python -B experiments/effect-fencing/probe_commit_deadline.py --asset artifacts/fixtures/camera.png --out experiments/effect-fencing/runs/deadline-demo
```

## Actual Caddy proxy

Set `CADDY_BIN` to the explicit path of the official verified executable. In PowerShell use `$CADDY_BIN = 'path/to/caddy.exe'`; in a POSIX shell use `CADDY_BIN=/path/to/caddy`. All control, front-end and backend sockets bind only to loopback.

```sh
python -B experiments/proxy-execution/run_proxy_effect.py --caddy "$CADDY_BIN" --assets artifacts/fixtures --out experiments/proxy-execution/runs/proxy-demo
python -B experiments/proxy-execution/probe_forward_delay.py --caddy "$CADDY_BIN" --assets artifacts/fixtures --out experiments/proxy-execution/runs/forward-demo
python -B experiments/proxy-execution/probe_inflight_route.py --caddy "$CADDY_BIN" --assets artifacts/fixtures --out experiments/proxy-execution/runs/inflight-demo
```


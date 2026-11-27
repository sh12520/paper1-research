# RDINP protocol and execution diagnostics

This research artifact includes the RDINP C2 negotiation prototype and four locally reproducible execution studies. The prototype uses signed HTTP messages and a single SQLite resource authority. The studies exercise a CPU worker, durable leases, stale-writer controls, and an actual Caddy reverse proxy.

## Quick start

Run these commands from this directory. The export was tested with Python 3.13.9 and the pinned dependencies.

```sh
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on a POSIX shell or `.venv\Scripts\Activate.ps1` on PowerShell.

```sh
python -m pip install -r requirements.txt
python -B tools/smoke.py
```

The smoke command generates deterministic image fixtures, runs the C2 loopback demo and selected conformance tests, and exercises worker, persistence, fencing and deadline checks. It prints output locations within ignored `runs/` and `artifacts/` directories. Each invocation uses a fresh ID.

To include the real proxy checks, obtain [Caddy v2.11.9](https://github.com/caddyserver/caddy/releases/tag/v2.11.9) from its official release, verify the published archive digest, extract the binary locally and pass its path. For example, with Caddy on your PATH:

```sh
python -B tools/smoke.py --caddy caddy
```

| Area | Contents |
|---|---|
| [Protocol](protocol/c2/CONTRACT.md) | Four phases, closed JSON schemas, ES256 authentication, durable logical effects and outcome knowledge |
| [Single worker](experiments/service-worker/STUDY_SPEC.md) | Actual CPU result, fallback and controlled lost replies |
| [Durable worker](experiments/durable-worker/STUDY_SPEC.md) | Sequential tasks, retained quota, restart and execution lease |
| [Effect fencing](docs/REPRODUCE.md#effect-fencing-and-deadline) | Controlled stale publisher, idempotence, expiry and interrupted commit |
| [Proxy](experiments/proxy-execution/STUDY_SPEC.md) | Native ETag, restored configuration, late forwarding and in-flight readback |

See [reproduction commands](docs/REPRODUCE.md) and [scope and attribution](docs/SCOPE.md). The C2 modules and protocol documents keep their original bytes. The source inventory reflects the export subset and experiment paths were made relative. The bundled generator produces engineering fixtures for this checkout. It does not reproduce the original image corpus or its timing measurements.

This artifact is a loopback research prototype. The local experiments use injected timing and loss conditions. Claims about real wireless performance, hard real-time completion or production deployments need additional evidence.


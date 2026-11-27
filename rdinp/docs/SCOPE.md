# Scope and attribution

## Evidence

- The `protocol/c2/` subset is the RDINP-A1-CANDIDATE-2 local prototype. It contains a contract, message and trust schemas, an OpenAPI description, a conditional proof, a loopback demo and associated tests. Historical result archives and host qualification are outside this export.
- The copied modules implement the protocol over one trusted SQLite resource authority. `COMMITTED` describes a logical effect. `UNKNOWN` preserves uncertainty about whether an effect occurred. The authority and workload timing premises apply to any deadline claim.
- The worker and proxy experiments use loopback processes, generated or caller-supplied inputs, and controlled faults. Their output supports execution-interface checks and measurement methods.
- The fixture generator creates three small geometric PNGs. It uses familiar filenames solely because the existing runners expect them. Users may provide independently obtained source images via `--assets`.
- Caddy and Python libraries remain external dependencies. Their own distribution and licensing terms apply. This repository does not bundle those packages, images obtained from others, executables, private keys, or logs.

## Related sources

Caddy's native ETag checks current scoped content, so this artifact separates current content, authorization epoch, dispatch deadline, and business readback. [Caddy API](https://caddyserver.com/docs/api#concurrent-config-changes)

Resource generations and conditional sink operations have established precedents. [Chubby lock service](https://static.usenix.org/events/osdi06/tech/full_papers/burrows/burrows_html/) · [RIFL](https://web.stanford.edu/~ouster/cgi-bin/papers/rifl.pdf)

## Distribution status

A repository license has not been selected for this export. Automatic permission to use or redistribute the repository should not be inferred. Confirm authorship and distribution permissions before public release.


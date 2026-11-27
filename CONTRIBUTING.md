# Contributing

Use a topic branch based on `main`. Keep changes scoped to the relevant subproject and run the checks in its README before opening a pull request.

- Record the input, command, dependency versions, and expected outputs for reproducible changes.
- Keep fixtures small. State whether a test measures software behavior, simulated conditions or physical execution.
- Preserve historical evidence when semantics or metrics change. Add a new version and a short comparison so reviewers can reproduce the affected result.
- Keep machine-specific paths, credentials, research holdouts and large outputs outside the working tree. Track a stable identifier or checksum when a permitted artifact is maintained separately.

Resolved correctness changes belong with their regression checks. Performance changes should state the applicable workload and environment.

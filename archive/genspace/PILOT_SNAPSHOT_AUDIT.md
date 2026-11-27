# Pilot instrumentation preparation snapshot

`PILOT_EXECUTION_SNAPSHOT_FINGERPRINT.json` is a **preparation-only**
snapshot. The existing execution-snapshot verifier can check its
`pilot-preparation` scope, and the separate `PILOT_AUTHORIZATION_STATE.json`
binds its SHA256 while retaining `PILOT=false` and `CONFIRM=false`.

The snapshot compares the current semantic-core hashes, configuration,
semantic graph, complete availability-index hash set, registry, model and
independent reference report against the earlier SMOKE-02 snapshot. Its
source-tree hash additionally binds all current instrumentation, tests,
schemas and the formal identity plan. The historical SMOKE-02 snapshot and
authorization state are not edited or overwritten.

This fingerprint alone does **not** establish that the future PILOT execution
route exists or is enabled. `FastLibrary` currently does not accept the
`pilot-preparation` scope and the seed/routing layer denies PILOT and CONFIRM.
Nor does hashing alone establish behavioral equivalence: that requires the
separate 16-instance SHADOW ON/OFF comparison. No research execution is
authorized by creating these files. Whether a later explicit authorization can
enable PILOT without additional routing work must be decided from the actual
entry-point audit, not inferred from this preparation fingerprint.

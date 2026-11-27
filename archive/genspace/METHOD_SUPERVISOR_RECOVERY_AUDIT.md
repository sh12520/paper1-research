# Method supervisor and recovery · REVIEW

## Supervisor boundary

The new supervisor launches a suspended Windows process, assigns it to the existing kill-on-close Job, and resumes it only after assignment. One active query is dispatched at a time. The worker can retain its loaded process context between queries. The parent maintains the query wall-clock deadline, samples the live process working set and host available memory, verifies the snapshot at the attempt boundaries and monitors its file identity during the attempt. On a limit the parent terminates the whole Job and requires zero active processes before recovery. No solver declaration of exhaustion is derived from a forced stop. [Supervisor](results/method_holdout_readiness/holdout_supervisor.py)

Expansion and frontier events are observed inside the frozen native methods at their existing check and enqueue boundaries. The observer publishes monotonically increasing counts and peak-frontier counts to an authenticated attempt-specific shared memory frame. At the expansion threshold or when the frontier would exceed the permitted observed count, the producer waits for the parent Job termination. The parent independently checks and records the observed counts, and uses its external wall-clock and working-set monitor even if the worker stops publishing. The always-applicable deadlines are 12 s and 45 s in the two planned depths. The query-specific independent working-set cap is 2 GiB; the working set is sampled, so transient memory below the polling interval is outside that measurement. A frontier overshoot is discarded at the native observation boundary, before a newly affected certificate can be accepted. [Worker bridge](results/method_holdout_readiness/holdout_worker.py)

The worker signs the original JSON transport bytes, preserving integer-key ordering through the authentication boundary. Checkpoints are published independently of later phases. A hard interruption preserves only checkpoint files whose recorded completion predates the time limit and stopping observation. Such checkpoints are materials for the independent referee. The warm worker itself returns `PROOF_PENDING` when no later resource stop occurs. V4 public capacity preparation and V5 private utility work use the archived code; their observation overhead and replay time are separate from the public search clock.

The engineering worker accepts only archive-manifest SHA-256 pairs for the fixed method development fixtures and expected effective depths. An engineering flag does not grant native holdout or legacy CONFIRM access. The formal worker requires the independent route and revalidates the approved release bytes for each slot. No stage invoked the formal route with an enabled authorization.

## Actual Windows engineering checks

Both current and generic methods ran on the sealed `F1__low__medium__sparse__d1__s0` bytes with their native formal query bounds. The same warm process returned an identical 500-record public prefix and executed the genuine V4/V5 calls for each method. Fresh engineering limit cases used reduced test limits on the same frozen cursors. The working-set value was measured from the running process.

FULL FLAT and both index routes also ran over those bytes in a second warm process. The real graph and index assets were loaded from verified read-only receipts. The same 500-record prefix digest matched across all five routes. The graph worker did not request legacy PILOT authorization for artifact access.

| Forced-stop check | Observed behavior |
|---|---|
| Wall-clock watchdog | 75 ms limit reached at approximately 77.3 ms while generic search had reported 52 native expansions. The parent terminated the Job. |
| Working set | The deliberate engineering 16 MiB limit detected a live working set of approximately 36.9 MiB. The parent terminated the Job. |
| Expansion stop | The worker published exactly 40 expansions and paused; the parent terminated the Job. |
| Frontier stop | Under the engineering limit of two entries, the next recorded high-water mark was three. The worker paused at that boundary, and the parent terminated the Job. |
| Real V4 and V5 interruptions | The instrumented callback pauses directly after a genuine public capacity preparation or private utility calculation. In each test the parent killed the Job and observed an abnormal exit with zero active Job processes. K=500 material was retained for the referee. |
| A5 stop after K=500 | The warmed query on the existing rich depth-two fixture preserved all four earlier checkpoint records. The parent killed the unfinished exhaustive delivery. |
| Unexpected exit and restart | A deliberately invalid input digest caused worker exit 1. A later real fixture on a new worker reproduced the same ordered prefix. |
| Snapshot drift | A deliberate change to an engineering-only snapshot interrupted a warmed job. The result was blocked and the Job was empty at exit. |

[Measured Windows evidence](results/method_holdout_readiness/supervisor-recovery-zeoco9ev/evidence.json) · [Reproducible engineering test](results/method_holdout_readiness/check_supervisor_recovery.py)

An integration attempt observed a transient Windows read denial immediately after the IPC publisher's atomic rename. The reader now makes at most four attempts at the same authenticated path, with a 2 ms interval, and still rejects persistent denial or an invalid MAC. The full Windows recovery suite and the integrated supervisor, independent referee, transaction and statistics-adapter path were rerun after the fix. [Final Windows regression](results/method_holdout_readiness/supervisor-recovery-_v7yu23k/evidence.json) · [Integrated regression](results/method_holdout_readiness/integration_evidence.json)

## Transaction and resume checks

One attempt transaction binds a slot, method, effective depth, serialized SHA-256, canonical instance hash, method hash, plan hash and snapshot hash. The store writes and flushes the input and result in a unique temporary directory, verifies the exact staged bytes, writes a matching authenticated COMPLETE marker, and publishes the directory with one non-overwriting rename. Reads validate the snapshot, marker authentication, hashes, native instance identity, verdict schema and certificate reference. The coordinator provides an out-of-band signing key held separately from the result directory. An exact successful commit requires the referee flag and matching certificate status. Routine resource outcomes remain terminal results with a resource status.

Independent Job child processes were terminated during the instance write stage, before publication, and immediately after publication. Before publication no terminal directory was accepted and the same slot could be rerun. After publication the parent verified the existing transaction and skipped it. Every duplicate commit failed. A different snapshot, modified result bytes, and a self-reported exact verdict without independent verification all failed closed. Partial staging directories were preserved as diagnostic evidence. These are real process interruption checks and do not cover power-loss behavior or storage-layer failure.

[Transactions](results/method_holdout_readiness/holdout_transactions.py) · [Interruption and tamper evidence](results/method_holdout_readiness/supervisor-recovery-zeoco9ev/evidence.json)

## Scope at review

The warm supervisor and commit primitives passed on the existing development fixture path. The work limits are authenticated native counters at instrumentation boundaries and do not assert a bound on events between two observations. The held-out namespace remains unauthorized. Independent certificate closure is a separate prerequisite and the supervisor makes no certification claim for an unverified Depth 3 result.

# Windows process lifecycle audit

The two prior memory engineering attempts remain BLOCKED and are preserved.
Their sample files do not record child PID and creation time, so the historical
32 KiB readings cannot be retrospectively classified as the original process
identity, PID reuse, or an inaccessible PID.

An independent seed-free Python child probe recorded a live PID and Windows
creation FILETIME, waited for exit code 0, and closed its Popen process handle.
Immediately afterward the same PID and creation time were still accessible;
`GetExitCodeProcess` returned 0. At the next one-second sample the PID was
inaccessible; subsequent observations through nine seconds were also absent.
Thus the new probe supports a briefly accessible terminated process object; it
does not identify which handle or component maintained the prior historical
objects. RSS alone is not used as a reclamation criterion.

`src/process_lifecycle.py` identifies processes by PID and creation FILETIME,
closes the parent's standard streams and process handle after wait, polls for
up to three seconds, records each classification, and accepts only ABSENT or
PID_REUSED; the same identity after timeout fails. It fails closed on access
errors other than the Windows codes indicating absence. A successful return
also requires exit code zero. The prelaunch guard requires three successive
samples at or above 2048 MiB and the emergency guard retains 768 MiB.

Descendants are observed using repeated Toolhelp process snapshots; each
observed PID, creation time, parent PID, parent identity and final identity
classification is recorded. **This is not exhaustive containment:** a
descendant born and exiting between snapshots, or created just before parent
exit between polls, may be missed. Consequently these observations alone
cannot establish the requested zero-surviving-descendant guarantee. A Windows
job object assigned before child execution, or an equivalent authoritative
lifecycle mechanism, is required before claiming that guarantee.

The module additionally exposes named Windows job objects. The parent creates
and holds the job; the child must self-bind at the first line of its entrypoint,
before any work or descendant creation. Job accounting reports active and total
processes, retaining a surviving descendant after its parent exits. A real
seed-free subprocess test confirms active membership until that descendant
exits. This child self-binding has a Python bootstrap window before assignment;
it is not equivalent to creating the process suspended and assigning it before
any child instruction. Every actual run must verify join succeeded and query
zero active job processes after child exit. The caller must also preserve the
parent job handle until that query; no breakaway permission is configured.

Four seed-free unit tests cover identity classes, guard thresholds, a real
short-lived process, and a job containing a surviving descendant. This audit is engineering-only; it neither runs SMOKE-02
nor modifies experiment semantics. End-to-end batch observations, if any,
must be reported separately against their actual source snapshot.

## First real-path batch observation

The first batch finished four ENGINEERING instances with exact reference outputs. Its original process identity (PID 14840, creation FILETIME 134393772873633129) remained accessible with the same creation time throughout the three-second post-exit identity check, so the strict lifecycle criterion failed and the 32-instance run stopped at 4/32. The job reported zero active processes. Toolhelp observed one descendant (PID 11048, creation FILETIME 134393772873732107); its original identity was absent at final inspection. The job is bound after Python interpreter startup, so coverage of the bootstrap interval cannot be guaranteed. Independent short-lived synthetic probes showed that holding the job handle did not consistently retain the original identity; the cause of the actual retained object remains unestablished. Neither the zero job count nor the historical 32 KiB reading substitutes for the requested identity check.

## WINDOWS-LIFECYCLE-FINALIZE-01 — current rule and evidence status

The historical 3-second inaccessible-PID criterion above is superseded for new execution. A waited process with the expected exit code, zero active processes in its non-breakaway Job, and no breakaway is classified `TERMINATED_OBJECT_QUERYABLE` when its same PID and creation time remain queryable; object accessibility alone is not a running process or memory-reclamation failure. Other current classes are `RUNNING`, `PID_REUSED`, and `ABSENT`. The earlier 4/32 BLOCKED run and its original criteria remain historical evidence and are not relabeled as a completed 32-instance run.

A parent-created Job with kill-on-close and a parent-launched CREATE_SUSPENDED process assigned to that Job before ResumeThread is required. A child self-binding after interpreter bootstrap is insufficient for this gate. Assignment, containment, Job accounting and close-on-parent-exit remain pending until directly tested on the new implementation. Toolhelp observations are diagnostic; Job accounting is the containment gate. No SMOKE-02, PILOT or CONFIRM execution is authorized by this engineering audit itself.

## Finalize-01 tested outcome and scope

The parent-side suspended launcher and eight real FAST ENGINEERING batches recorded 8/8 verified Job assignments before resume, no breakaway flags, exit code zero, and ActiveProcesses=0. All 32 ENGINEERING transactions were COMPLETE and matched their reference. Three short-task probes classified terminated objects as queryable while held, without treating that diagnostic as a failure. Full details, including sampled memory, are in `WINDOWS_SUSPENDED_JOB_AUDIT.md` and `results/windows_lifecycle_finalize_01/report.json`.

This closes the observed Windows launcher engineering issue only. The suspended launcher is not integrated into an executable SMOKE-02 192-instance orchestration, and `src/engineering_recovery.py` explicitly accepts only ENGINEERING input. The no-breakaway accounting results must not be presented as a validated SMOKE-02 run or end-to-end SMOKE-02 resume/repeat pipeline.

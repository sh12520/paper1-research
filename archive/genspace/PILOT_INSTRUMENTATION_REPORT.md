# PILOT instrumentation report

Status: **PASS**.

- Main telemetry files: 480; post-main telemetry files: 28.
- Main event records: 27360; post-main event records: 504.
- Each committed instance must have the 12 ordered phase events; each completed batch must contain Job assignment, child start, child pre-exit, and Job completion with zero active processes. Interrupted memory-pause attempts are recorded separately in machine-readable batch details.
- Recorded telemetry sampling errors: 0.
- Minimum sampled physical availability: 1756.484375 MiB. Maximum event-recorded OS worker peak working set: 729.52734375 MiB. These are measured samples, not claims about unobserved instantaneous physical-memory peaks.
- All 508 Job launches passed the three-sample 2,048 MiB prelaunch guard; the minimum prelaunch sample was 2,623.3 MiB. The lower 1,756.5 MiB sample occurred during execution, when the applicable emergency threshold was 768 MiB.
- Samples below the 768 MiB emergency threshold: 0; a legitimate pause is reported, not itself called research failure.
- Phase-event snapshot hash is checked against `18c3ef2eda454dd91a607eaecdd7501f5f82624f907d09bd6939cc77dd6bec0f`.

Machine-readable detail: `results/pilot_integrity_work/report.json`.

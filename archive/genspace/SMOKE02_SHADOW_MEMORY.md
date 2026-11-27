# SMOKE-02 SHADOW memory and Job report

All **32/32 Jobs** returned OK, recorded verified CREATE_SUSPENDED assignment before resume, no breakaway flags, and zero final active processes. Each new child passed three prelaunch samples at the 2048 MiB floor. No 768 MiB emergency breach was recorded. Minimum sampled available physical memory: **2155.23 MiB**. Maximum observed OS-reported worker peak working set: **667.40 MiB**.

The first segment ended with the planned 8/16 stop; the second validated and skipped eight and completed the remainder and post-main stages. Samples and Job records are in `results/smoke02_shadow/segments/`.

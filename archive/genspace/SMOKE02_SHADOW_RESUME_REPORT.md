# SMOKE-02 SHADOW resume report

A planned normal stop occurred after 8/16 completed instances and two batch Jobs. The first segment recorded all eight result and COMPLETE marker hashes. The second segment verified and skipped those same eight, then executed the remaining eight. There were 16 unique main executions, no duplicate COMPLETE, and no re-execution of the first eight. A shadow snapshot copy with a modified source hash was rejected by the real resume inspection path.

This validates the specified planned stop, not all unplanned interruption or low-memory partial-batch recovery. Evidence: `results/smoke02_shadow/segments/00.json`, `segments/01.json`, `snapshot_mismatch_test.json`.

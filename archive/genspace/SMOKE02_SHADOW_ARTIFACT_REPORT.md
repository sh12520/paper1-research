# SMOKE-02 SHADOW candidate artifacts

**4/4 PASS.** The four fixed family-specific candidate-level NPZs were generated after all 16 main transactions, one per fresh suspended child. The common checker decoded the files and verified the exact four-file set, instance ID/hash, graph and snapshot hashes, per-class first-failure digest, and decoded B0/B1/B2/O1 counts against the main summaries. Every associated Job ended with zero active processes.

Evidence: `results/smoke02_shadow/audit/` and the `artifacts` section of `aggregation.json`.

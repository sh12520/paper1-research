# SMOKE reproducibility

```json
{
  "ok": false,
  "rerun8_ids": [
    "F1__medium__high__rich__d2__s0",
    "F1__medium__high__rich__d2__s1",
    "F2__medium__high__rich__d2__s0",
    "F2__medium__high__rich__d2__s1",
    "F3__medium__high__rich__d2__s0",
    "F3__medium__high__rich__d2__s1",
    "F4__medium__high__rich__d2__s0",
    "F4__medium__high__rich__d2__s1"
  ],
  "parallel16_ids": [
    "F1__low__medium__sparse__d1__s0",
    "F1__low__medium__sparse__d2__s0",
    "F1__high__medium__sparse__d1__s0",
    "F1__high__medium__sparse__d2__s0",
    "F2__low__medium__sparse__d1__s0",
    "F2__low__medium__sparse__d2__s0",
    "F2__high__medium__sparse__d1__s0",
    "F2__high__medium__sparse__d2__s0",
    "F3__low__medium__sparse__d1__s0",
    "F3__low__medium__sparse__d2__s0",
    "F3__high__medium__sparse__d1__s0",
    "F3__high__medium__sparse__d2__s0",
    "F4__low__medium__sparse__d1__s0",
    "F4__low__medium__sparse__d2__s0",
    "F4__high__medium__sparse__d1__s0",
    "F4__high__medium__sparse__d2__s0"
  ],
  "rerun8": {
    "ok": false,
    "checks": {
      "exact_repeat_subset": false,
      "non_timing_fields_identical": true
    },
    "expected_repeat_count": 8,
    "observed_repeat_count": 8
  },
  "parallel_1v2": {
    "ok": false,
    "checks": {
      "exact_repeat_subset": false,
      "non_timing_fields_identical": true
    },
    "expected_repeat_count": 16,
    "observed_repeat_count": 0
  },
  "parallel_vs_primary": {
    "ok": false,
    "checks": {
      "exact_repeat_subset": false,
      "non_timing_fields_identical": true
    },
    "expected_repeat_count": 16,
    "observed_repeat_count": 16
  }
}
```

## Available partial comparisons

All 8 preregistered reruns completed, but only 2 have completed primary results; these 2/2 match in all non-timing fields. All 16 one-worker comparisons completed, of which 4/4 overlap and match the partial primary run. The required 2-worker execution was not started because the preregistered memory guard failed, so 1-versus-2-worker equivalence is uncheckable.

# SMOKE invariants

```json
{
  "ok": false,
  "invariants": {
    "C01_192_complete": false,
    "C02_zero_crash": false,
    "C03_zero_silent_skip": false,
    "C04_same_instance_hash": true,
    "C05_space_containment": false,
    "C06_negative_control_exact": false,
    "C07_invalid_never_verified": false,
    "C08_zero_nan_inf": false,
    "C09_utility_unit_interval": false,
    "C10_schema_complete": false,
    "C11_rerun_8_equal": false,
    "C12_1v2_16_equal": false,
    "C13_snapshot_unchanged": true
  },
  "row_checks": {
    "ok": false,
    "checks": {
      "exact_instance_coverage": false,
      "four_distinct_methods": true,
      "paired_instance_hashes": true,
      "complete_output_schema": true,
      "output_finite": true,
      "reported_utilities_unit_interval": true,
      "aggregate_counts_consistent": true,
      "per_instance_checks_all_pass": false,
      "o1_generated_count_matches": false
    },
    "expected_instance_count": 192,
    "observed_instance_count": 35,
    "observed_method_row_count": 140
  },
  "execution": {
    "ok": false,
    "checks": {
      "completion_evidence_present": true,
      "every_instance_completed_once": false,
      "no_crash_or_exception": false,
      "no_explicit_or_silent_skip": false
    },
    "expected_instance_count": 192,
    "completed_instance_count": 35
  },
  "audit_artifacts": {
    "ok": false,
    "checks": {
      "exact_artifact_set": false,
      "decoded_artifacts_match_rows": true
    },
    "expected_count": 4,
    "observed_count": 1,
    "sha256": {
      "F1__medium__high__rich__d2__s0": "d418214edf0dc462656a15f715197cc0c0c17a66ef8295f33b79f1fc1f87dd2f"
    },
    "errors": []
  },
  "per_instance": {
    "F1__high__medium__sparse__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "dd240ed3025c76ad7213e27d8f260b878b9259b92729fe89ff4d023a45bcc868",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__high__medium__sparse__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "6f19407f6b8992e8ce43d60062230a80702ed338846001a4e00cae52a4464832",
        "generated_semantic_class_count": 1512,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 4,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__high__medium__sparse__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "d2843d205c74b5c5bcdf2558c80b2cc1ac479369103cf7e40d973d066bbc417b",
        "generated_semantic_class_count": 11826,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 4,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__high__rich__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "8e475d69514a8a06bb54169fdd67795b244d2e49f59e9d3d3a4d36961c70d477",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__high__rich__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "6c82c924ddd5466f3b4161ac59f75d66f13c1d08dd5ce4032ff5d9e72ae2a935",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__high__rich__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "1d184267454a943c10d489903e07b81c2fd1bf4037bd19571493b32e51ae9ab3",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__high__rich__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "eb5e884ead0c7b8d71ce12cc0ad5a623f451622764011c2af9b54168322ddcfc",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__high__sparse__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "b0df1363892b4fb399a6fb4106692333aa858cb6b4e7034142fae5dac0c88747",
        "generated_semantic_class_count": 783,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__high__sparse__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "2e06055250de6416376982931cf9e5b7a4d824170a5c235d4fad8b1c5694fa81",
        "generated_semantic_class_count": 810,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__high__sparse__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "300d415c5c6a998bd63dd88a38f6f504c200be24f4c28d84dd69509acf26013b",
        "generated_semantic_class_count": 6615,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__high__sparse__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "7bbbb8612a4d642cfa71b3e7420d2c4be194805d036b27675ee7af864eeb12be",
        "generated_semantic_class_count": 6669,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__medium__rich__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "c7e5d571c460397883af17d7d4264ced8761bff71835ab6a1d1f6635eb7e00e5",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__medium__rich__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "e9c1a3933a487d08a7a226a7e5e3cfb77ebcf27b084170c56dcc281aef506131",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__medium__rich__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "728a22b1adea1cc8e14b9d145af104232f63fa8d5b46e9ac416ba8d86f6830b2",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__medium__rich__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "460ec9704035739e5a6cd7a47534e54bf6dc81cd4c113ab4343fb61c3e0f7e88",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__medium__sparse__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "550e117d75d3bc73acfb1ffaae336e257b7a8608b05d29088d886458ca7dabff",
        "generated_semantic_class_count": 81,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__medium__sparse__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "ae311eb5e82f10b9753d873c0138eb8bfaaaf358e200b350b1943257781080e2",
        "generated_semantic_class_count": 783,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__low__medium__sparse__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "feae560deadee39afef3b011adfd7d86124e2106769e3ca7435d249e02b3b5ea",
        "generated_semantic_class_count": 6615,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__low__medium__sparse__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "00bc7e81d0365900bddcf20abee5fb3f3084564ec27e457c0528111f1edb40bf",
        "generated_semantic_class_count": 1288278,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 4,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__high__rich__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "9138dc449534701f08b6bb69d5e9f1dd8b787ff271fcc318e81f4068d779645a",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__high__rich__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "53cdeb01ff7afcc2d82071f9a51eb5e7c80e51b2d5c6d0fbbd2406d90c46de63",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__high__rich__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "061b0df58b84f62aa29be300cc1e3aa4d1e69428ef4ae12e642afe816dea02d0",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__high__rich__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "492340b53094f5f87af2ea46a65b86728a53c9d2a5613b6c7b51c6359a472781",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__high__sparse__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "fe2030e4a6eaff5756c5a63030a5811163449c249209f782c1cb9b59ed6484bc",
        "generated_semantic_class_count": 81,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__high__sparse__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "2dcbaebdde54213abec742c24a8590c724ab1167da2d12d8c910a65a265d53f9",
        "generated_semantic_class_count": 1512,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 4,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__high__sparse__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "26192f946202d2db762eb9eafe435d31e2aa152069f345a3e76df942db6d378c",
        "generated_semantic_class_count": 41607,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__high__sparse__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "0ff398d4e6efc5118da59ef3a92e8967c8d7ccc7a9fa544a3b46511c31c82a67",
        "generated_semantic_class_count": 68121,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 4,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__medium__rich__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "cddcd9f53ed49727ad678799e4229e8b72bc9c88541ccb99d09bc232fa84d7bc",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__medium__rich__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "af84e05fe95947bce17b6ef0a03ad56cd784bcd894e6d4fc6461b7710c05b8b5",
        "generated_semantic_class_count": 1539,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__medium__rich__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "ff54f1dc3757210186b2684204bacf9103d8519dd94030f7199254e8744638cc",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__medium__rich__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "3947f1e13c39abc3f4fe3d5827b0629204259cce4e83c423d2f03698829a78a7",
        "generated_semantic_class_count": 1394064,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 5,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__medium__sparse__d1__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "309639e78b6f72690588a4e141c97e59a2b6ba774f7b808a8cd9a00bd6678b84",
        "generated_semantic_class_count": 108,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__medium__sparse__d1__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "c5903e50ae751f4376fa8d9cd4725f1b0ef61c9e175e59c0c534d828a25e796b",
        "generated_semantic_class_count": 756,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1539
      },
      "ok": true
    },
    "F1__medium__medium__sparse__d2__s0": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "f0f9666cc2fe5ebf27fbee400d56467518c9b6af98348df0a7336e713c045cf5",
        "generated_semantic_class_count": 44685,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 3,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    },
    "F1__medium__medium__sparse__d2__s1": {
      "checks": {
        "all_capacity_cells_finite_nonnegative": true,
        "b2_matches_library_static_mask": true,
        "b2_subset_mc": true,
        "generated_only_in_domain": true,
        "m0_subset_mr_subset_b2": true,
        "negative_control_o1_equals_b2": true,
        "negative_control_pattern_zero": true,
        "no_invalid_class_verified": true,
        "reached_v5_utility_finite_unit_interval": true,
        "stage_masks_nested": true,
        "verified_only_generated": true
      },
      "counts": {
        "first_failure_layer_sha256": "b27005c8529907757becb33287ab2471291cbc2f60a15760ef8223b28d80cc74",
        "generated_semantic_class_count": 2943,
        "invalid_verified_count": 0,
        "negative_control_removed_capability_count": 2,
        "rich_graph_in_domain_count": 1394064
      },
      "ok": true
    }
  }
}
```

## Post-run interpretation

C01-C03 failed because low-memory protection stopped the main worker. C05-C12 are uncheckable for the complete plan and are conservatively false in the machine-readable record. All 35 completed main instances passed their individual negative-control, containment, verified-candidate and defined-utility checks. C04 covers only those 35. The interrupted instance has no post-instance snapshot check.

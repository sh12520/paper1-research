"""Identical C01--C13 validation for shadow and future SMOKE executions.

This module never constructs instances or accesses seeds.  The caller supplies
validated commits, explicit execution evidence, and independent observer data.
Missing evidence is always failure, never implicit success.
"""
from __future__ import annotations
import re
from .smoke_invariants import check_rows,check_repeats,SMOKE_NAMESPACE,SHADOW_NAMESPACE,PILOT_NAMESPACE

EVIDENCE=('no_unexplained_crash','no_silent_skip','all_jobs_passed',
          'snapshot_unchanged','all_complete_markers_valid','artifact_after_main',
          'repeats_after_audit')

def aggregate(*,namespace,planned_ids,instances,main,rerun,fresh,audit_dir,
              audit_ids,rerun_ids,fresh_ids,graph_hash,snapshot_hash,execution_evidence):
    from tools.smoke_01 import check_audit_artifacts
    if namespace not in (SMOKE_NAMESPACE,SHADOW_NAMESPACE,PILOT_NAMESPACE):
        raise ValueError('unsupported experiment namespace')
    expected=list(planned_ids); expected_set=set(expected)
    if not expected or len(expected)!=len(expected_set):raise ValueError('invalid planned identities')
    if len(expected) != {SHADOW_NAMESPACE:16, SMOKE_NAMESPACE:192, PILOT_NAMESPACE:1920}[namespace]:
        raise ValueError('planned coverage does not match namespace')
    for label, subset, count in (('audit',audit_ids,4),('rerun',rerun_ids,8),('fresh',fresh_ids,16)):
        if len(subset)!=count or len(set(subset))!=count or not set(subset)<=expected_set:
            raise ValueError('invalid preregistered '+label+' subset')
    ids=[x.get('instance_id') for x in main]
    ok_main=[x for x in main if x.get('ok') is True]
    rows=[r for x in ok_main for r in x.get('rows',[])]
    checks_by_id={x['instance_id']:x.get('check') for x in ok_main}
    row_report=check_rows(rows,instances,expected_ids=expected,validations=checks_by_id,namespace=namespace)
    row_checks=row_report['checks']
    def every(*names):
        return (len(checks_by_id)==len(expected) and all(isinstance(v,dict) and
            all(v.get('checks',{}).get(name) is True for name in names) for v in checks_by_id.values()))
    def index(items):
        keys=[x.get('instance_id') for x in items]
        if len(keys)!=len(set(keys)) or any(x.get('ok') is not True for x in items):return {}
        return {x['instance_id']:x.get('rows') for x in items}
    primary=index(main); repeats=index(rerun); repeated_fresh=index(fresh)
    r8=check_repeats(primary,repeats,rerun_ids)
    r16=check_repeats(primary,repeated_fresh,fresh_ids)
    artifacts=check_audit_artifacts(audit_dir,audit_ids,rows,graph_hash,snapshot_hash,checks_by_id)
    ev={k:execution_evidence.get(k) is True for k in EVIDENCE}
    snapshot_items=(bool(re.fullmatch(r'[0-9a-f]{64}',str(snapshot_hash))) and
                   all(x.get('snapshot_pre_verified') is True and x.get('snapshot_post_verified') is True
                       and x.get('snapshot_hash')==snapshot_hash for x in main+rerun+fresh))
    complete=(len(main)==len(expected) and len(ids)==len(set(ids)) and set(ids)==expected_set and len(ok_main)==len(expected))
    c={
      'C01_coverage':complete and ev['all_complete_markers_valid'] and row_checks['exact_instance_coverage'],
      'C02_zero_unexplained_crash':ev['no_unexplained_crash'] and ev['all_jobs_passed'],
      'C03_no_silent_skip':complete and ev['no_silent_skip'] and row_checks['four_distinct_methods'],
      'C04_paired_hashes':row_checks['paired_instance_hashes'],
      'C05_space_containment':every('m0_subset_mr_subset_b2','b2_subset_mc','b2_matches_library_static_mask'),
      'C06_negative_control_exact':every('negative_control_pattern_zero','negative_control_o1_equals_b2'),
      'C07_invalid_never_verified':every('stage_masks_nested','verified_only_generated','generated_only_in_domain','all_capacity_cells_finite_nonnegative','no_invalid_class_verified') and all(isinstance(x,dict) and x.get('ok') is True for x in checks_by_id.values()),
      'C08_zero_nan_inf':row_checks['output_finite'] and every('reached_v5_utility_finite_unit_interval'),
      'C09_utility_unit_interval':row_checks['reported_utilities_unit_interval'] and every('reached_v5_utility_finite_unit_interval'),
      'C10_schema_and_artifacts':row_checks['complete_output_schema'] and row_checks['aggregate_counts_consistent'] and row_checks['per_instance_checks_all_pass'] and row_checks['o1_generated_count_matches'] and artifacts['ok'] and ev['artifact_after_main'],
      'C11_rerun8_equal':r8['ok'] and ev['repeats_after_audit'],
      'C12_fresh_repeat16_equal':r16['ok'] and ev['repeats_after_audit'],
      'C13_snapshot_unchanged':ev['snapshot_unchanged'] and snapshot_items,
    }
    return {'ok':all(c.values()),'invariants':c,'rows':row_report,'artifacts':artifacts,
            'rerun8':r8,'fresh16':r16,'execution_evidence':ev,'snapshot_items_verified':snapshot_items}

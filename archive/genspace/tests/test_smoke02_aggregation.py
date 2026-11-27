"""Seed-free tests of strict shared aggregation, not a shadow experiment."""
import unittest
from unittest.mock import patch
from src.smoke02_aggregation import aggregate,EVIDENCE
from src.smoke_invariants import SHADOW_NAMESPACE

class AggregateTests(unittest.TestCase):
    def fixtures(self):
        names=('m0_subset_mr_subset_b2','b2_subset_mc','b2_matches_library_static_mask',
               'negative_control_pattern_zero','negative_control_o1_equals_b2','stage_masks_nested',
               'verified_only_generated','generated_only_in_domain','all_capacity_cells_finite_nonnegative',
               'no_invalid_class_verified','reached_v5_utility_finite_unit_interval')
        item={'instance_id':'x','ok':True,'rows':[],'check':{'ok':True,'checks':{k:True for k in names}},
              'snapshot_pre_verified':True,'snapshot_post_verified':True,'snapshot_hash':'b'*64}
        ids=['x']+['y'+str(i) for i in range(15)]
        items=[{**item,'instance_id':iid} for iid in ids]
        return dict(namespace=SHADOW_NAMESPACE,planned_ids=ids,instances={iid:object() for iid in ids},main=items,
                    rerun=items[:8],fresh=items,audit_dir='unused',audit_ids=ids[:4],rerun_ids=ids[:8],fresh_ids=ids,
                    graph_hash='a'*64,snapshot_hash='b'*64,execution_evidence={k:True for k in EVIDENCE})
    def run_with_stubbed_data(self,kw,artifact_ok=True):
        checks={k:True for k in ('exact_instance_coverage','four_distinct_methods','paired_instance_hashes',
                 'complete_output_schema','output_finite','reported_utilities_unit_interval',
                 'aggregate_counts_consistent','per_instance_checks_all_pass','o1_generated_count_matches')}
        with patch('src.smoke02_aggregation.check_rows',return_value={'checks':checks}),\
             patch('src.smoke02_aggregation.check_repeats',return_value={'ok':True}),\
             patch('tools.smoke_01.check_audit_artifacts',return_value={'ok':artifact_ok}):
            return aggregate(**kw)
    def test_complete_evidence_and_each_required_evidence(self):
        self.assertTrue(self.run_with_stubbed_data(self.fixtures())['ok'])
        for key in EVIDENCE:
            kw=self.fixtures();del kw['execution_evidence'][key]
            self.assertFalse(self.run_with_stubbed_data(kw)['ok'],key)
    def test_no_missing_validation_or_artifact(self):
        kw=self.fixtures();kw['main'][0]['check']['checks']['no_invalid_class_verified']=False
        self.assertFalse(self.run_with_stubbed_data(kw)['invariants']['C07_invalid_never_verified'])
        self.assertFalse(self.run_with_stubbed_data(self.fixtures(),False)['invariants']['C10_schema_and_artifacts'])
    def test_duplicate_plan_and_forbidden_namespace(self):
        kw=self.fixtures();kw['planned_ids']=['x','x']
        with self.assertRaises(ValueError):self.run_with_stubbed_data(kw)
        kw=self.fixtures();kw['namespace']='GENSPACE-FAIL-01-PILOT'
        with self.assertRaises(ValueError):self.run_with_stubbed_data(kw)

if __name__=='__main__':unittest.main()

"""PILOT identity-only plan tests. No actual seed or instance is generated."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src.pilot_plan import PILOT_NAMESPACE, pilot_template, validate_pilot_template, inherited_engineering_subsets


class PilotPlanTests(unittest.TestCase):
    def test_fixed_identity_grid_without_seed_calls(self):
        with patch('src.instances.derive_seed', side_effect=AssertionError('seed access')), \
             patch('src.instances.generate_instance', side_effect=AssertionError('instance access')):
            p = pilot_template()
            self.assertTrue(validate_pilot_template(p))
            self.assertEqual(p, json.loads(Path('PILOT01_PLAN_TEMPLATE.json').read_text(encoding='utf8')))
        self.assertEqual(len(p['instances']), 1920)
        self.assertTrue(all(x['namespace'] == PILOT_NAMESPACE for x in p['instances']))
        self.assertEqual(p, pilot_template())
        sets=inherited_engineering_subsets(p)
        self.assertEqual([len(sets[k]) for k in ('audit4','rerun8','fresh_repeat16')],[4,8,16])
        self.assertEqual(len(set(sets['audit4'])),4)
        self.assertTrue(set(sets['audit4']) <= set(sets['rerun8']))

    def test_missing_duplicate_reordered_and_namespace_rejected(self):
        for mode in ('missing', 'duplicate', 'order', 'namespace'):
            p = copy.deepcopy(pilot_template())
            if mode == 'missing': p['instances'].pop()
            elif mode == 'duplicate': p['instances'][-1] = p['instances'][0]
            elif mode == 'order': p['instances'][0], p['instances'][1] = p['instances'][1], p['instances'][0]
            else: p['instances'][0]['namespace'] = 'GENSPACE-FAIL-01-CONFIRM'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_pilot_template(p)

    def test_common_plan_dispatch_without_seed(self):
        import src.experiment_orchestrator as orchestration
        with patch.object(orchestration, 'NAMESPACE', PILOT_NAMESPACE), \
             patch('src.instances.derive_seed', side_effect=AssertionError('seed access')), \
             patch('src.instances.generate_instance', side_effect=AssertionError('instance access')):
            plan=orchestration.getplan()
        self.assertEqual(len(plan['instances']),1920)
        self.assertEqual([len(plan[k]) for k in ('audit4','rerun8','fresh_repeat16')],[4,8,16])

    def test_same_aggregator_admits_pilot_coverage_without_seed(self):
        from src.smoke02_aggregation import aggregate, EVIDENCE
        plan=pilot_template(); ids=[s['instance_id'] for s in plan['instances']]
        subsets=inherited_engineering_subsets(plan)
        names=('m0_subset_mr_subset_b2','b2_subset_mc','b2_matches_library_static_mask',
               'negative_control_pattern_zero','negative_control_o1_equals_b2','stage_masks_nested',
               'verified_only_generated','generated_only_in_domain','all_capacity_cells_finite_nonnegative',
               'no_invalid_class_verified','reached_v5_utility_finite_unit_interval')
        items=[{'instance_id':iid,'ok':True,'rows':[],
                'check':{'ok':True,'checks':{k:True for k in names}},
                'snapshot_pre_verified':True,'snapshot_post_verified':True,'snapshot_hash':'b'*64} for iid in ids]
        byid={x['instance_id']:x for x in items}
        row_names=('exact_instance_coverage','four_distinct_methods','paired_instance_hashes',
                   'complete_output_schema','output_finite','reported_utilities_unit_interval',
                   'aggregate_counts_consistent','per_instance_checks_all_pass','o1_generated_count_matches')
        with patch('src.instances.derive_seed', side_effect=AssertionError('seed access')), \
             patch('src.instances.generate_instance', side_effect=AssertionError('instance access')), \
             patch('src.smoke02_aggregation.check_rows',return_value={'checks':{k:True for k in row_names}}), \
             patch('src.smoke02_aggregation.check_repeats',return_value={'ok':True}), \
             patch('tools.smoke_01.check_audit_artifacts',return_value={'ok':True}):
            result=aggregate(namespace=PILOT_NAMESPACE,planned_ids=ids,instances={},main=items,
                rerun=[byid[i] for i in subsets['rerun8']],fresh=[byid[i] for i in subsets['fresh_repeat16']],
                audit_dir='unused',audit_ids=subsets['audit4'],rerun_ids=subsets['rerun8'],
                fresh_ids=subsets['fresh_repeat16'],graph_hash='a'*64,snapshot_hash='b'*64,
                execution_evidence={k:True for k in EVIDENCE})
        self.assertTrue(result['ok'])

    def test_shared_row_validator_accepts_index_19_and_rejects_20(self):
        from tests.test_smoke_invariants import synthetic
        from src.smoke_invariants import check_rows
        instance, _, _, _, _ = synthetic()
        instance.namespace=PILOT_NAMESPACE
        validations_template={'ok':True,'counts':{'generated_semantic_class_count':3,
                                                   'rich_graph_in_domain_count':3}}
        def assess(index):
            iid=f'F1__low__medium__rich__d2__s{index}'
            instance.seed_label=str(index)
            rows=[]
            for method,count in (('B0',1),('B1',2),('B2',2),('O1',3)):
                rows.append({'instance_id':iid,'seed_index':index,'method':method,
                    'agreement':False,'candidate_count':count,'validator_rejections':{'V4':count},
                    'verified_count':0,'representative':None,'application_utility':None,
                    'network_utility':None,'nash_welfare':None,'compiled_actions':None,
                    'runtime_seconds':.1,'instance_hash':instance.instance_hash,
                    'public_hash':instance.public_hash,'private_hash':instance.private_hash,
                    'family':instance.public.family,'configuration':instance.public.configuration,
                    'namespace':PILOT_NAMESPACE,'seed_label':str(index),'structurally_novel':None,
                    'mechanism_labels':(),'capability_count':None,'ast_depth':None,
                    'rich_graph_in_domain_count':3})
            return check_rows(rows,{iid:instance},[iid],{iid:validations_template},namespace=PILOT_NAMESPACE)
        with patch('src.instances.derive_seed', side_effect=AssertionError('seed access')), \
             patch('src.instances.generate_instance', side_effect=AssertionError('instance access')):
            self.assertTrue(assess(19)['ok'])
            self.assertFalse(assess(20)['ok'])

if __name__ == '__main__': unittest.main()

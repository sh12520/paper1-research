"""Seed-free synthetic checks; no SMOKE instance is generated."""
from dataclasses import asdict
import hashlib
from types import SimpleNamespace
import unittest

import numpy as np

from src.compact_semantics import CompactEncoder
from src.models import Profile, Static, Delay
from src.registry import default_registry
from src.instances import registry_from_public
from src.stage_report import derive_candidate_layers
from src.smoke_invariants import (SMOKE_NAMESPACE, check_execution_status,
    check_instance, check_repeats, check_rows, check_snapshot_unchanged,
    expected_instance_ids, _negative_available)


class Variant:
    def __init__(self, mask): self.value = np.asarray(mask, dtype=bool)
    def mask(self, depth): return self.value


class Bundle:
    def __init__(self, negative): self.entries = {0: Variant(negative)}
    def pattern(self, evaluator):
        roles = dict(zip(evaluator.reference.roles, evaluator.reference.available))
        groups = (('observe_motion_state', 'apply_conditional_policy'), ('apply_phased_policy',),
                  ('schedule_start',), ('enable_edge_offload', 'reserve_edge_compute'),
                  ('set_validity_interval',))
        return sum(1 << i for i, group in enumerate(groups) if all(roles[r] for r in group))


def synthetic():
    reg = default_registry()
    profiles = (Profile(.4, 1., 1.), Profile(.8, 1., 1.))
    cfg = {'resource_pressure': 'low', 'preference_conflict': 'medium',
           'capability_richness': 'rich', 'composition_depth': 2}
    public = SimpleNamespace(family='F1', configuration=cfg, horizon=3, states=('still', 'moving'),
        b2_profiles=profiles, mr_profiles=profiles, m0_profiles=profiles[:1],
        capabilities=tuple(reg), registry={k: asdict(v) for k, v in reg.items()},
        capacity=tuple((t, s, .5, 1., 1.) for t in range(3) for s in ('still', 'moving')),
        public_constraints={'min_active_slots': 1, 'min_quality': 0., 'max_deadline': 2., 'reservation_supported': True},
        resource_parameters={'fh_rate_factor': .4, 'offload_ran_factor': .5,
                             'offload_fh_factor': .7, 'offload_edge_factor': .5})
    encoder = CompactEncoder(public)
    a, b = (encoder.encode(Static(p)) for p in profiles)
    structural = encoder.encode(Delay(1, Static(profiles[0])))
    key_bytes = sorted((a, b, structural))
    keys = np.array([list(k) for k in key_bytes], dtype=np.uint8)
    cells = keys[:, 25:].reshape(-1, 6, 4)
    required = np.zeros(len(keys), dtype=np.uint16)
    for i in range(12): required |= (keys[:, 1 + 2*i] != 255).astype(np.uint16) << i
    scalar = np.array([key in (a, b) for key in key_bytes], dtype=bool)
    library = SimpleNamespace(keys=keys, structural=~scalar,
        profiles=cells[:, :, 0], active=cells[:, :, 0] != 255,
        level=cells[:, :, 1], role_masks=(cells[:, :, 2].astype(np.uint16) << 8) | cells[:, :, 3],
        required_role_masks=required, availability=Bundle(scalar))
    chosen = key_bytes.index(a)
    domain = np.ones(len(keys), dtype=bool)
    physical = np.zeros(len(keys), dtype=bool); physical[chosen] = True
    app = np.full(len(keys), np.nan); app[chosen] = .5
    network = np.full(len(keys), np.nan); network[chosen] = .6
    nash = np.full(len(keys), np.nan); nash[chosen] = .3
    result = SimpleNamespace(in_domain=domain, v2_pass=domain.copy(), v3_pass=domain.copy(),
        physical_ok=physical, accepted=physical.copy(), application_utility=app,
        network_utility=network, nash=nash)
    instance = SimpleNamespace(namespace=SMOKE_NAMESPACE, public=public, seed_label='0',
        instance_hash='a' * 64, public_hash='b' * 64, private_hash='c' * 64)
    return instance, library, result, Variant(domain), key_bytes


class SmokeInvariantTests(unittest.TestCase):
    def test_192_plan_has_no_duplicate_ids(self):
        ids = expected_instance_ids()
        self.assertEqual((len(ids), len(set(ids))), (192, 192))

    def test_negative_control_and_every_verified_physical_check(self):
        inst, lib, result, variant, keys = synthetic()
        kept, _ = _negative_available(inst.public, registry_from_public(inst.public))
        self.assertEqual(set(inst.public.capabilities) - set(kept), {
            'apply_conditional_policy', 'apply_phased_policy', 'schedule_start',
            'set_validity_interval', 'enable_edge_offload'})
        self.assertIn('observe_motion_state', kept)
        self.assertIn('reserve_edge_compute', kept)
        report = check_instance(inst, lib, None, result, variant)
        self.assertTrue(report['ok'], report)
        self.assertTrue(report['checks']['negative_control_o1_equals_b2'])
        self.assertEqual(len(report['counts']['first_failure_layer_sha256']), 64)
        artifact = derive_candidate_layers(result, variant.mask(2))
        self.assertEqual(report['counts']['first_failure_layer_sha256'],
                         hashlib.sha256(artifact.tobytes()).hexdigest())
        # Claiming the high-quality static class verified violates RAN capacity.
        high = next(i for i in range(len(keys)) if lib.profiles[i, 0] == 1)
        result.physical_ok[high] = result.accepted[high] = True
        result.application_utility[high], result.network_utility[high], result.nash[high] = .5, .6, .3
        bad = check_instance(inst, lib, None, result, variant)
        self.assertFalse(bad['ok'])
        self.assertGreater(bad['counts']['invalid_verified_count'], 0)
        self.assertNotEqual(report['counts']['first_failure_layer_sha256'],
                            bad['counts']['first_failure_layer_sha256'])

    def test_negative_set_difference_and_nonfinite_utility_fail(self):
        inst, lib, result, variant, _ = synthetic()
        lib.availability.entries[0].value[:] = True
        self.assertFalse(check_instance(inst, lib, None, result, variant)['checks']['negative_control_o1_equals_b2'])
        inst, lib, result, variant, _ = synthetic()
        result.application_utility[result.physical_ok] = np.nan
        self.assertFalse(check_instance(inst, lib, None, result, variant)['checks']['reached_v5_utility_finite_unit_interval'])

    def test_rows_complete_and_partial_fails(self):
        inst, _, _, _, _ = synthetic()
        iid = 'F1__low__medium__rich__d2__s0'
        rows = []
        for method, count in (('B0', 1), ('B1', 2), ('B2', 2), ('O1', 3)):
            rows.append({'instance_id': iid, 'seed_index': 0, 'method': method, 'agreement': False,
                'candidate_count': count, 'validator_rejections': {'V4': count}, 'verified_count': 0,
                'representative': None, 'application_utility': None, 'network_utility': None,
                'nash_welfare': None, 'compiled_actions': None, 'runtime_seconds': .1,
                'instance_hash': inst.instance_hash, 'public_hash': inst.public_hash,
                'private_hash': inst.private_hash, 'family': inst.public.family,
                'configuration': inst.public.configuration, 'namespace': SMOKE_NAMESPACE,
                'seed_label': '0', 'structurally_novel': None, 'mechanism_labels': (),
                'capability_count': None, 'ast_depth': None, 'rich_graph_in_domain_count': 3})
        validations = {iid: {'ok': True, 'counts': {'generated_semantic_class_count': 3,
                                                  'rich_graph_in_domain_count': 3}}}
        self.assertTrue(check_rows(rows, {iid: inst}, [iid], validations)['ok'])
        self.assertFalse(check_rows(rows[:-1], {iid: inst}, [iid], validations)['ok'])
        self.assertFalse(check_rows(rows, {iid: inst}, [iid], None)['ok'])

    def test_explicit_completion_repeat_and_snapshot_rules(self):
        self.assertTrue(check_execution_status(['i'], [], [], ['i'])['ok'])
        self.assertFalse(check_execution_status(['i'], None, [], ['i'])['ok'])
        self.assertFalse(check_execution_status(['i', 'i'], [], [], ['i'])['ok'])
        primary = {'i': [{'runtime_seconds': 1., 'compiled_actions': [{'action': 1}]}]}
        repeat = {'i': [{'runtime_seconds': 2., 'compiled_actions': [{'action': 1}]}]}
        self.assertTrue(check_repeats(primary, repeat, ['i'])['ok'])
        repeat['i'][0]['compiled_actions'][0]['action'] = 2
        self.assertFalse(check_repeats(primary, repeat, ['i'])['ok'])
        self.assertTrue(check_snapshot_unchanged('a'*64, 'a'*64)['ok'])
        self.assertFalse(check_snapshot_unchanged('a'*64, 'b'*64)['ok'])


if __name__ == '__main__':
    unittest.main()

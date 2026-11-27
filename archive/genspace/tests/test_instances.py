import unittest
from dataclasses import replace
from copy import deepcopy
from src.instances import generate_instance as _generate_instance, deserialize_instance, demand, hard_check, utilities, load_model_config, digest
from src.models import Profile

C = {'resource_pressure':'medium','preference_conflict':'medium','capability_richness':'rich','composition_depth':2}

def generate_instance(family, configuration, seed):
    return _generate_instance(family, configuration, seed, namespace='GENSPACE-FAIL-01-ENGINEERING')

class InstanceModelTests(unittest.TestCase):
    def test_engineering_instance_roundtrip_and_hashes(self):
        x=generate_instance('F1',C,0)
        y=deserialize_instance(x.serialize())
        self.assertEqual(x,y)
        self.assertEqual((x.public_hash,x.private_hash,x.instance_hash),(y.public_hash,y.private_hash,y.instance_hash))
        self.assertEqual(x,generate_instance('F1',C,0))
        self.assertNotEqual(x.instance_hash,generate_instance('F1',C,1).instance_hash)

    def test_model_config_is_loaded_and_hashed(self):
        cfg=load_model_config()
        x=generate_instance('F1',C,0)
        m=cfg['model_draft']
        self.assertEqual(x.public.model_config_hash,digest({'model_draft':m,'capability_cost_accounting':cfg['capability_cost_accounting']}))
        self.assertEqual(set(p.deadline for p in x.public.b2_profiles),set(m['scalar_domains']['b2']['deadline']))
        self.assertEqual(x.public.resource_parameters,m['demand'])

    def test_registry_is_part_of_public_hash(self):
        x=generate_instance('F1',C,0)
        changed=deepcopy(x.public.registry)
        changed['set_rate']['execution_cost']=0.9
        y=replace(x,public=replace(x.public,registry=changed))
        self.assertNotEqual(x.public_hash,y.public_hash)
        self.assertNotEqual(x.instance_hash,y.instance_hash)
        self.assertEqual(x.private_hash,y.private_hash)

    def test_full_scalar_cartesian_and_inclusion(self):
        x=generate_instance('F2',C,0).public
        self.assertEqual((len(x.m0_profiles),len(x.mr_profiles),len(x.b2_profiles)),(1,8,27))
        self.assertTrue(set(x.m0_profiles) <= set(x.mr_profiles) <= set(x.b2_profiles))

    def test_cost_surcharges_reduce_network_utility(self):
        x=generate_instance('F1',C,0)
        actions=tuple((t,s,Profile(.4,1.,1.),'none') for t in range(3) for s in x.public.states)
        base=utilities(x.public,x.private,actions)
        charged=utilities(x.public,x.private,actions,execution_cost=.1,resource_surcharge={'EDGE':.1})
        self.assertEqual(base[0],charged[0])
        self.assertLess(charged[1],base[1])

    def test_utility_bounds_and_hard_separation(self):
        x=generate_instance('F3',C,0)
        actions=tuple((t,s,Profile(.8,1.,1.),'none') for t in range(3) for s in x.public.states)
        self.assertTrue(hard_check(x.public, actions))
        self.assertEqual(demand(x.public, actions[0][2], 'none', 0, 'still'), {'RAN':.8,'FH':.4,'EDGE':0.})
        self.assertTrue(all(0<=v<=1 for v in utilities(x.public,x.private,actions)))
        self.assertFalse(hard_check(x.public, ()))

if __name__=='__main__': unittest.main()

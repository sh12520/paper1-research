"""Depth-one engineering performance fixtures; no research outcome output.

Not a pilot, smoke, confirmation or completeness proof. A separate semantic
reference test is required before using any benchmark as an existence oracle.
"""
import json
import statistics
from time import perf_counter
from .instances import generate_instance
from .runner import precompute_library, library_basis_hash
from .state_machine import semantic_key, verify_instance


def run():
    namespace='GENSPACE-FAIL-01-ENGINEERING'
    configs=[]
    for index in range(20):
        config={'resource_pressure': ('low','medium','high')[index % 3],
                'preference_conflict': ('medium','high')[index % 2],
                'capability_richness': 'rich', 'composition_depth': 1}
        family=('F1','F2','F3','F4')[index % 4]
        configs.append((family,config,'depth1-performance-fixture-'+str(index)))
    instances=[generate_instance(f,c,s,namespace=namespace) for f,c,s in configs]
    started=perf_counter()
    prepared=precompute_library(instances[0].public,1)
    precompute=perf_counter()-started
    checks=[]
    all_times=[]
    for instance in instances:
        if library_basis_hash(instance.public,1) != prepared.basis_hash:
            raise ValueError('fixtures cannot share this precomputed library')
        start=perf_counter()
        for signature, entry in prepared.entries.items():
            if semantic_key(entry.witness,instance.public) != signature:
                raise ValueError('semantic library mismatch')
            verify_instance(entry.witness,instance,1)
        all_times.append(perf_counter()-start)
        checks.append(len(prepared.entries))
    return {'purpose':'engineering only; not research outcomes', 'namespace':namespace,
            'fixture_count':len(instances),'depth':1,'semantic_classes':len(prepared.entries),
            'library_precompute_seconds':precompute,
            'validation_per_instance_seconds':all_times,
            'validation_median_seconds':statistics.median(all_times),
            'validation_min_seconds':min(all_times), 'validation_max_seconds':max(all_times),
            'validation_scope':'signature check plus combined V1-V5; cannot split V2-V4 and V5',
            'reuse':'one in-memory library reused for all fixtures'}

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))

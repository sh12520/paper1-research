"""Create a locked, explicitly non-executable SMOKE-02 integration draft.

The existing execution_snapshot verifier intentionally rejects this extended
format. No instance generation or experimental namespace access occurs here.
"""
from pathlib import Path
import json
from .execution_snapshot import ROOT, build_snapshot, sha256_file

TARGET=ROOT/'SMOKE02_EXECUTION_SNAPSHOT_FINGERPRINT.json'

def locked_draft():
    obj=build_snapshot(scope='smoke02')
    files={'orchestrator':'src/smoke_orchestrator.py','fast_runner':'src/fast_runner.py',
           'windows_launcher':'src/windows_suspended_job.py','plan_template':'SMOKE02_PLAN_TEMPLATE.json',
           'shadow_plan':'SMOKE02_SHADOW_PLAN.json'}
    obj['integration_bindings']={k:{'path':v,'sha256':sha256_file(ROOT/v) if (ROOT/v).is_file() else None}
                                 for k,v in files.items()}
    obj['schema_versions']={'semantic_library':obj['semantic_library_format_version'],
                            'execution_snapshot':obj['snapshot_version'],
                            'orchestrator_commit':'UNIMPLEMENTED_PENDING_REVIEW'}
    obj['authorized_for_execution']=False
    obj['integration_status']='BLOCKED_PENDING_NAMESPACE_AND_PIPELINE_VALIDATION'
    return obj

def write_locked_draft(path=TARGET):
    data=locked_draft()
    Path(path).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',encoding='utf8')
    return data

if __name__=='__main__':
    write_locked_draft()
    print('locked non-executable integration draft written')

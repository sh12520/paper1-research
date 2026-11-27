"""Isolated preview runner for differential tests; never production provenance."""
from pathlib import Path
import runpy,sys
ROOT=Path(__file__).resolve().parents[3]
METHOD=ROOT/'results/method_dev_v1';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(METHOD));sys.path.insert(0,str(Path(__file__).parent))
import runtime,private_protocol
from preview_protocol import HeapPrivateAgent,PreviewPublicVerifier
runtime.PublicVerifier=PreviewPublicVerifier
private_protocol.PrivateAgent=HeapPrivateAgent
sys.argv=[str(METHOD/'harness.py'),*sys.argv[1:]]
runpy.run_path(str(METHOD/'harness.py'),run_name='__main__')

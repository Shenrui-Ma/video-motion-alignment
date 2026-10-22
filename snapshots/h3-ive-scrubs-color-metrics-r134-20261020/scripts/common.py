"""Reuse the verified R120 consumer in the R134 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='09bfa9b6aa5c4035b17b690753abb4c725b7bab683efeafbeb427794d75cdd37'
_code=_shared_bytes.decode().replace('r120','r134').replace('R120','R134')
exec(compile(_code,str(_shared),'exec'),globals())

SOURCES=('short_0353',)
EXPECTED_PROMPT_SHA='8e015a65d5b1ba8f44db4d9372c0e354f7dd95dbb90fc4ea7086c720684b6a6e'
def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='IVEBench-edit-with-generic-retention-v1','prompt format label differs')
 require(_hashlib.sha256(p['prompt'].encode()).hexdigest()==EXPECTED_PROMPT_SHA,'frozen task/reference/retention prompt changed')
 require(p['original_task']['edit_prompt'] in p['prompt'],'official edit instruction missing')
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')

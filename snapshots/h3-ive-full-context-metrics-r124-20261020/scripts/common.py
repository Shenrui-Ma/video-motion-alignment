"""Reuse the verified R120 consumer in the R124 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='09bfa9b6aa5c4035b17b690753abb4c725b7bab683efeafbeb427794d75cdd37'
_code=_shared_bytes.decode().replace('r120','r124').replace('R120','R124')
exec(compile(_code,str(_shared),'exec'),globals())

SOURCES=('long_0163',)
EXPECTED_PROMPT_SHA='d212cd5d5fffe20c9619882c226470d45b8fe6708b1a081f7a5243842a0ed4fb'
def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='IVEBench-official-fields-full-Context-IR-v1','prompt format label differs')
 require(_hashlib.sha256(p['prompt'].encode()).hexdigest()==EXPECTED_PROMPT_SHA,'full Context-IR prompt changed')
 for field in ('source_prompt','edit_prompt','target_prompt'):
  require(p['original_task'][field] in p['prompt'],'official benchmark field missing: '+field)
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')

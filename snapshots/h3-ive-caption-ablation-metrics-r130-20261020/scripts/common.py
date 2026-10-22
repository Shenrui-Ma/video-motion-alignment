"""Reuse the verified R120 consumer in the R130 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='09bfa9b6aa5c4035b17b690753abb4c725b7bab683efeafbeb427794d75cdd37'
_code=_shared_bytes.decode().replace('r120','r130').replace('R120','R130')
exec(compile(_code,str(_shared),'exec'),globals())

SOURCES=('long_0163',)
EXPECTED_PROMPT_SHA='5a788849aaf2a3353aa21e0690111b05179d0f9bc2c1d205708b86bf237c75ce'
def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='IVEBench-subject-bound-edit-no-caption-narrative-v1','prompt format label differs')
 require(_hashlib.sha256(p['prompt'].encode()).hexdigest()==EXPECTED_PROMPT_SHA,'full Context-IR prompt changed')
 require(p['original_task']['edit_prompt'] in p['prompt'],'official edit missing')
 for field in ('source_prompt','target_prompt'):
  require(p['original_task'][field] not in p['prompt'],'caption ablation violated: '+field)
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')

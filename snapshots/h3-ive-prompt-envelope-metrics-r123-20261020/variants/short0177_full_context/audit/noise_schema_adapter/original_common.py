"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='bad6f9addae1e7fb64b9f555b130eb1a8d64359a081e20bf3b3ae74b7abaf631'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

FULL_PROMPT_SHA="17a38d6ba56c73788a941238ef456c59e17c3bb0e2078d935a87af8220099b3d"
def verify_official_prompt(p,graph=None):
 require(p['prompt_version']=='official_context_ir_with_benchmark_captions_and_subject_binding','prompt format label differs')
 require(hashlib.sha256(p['prompt'].encode()).hexdigest()==FULL_PROMPT_SHA,'full Context-IR prompt changed')
 for field in ('source_prompt','edit_prompt','target_prompt'):
  require(p['original_task'][field] in p['prompt'],'benchmark caption or edit text missing')
 if graph is not None:require(graph['5']['inputs']['prompt']==p['prompt'],'actual graph prompt differs')

SOURCES=('short_0177',)

SOURCES=('short_0177',)

SOURCES=('short_0177',)

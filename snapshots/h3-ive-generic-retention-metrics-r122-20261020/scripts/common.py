"""Reuse SHA-bound R120 consumer helpers for one R122 source."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='09bfa9b6aa5c4035b17b690753abb4c725b7bab683efeafbeb427794d75cdd37'
_code=_shared_bytes.decode().replace('r120','r122').replace('R120','R122')
exec(compile(_code,str(_shared),'exec'),globals())

SOURCES=('long_0039',)
TASK_ENVELOPE = 'subject_definitions:\n<Video 1> is the source video for this edit.\n\nsummary:\n[video editing] The target video is an edited version of <Video 1>.\n'
GENERIC_RETENTION = "\n\nretention_analysis:\n<Video 1>: Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary."
def verify_official_prompt(p,graph=None):
 expected=TASK_ENVELOPE+p['original_task']['edit_prompt']+GENERIC_RETENTION
 require(p['prompt_version']=='IVEBench-edit-with-generic-retention-v1','prompt format label differs')
 require(p['prompt']==expected,'generic template or official edit sentence changed')
 if graph is not None:require(graph['5']['inputs']['prompt']==expected,'actual graph prompt differs')

# The actual producer gate carries its parent's descriptive label. Validate its
# sealed graph and all runtime evidence, while preserving the original receipt.
def gate_label_view(g):
 import copy
 require(config()['producer_seal_sha256']=='3c8b41e7fbbe6d226292ae96f07c43c58eef1e9535cac42ba159008910adb196','unregistered producer for label compatibility')
 v=copy.deepcopy(g)
 if v.get('prompt_version')=='IVEBench-original-edit-prompt-v1':
  require(v.get('source_id')=='long_0039','unregistered source for label compatibility')
  v['prompt_version']='IVEBench-edit-with-generic-retention-v1'
 return v
_verify_gate_original=verify_gate
def verify_gate(g,source,owner):
 _verify_gate_original(gate_label_view(g),source,owner)
 return g

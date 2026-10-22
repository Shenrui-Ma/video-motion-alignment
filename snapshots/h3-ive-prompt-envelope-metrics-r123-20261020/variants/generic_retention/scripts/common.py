"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/common.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='bad6f9addae1e7fb64b9f555b130eb1a8d64359a081e20bf3b3ae74b7abaf631'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

GENERIC_RETENTION = "\n\nretention_analysis:\n<Video 1>: Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary."
def verify_official_prompt(p,graph=None):
 expected=TASK_ENVELOPE+p['original_task']['edit_prompt']+GENERIC_RETENTION
 require(p['prompt_version']=='official_edit_prompt_with_task_reference_and_generic_retention','prompt format label differs')
 require(p['prompt']==expected,'task envelope, official edit sentence or generic retention changed')
 if graph is not None:require(graph['5']['inputs']['prompt']==expected,'actual graph prompt differs')

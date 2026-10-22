"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/common.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == 'bad6f9addae1e7fb64b9f555b130eb1a8d64359a081e20bf3b3ae74b7abaf631'
exec(compile(_data, str(_shared), "exec"), globals())

SOURCES = ('short_0252',)
GENERIC_RETENTION = "\n\nretention_analysis:\n<Video 1>: Preserve the source video's people, scene, framing, camera motion, and actions, except for changes explicitly requested in the summary."
def verify_official_prompt(p, graph=None):
    expected = TASK_ENVELOPE + p['original_task']['edit_prompt'] + GENERIC_RETENTION
    require(p['prompt_version'] == 'official_edit_prompt_with_task_reference_and_generic_retention', 'prompt version differs')
    require(p['prompt'] == expected, 'official instruction or generic envelope changed')
    if graph is not None:
        require(graph['5']['inputs']['prompt'] == expected, 'actual graph prompt differs')
REQUIRED_CHECKS = tuple('native_registered_initial_noise_equal' if k == 'native_r121_initial_noise_equal' else k for k in REQUIRED_CHECKS)

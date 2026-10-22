"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/paired.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == 'c903ddf46516cb19e55c1b071725f901ae6960d8ed96ab497fb0638e8f735153'
exec(compile(_data, str(_shared), "exec"), globals())

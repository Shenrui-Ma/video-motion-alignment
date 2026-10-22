"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/paired.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='c903ddf46516cb19e55c1b071725f901ae6960d8ed96ab497fb0638e8f735153'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/render_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='22837fc3db5ecd9e0a2019279cfc7184a2790b31743e93b0aff7d6eb85b11c8a'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/review.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='903697f720e57b02bb3474a3c2672a0cb855f797bc8a8015ed42f36578067f3e'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/consume_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='7ca258fa2acd71b29484941c777093c3a6b247bdf7e8eb6d94e203ee61151619'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

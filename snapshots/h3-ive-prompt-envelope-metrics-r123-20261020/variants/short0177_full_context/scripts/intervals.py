"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/intervals.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='7a637028002647132a4f0b80094faa3f1c3e4cc47023b5c13fbd21f8c12a6a4b'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

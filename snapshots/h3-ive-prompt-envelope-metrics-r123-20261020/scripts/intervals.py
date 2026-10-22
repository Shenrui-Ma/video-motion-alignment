"""Reuse the pinned R121 helper within this variant module namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-official-positive-recheck-metrics-r121-20261020/scripts/intervals.py')
_shared_bytes = _shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest() == 'c86ca4b43b3d7cfab58c7959f7b1601991e986b13ac4bff529bf274c0946bcef'
exec(compile(_shared_bytes, str(_shared), "exec"), globals())

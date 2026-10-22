"""Reuse the pinned R121 helper within this variant module namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-official-positive-recheck-metrics-r121-20261020/scripts/full_frame_review.py')
_shared_bytes = _shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest() == '205c40f1d10a1227e3664f917c3ef6ed500c64cbc07c6792509ccb87d2d99fbf'
exec(compile(_shared_bytes, str(_shared), "exec"), globals())

"""Reuse the pinned R121 helper within this variant module namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-official-positive-recheck-metrics-r121-20261020/scripts/remote.py')
_shared_bytes = _shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest() == '7c40b6343be106db6b245511d1d9fc59b1c55a934907d6cef23ceda2f7f28c7c'
exec(compile(_shared_bytes, str(_shared), "exec"), globals())

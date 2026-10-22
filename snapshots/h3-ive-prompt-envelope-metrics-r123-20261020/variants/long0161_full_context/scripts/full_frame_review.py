"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/full_frame_review.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='8d5f9f8d592772accfc22f3594cfe4a2c08b1abf2ed9d864fba9a99d8a66094e'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

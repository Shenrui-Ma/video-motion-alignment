"""Reuse the verified R120 consumer in the R128 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/full_frame_review.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='205c40f1d10a1227e3664f917c3ef6ed500c64cbc07c6792509ccb87d2d99fbf'
_code=_shared_bytes.decode().replace('r120','r128').replace('R120','R128')
exec(compile(_code,str(_shared),'exec'),globals())

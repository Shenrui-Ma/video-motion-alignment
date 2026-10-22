"""Reuse the verified R120 consumer in the R126 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/intervals.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='c86ca4b43b3d7cfab58c7959f7b1601991e986b13ac4bff529bf274c0946bcef'
_code=_shared_bytes.decode().replace('r120','r126').replace('R120','R126')
exec(compile(_code,str(_shared),'exec'),globals())

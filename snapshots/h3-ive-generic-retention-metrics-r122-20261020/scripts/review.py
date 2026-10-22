"""Reuse SHA-bound R120 consumer helpers for one R122 source."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/review.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='aa7138ce488d3ba34de5c3cc14aac14570517e25e175357bded1cc726b8fab83'
_code=_shared_bytes.decode().replace('r120','r122').replace('R120','R122')
exec(compile(_code,str(_shared),'exec'),globals())

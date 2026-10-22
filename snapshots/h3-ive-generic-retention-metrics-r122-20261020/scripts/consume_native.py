"""Reuse SHA-bound R120 consumer helpers for one R122 source."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/consume_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='c9f0c5397d12aea02ddde1b01ecc31b626f987b059c43e56f012dd531b85bdf4'
_code=_shared_bytes.decode().replace('r120','r122').replace('R120','R122')
exec(compile(_code,str(_shared),'exec'),globals())

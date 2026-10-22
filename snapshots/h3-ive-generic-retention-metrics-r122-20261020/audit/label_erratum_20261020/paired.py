"""Reuse SHA-bound R120 consumer helpers for one R122 source."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/paired.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='4d3e48ef4c94c0c479791b19c1143414a9bfd3c44e48458917f22f933fdac021'
_code=_shared_bytes.decode().replace('r120','r122').replace('R120','R122')
exec(compile(_code,str(_shared),'exec'),globals())

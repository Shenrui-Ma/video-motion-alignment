"""Reuse the verified R120 consumer in the R126 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/collect_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='89bce5185f5627f9902d00276b9fec61bdab99ab2f9ce1e372d48113eeee9082'
_code=_shared_bytes.decode().replace('r120','r126').replace('R120','R126')
exec(compile(_code,str(_shared),'exec'),globals())

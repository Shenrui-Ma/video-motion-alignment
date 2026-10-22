"""Reuse the verified R120 consumer in the R128 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/bind_execution.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='ec25ec5ebdc7e54151f8a75017bfcdb1215b1e681feb48279c7fc9471ccc70f1'
_code=_shared_bytes.decode().replace('r120','r128').replace('R120','R128')
exec(compile(_code,str(_shared),'exec'),globals())

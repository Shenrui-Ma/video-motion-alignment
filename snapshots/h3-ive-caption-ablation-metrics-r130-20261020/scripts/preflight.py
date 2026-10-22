"""Reuse the verified R120 consumer in the R130 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/preflight.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='41b385a2b0960be28b495bcb6c964d0318f62a456ed709d63751b3ab3565f1c4'
_code=_shared_bytes.decode().replace('r120','r130').replace('R120','R130')
assert _code.count("len(science['cases'])==6")==1
_code=_code.replace("len(science['cases'])==6","len(science['cases'])==2")
exec(compile(_code,str(_shared),'exec'),globals())

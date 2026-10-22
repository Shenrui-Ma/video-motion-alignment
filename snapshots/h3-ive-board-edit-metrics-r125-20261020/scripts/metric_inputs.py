"""Reuse the verified R120 consumer in the R125 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/metric_inputs.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='ad7619d9046b1ccdae6e26c4e938401e595687e7a62854c9ed0562ba0e3b0628'
_code=_shared_bytes.decode().replace('r120','r125').replace('R120','R125')
exec(compile(_code,str(_shared),'exec'),globals())

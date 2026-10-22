"""Reuse the verified R120 consumer in the R124 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/remote.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='b453b7ba7b172806ce3fd8202f40bb42aaec2c34eb013d57eff325239eae7cbf'
_code=_shared_bytes.decode().replace('r120','r124').replace('R120','R124')
exec(compile(_code,str(_shared),'exec'),globals())

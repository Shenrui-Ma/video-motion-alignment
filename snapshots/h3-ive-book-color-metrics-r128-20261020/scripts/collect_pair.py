"""Reuse the verified R120 consumer in the R128 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/collect_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='312f429482e6e8a38763768c7cdf7e4800292ab6cb7b77feaaab7fcbe4c3abd5'
_code=_shared_bytes.decode().replace('r120','r128').replace('R120','R128')
exec(compile(_code,str(_shared),'exec'),globals())

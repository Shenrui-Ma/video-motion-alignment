"""Reuse the verified R120 consumer in the R124 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/consume_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='70b03b2fec8692b660cd4c124865486ea673f7c303739f38ff4016ee085a912f'
_code=_shared_bytes.decode().replace('r120','r124').replace('R120','R124')
exec(compile(_code,str(_shared),'exec'),globals())

"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/preflight.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '105a10f993f299a8595ab2c1122dd0a1d313531e35b07dcc7b597bd40064da1d'
exec(compile(_data, str(_shared), "exec"), globals())

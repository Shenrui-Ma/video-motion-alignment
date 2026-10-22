"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/remote.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '6f047cb96df14637b8fa061aaf75e8c5ab939b425bfdf6caaf00659e8334c62e'
exec(compile(_data, str(_shared), "exec"), globals())

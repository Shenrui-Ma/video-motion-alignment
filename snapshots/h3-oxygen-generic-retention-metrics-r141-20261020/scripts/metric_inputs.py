"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/metric_inputs.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '24d443005ffa613e4e420e8e56196af22da0174e0253f82d19e4b28e80dda579'
exec(compile(_data, str(_shared), "exec"), globals())

"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/bind_execution.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == 'e81450b06f3480d1bde357ab1ab335d881127f31a7566e6f75d5b166efb4945e'
exec(compile(_data, str(_shared), "exec"), globals())

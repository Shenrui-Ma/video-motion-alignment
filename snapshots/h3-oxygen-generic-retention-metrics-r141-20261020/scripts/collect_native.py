"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/collect_native.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == 'ccab78f079400c31ab58813ccdbf0f3646b1ee25ebb90dc3c4ef32c0a5b329dc'
exec(compile(_data, str(_shared), "exec"), globals())

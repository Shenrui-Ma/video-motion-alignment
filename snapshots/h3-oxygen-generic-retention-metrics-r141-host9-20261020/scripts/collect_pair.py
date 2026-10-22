"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/collect_pair.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '185807c253d2ff9d21bcdcee747ec06147f1de7164b7a4aa6e2ff0b572cbaf7a'
exec(compile(_data, str(_shared), "exec"), globals())

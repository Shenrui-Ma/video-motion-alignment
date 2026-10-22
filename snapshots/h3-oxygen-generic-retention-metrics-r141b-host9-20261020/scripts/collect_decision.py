"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/collect_decision.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '3edc410aea681369e84bfe8566ce04af9036deca2f45c68629a38ab1ef5ebb21'
exec(compile(_data, str(_shared), "exec"), globals())

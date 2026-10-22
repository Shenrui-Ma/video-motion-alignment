"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/collect_decision.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='3edc410aea681369e84bfe8566ce04af9036deca2f45c68629a38ab1ef5ebb21'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

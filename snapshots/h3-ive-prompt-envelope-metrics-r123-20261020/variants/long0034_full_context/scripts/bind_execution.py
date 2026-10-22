"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/bind_execution.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='e81450b06f3480d1bde357ab1ab335d881127f31a7566e6f75d5b166efb4945e'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

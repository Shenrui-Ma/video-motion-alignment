"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/remote.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='6f047cb96df14637b8fa061aaf75e8c5ab939b425bfdf6caaf00659e8334c62e'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

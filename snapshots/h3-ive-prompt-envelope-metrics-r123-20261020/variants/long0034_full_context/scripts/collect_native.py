"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/collect_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='ccab78f079400c31ab58813ccdbf0f3646b1ee25ebb90dc3c4ef32c0a5b329dc'
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

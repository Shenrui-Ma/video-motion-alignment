"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/consume_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='33011158bfb2178dc37cc271359aeee59bfff35bc3d5ab1665f02a5c0ab2c76c'
import sys as _sys
if __name__=='__main__' and '--output' not in _sys.argv:
 _sys.argv += ['--output','/Users/researcher/Downloads/H3_R123_鸟类替换完整官方格式_20261020.html']
exec(compile(_shared_bytes,str(_shared),'exec'),globals())

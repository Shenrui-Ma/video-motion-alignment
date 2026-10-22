"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/consume_native.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '33011158bfb2178dc37cc271359aeee59bfff35bc3d5ab1665f02a5c0ab2c76c'
import sys as _sys
if __name__ == "__main__" and "--output" not in _sys.argv:
 _sys.argv += ["--output", '/Users/researcher/DevProjects/h3-oxygen-generic-retention-metrics-r141-20261020/showcase/consume_native.html']
exec(compile(_data, str(_shared), "exec"), globals())

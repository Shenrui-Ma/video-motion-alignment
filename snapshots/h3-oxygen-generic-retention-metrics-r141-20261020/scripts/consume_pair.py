"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/consume_pair.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '7ca258fa2acd71b29484941c777093c3a6b247bdf7e8eb6d94e203ee61151619'
import sys as _sys
if __name__ == "__main__" and "--output" not in _sys.argv:
 _sys.argv += ["--output", '/Users/researcher/DevProjects/h3-oxygen-generic-retention-metrics-r141-20261020/showcase/consume_pair.html']
exec(compile(_data, str(_shared), "exec"), globals())

"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/full_frame_review.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '8d5f9f8d592772accfc22f3594cfe4a2c08b1abf2ed9d864fba9a99d8a66094e'
exec(compile(_data, str(_shared), "exec"), globals())

"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/metric_inputs.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='24d443005ffa613e4e420e8e56196af22da0174e0253f82d19e4b28e80dda579'
from fractions import Fraction as _Fraction
import math as _math
def _source_pts(provenance):
    if 'original_pts' in provenance:
        values = provenance['original_pts']
    else:
        values = [float(_Fraction(x)) for x in provenance['original_pts_rational']]
    assert values and all(_math.isfinite(x) for x in values)
    assert all(a < b for a,b in zip(values,values[1:]))
    if 'original_pts_rational' in provenance:
        assert values == [float(_Fraction(x)) for x in provenance['original_pts_rational']]
    return values
_code=_shared_bytes.decode()
assert _code.count("provenance['original_pts']")==1
_code=_code.replace("provenance['original_pts']","_source_pts(provenance)")
exec(compile(_code,str(_shared),'exec'),globals())


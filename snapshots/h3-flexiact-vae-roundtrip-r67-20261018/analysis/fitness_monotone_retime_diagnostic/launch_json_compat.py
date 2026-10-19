"""Preserve frozen numeric implementation; serialize NumPy boolean mask values."""
import json
import numpy as np
from run import main

original = json.JSONEncoder.default


def scalar(self, value):
    if isinstance(value, np.bool_):
        return bool(value)
    return original(self, value)


if __name__ == '__main__':
    json.JSONEncoder.default = scalar
    assert json.dumps({'valid': np.bool_(True)}) == '{"valid": true}'
    main()

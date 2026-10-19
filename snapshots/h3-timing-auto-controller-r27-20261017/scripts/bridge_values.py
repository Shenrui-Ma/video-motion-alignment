"""Exact comparison domains. Explicit path/time exclusions only, no tolerance."""
import copy,hashlib,json

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def pose_values(value):
    out=copy.deepcopy(value);out['video'].pop('path')
    for key in ('detector_s','pose_s','elapsed_s'):out['statistics'].pop(key)
    return out

def scan_values(value):
    out=copy.deepcopy(value)
    for key in ('scan_seconds','edited_pose_sha256'):out.pop(key)
    return out

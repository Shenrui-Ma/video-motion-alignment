"""Preflight hashes before array decoding; model adapter remains unavailable."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import zipfile
import numpy as np


class PendingRuntime(RuntimeError):
    pass


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify_sources(paths,expected):
    if set(paths)!=set(expected) or not paths:
        raise ValueError('source roles missing or changed')
    for role in sorted(expected):
        if not isinstance(expected[role],str) or re.fullmatch('[0-9a-f]{64}',expected[role]) is None:
            raise ValueError('invalid expected source SHA')
        if sha256(paths[role])!=expected[role]:
            raise ValueError('source SHA mismatch: '+role)
    return dict(expected)


def verified_npz(paths,expected,whitelist):
    """All sources pass before any NPZ decoding. No files are written here."""
    verify_sources(paths,expected)
    if set(whitelist)!=set(paths):raise ValueError('member contract missing')
    result={}
    for role in sorted(paths):
        keys=whitelist[role]
        if not isinstance(keys,(list,tuple)) or not keys or len(keys)!=len(set(keys)):
            raise ValueError('invalid member whitelist')
        with zipfile.ZipFile(paths[role]) as z:
            if len(z.namelist())!=len(set(z.namelist())):raise ValueError('duplicate member')
        with np.load(paths[role],allow_pickle=False) as data:
            if set(data.files)!=set(keys):raise ValueError('unexpected or missing NPZ member')
            result[role]={key:np.array(data[key],copy=True) for key in keys}
    return result


def request_model_forward(*args,**kwargs):
    """Intentional hard boundary: no adapter/model loading or GPU side effects."""
    raise PendingRuntime('CPU-only package: exact original condition-noise recovery, same-environment single-forward adapter, new full raw-AV/QK zero gates and root GPU release remain pending. Old REPLAY_GATE=false cannot satisfy these gates.')


def verify_original_native_states(paths,policy):
    """Check the four already-captured original file identities, without decoding PT."""
    expected={}
    for capture in policy['original_native_metadata']:
        step=capture['step_zero_based']
        expected[f'step{step:03d}_state']=capture['state_file_sha256']
        expected[f'step{step:03d}_qk']=capture['qk_sha256']
    return verify_sources(paths,expected)

"""Stdlib-only pre-CUDA rendezvous, bound to exact process identities.

The bootstrap calls this before importing torch, PyAV, kitchen, or Comfy.
No bypass flag/environment variable exists. Tests inject a process reader.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

PRIMARY = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
RUN = Path(str(PRIMARY) + '_semantic0')
GPU = 'GPU-REDACTED'
PORT = 8462


def process_identity(pid):
    proc = Path('/proc') / str(int(pid))
    try:
        stat = proc.joinpath('stat').read_text().split(') ', 1)[1].split()
        if stat[0] in ('Z', 'X'):
            return None
        return {'uid': proc.stat().st_uid,
                'start_ticks': stat[19],
                'cmdline_sha256': hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest()}
    except FileNotFoundError:
        return None


def atomic_bytes(path, data):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('Refusing symlink target: ' + str(path))
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temp.open('xb') as handle:
        os.chmod(temp, 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2) + '\n').encode())


def read_json(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_live(record, reader=process_identity):
    if not isinstance(record.get('pid'), int) or record['pid'] <= 0:
        raise RuntimeError('Invalid peer PID')
    identity = record.get('identity', {})
    if set(identity) != {'uid', 'start_ticks', 'cmdline_sha256'}:
        raise RuntimeError('Exact external identity required')
    if identity['uid'] != os.getuid() or reader(record['pid']) != identity:
        raise RuntimeError('Peer missing/restarted/changed identity')


def validate_gate(root, *, reader=process_identity):
    root = Path(root)
    gate = read_json(root / 'processes/pre_cuda_gate.json')
    if gate.get('schema') != 1 or re.fullmatch('[a-f0-9]{32}', gate.get('launch_id', '')) is None:
        raise RuntimeError('Invalid launch gate')
    if gate.get('root') != str(root) or gate.get('gpu_uuid') != GPU or gate.get('port') != PORT:
        raise RuntimeError('Launch gate instance/GPU/port mismatch')
    now = time.time()
    if not (gate['created_unix'] <= now <= gate['expires_unix'] <= gate['created_unix'] + 180):
        raise RuntimeError('Launch gate is stale or invalid')
    verify_live(gate['coordinator'], reader)
    verify_live(gate['primary'], reader)
    return gate


def paths(root, launch_id):
    base = Path(root) / 'processes'
    return (base / f'pre_cuda_ready_{launch_id}.json',
            base / f'pre_cuda_release_{launch_id}.json')


def require_admitted(path, peer):
    admission = read_json(path)
    if admission.get('scope') != 'own_user_video_jobs' or admission.get('existing_comfy_port') is not None:
        raise RuntimeError('Unexpected admission policy; explicit review required')
    rows = admission.get('permitted_compute_processes', [])
    matches = [row for row in rows if row.get('pid') == peer['pid']]
    if matches != [peer]:
        raise RuntimeError('Peer is not admitted by exact PID and identity')


def validate_release(root, gate, ready, release, *, reader=process_identity):
    for name in ('schema', 'launch_id', 'root', 'gpu_uuid', 'port', 'pid', 'identity'):
        if release.get(name) != ready.get(name):
            raise RuntimeError('Stale/mismatched release field: ' + name)
    if not (time.time() <= release.get('expires_unix', 0) <= gate['expires_unix']):
        raise RuntimeError('Release expired or exceeds gate')
    if release.get('primary') != gate['primary'] or release.get('coordinator') != gate['coordinator']:
        raise RuntimeError('Release peer/coordinator mismatch')
    verify_live({'pid': ready['pid'], 'identity': ready['identity']}, reader)
    verify_live(gate['primary'], reader)
    verify_live(gate['coordinator'], reader)
    own_admission = Path(root) / 'configs/admission.json'
    primary_admission = Path(gate['primary_root']) / 'configs/admission.json'
    for label, path in [('transfer', own_admission), ('primary', primary_admission)]:
        if sha256(path) != release.get(label + '_admission_sha256'):
            raise RuntimeError(label + ' admission changed before release')
    require_admitted(own_admission, gate['primary'])
    require_admitted(primary_admission, {'pid': ready['pid'], 'identity': ready['identity']})


def wait_for_release(root, *, reader=process_identity, poll_seconds=0.1):
    root = Path(root)
    gate = validate_gate(root, reader=reader)
    # Runtime has no option to change the pinned remote paths or GPU.
    if reader is process_identity and (root.resolve() != RUN or Path(gate['primary_root']) != PRIMARY):
        raise RuntimeError('Unexpected deployment root')
    if os.environ.get('CUDA_VISIBLE_DEVICES') != GPU:
        raise RuntimeError('CUDA UUID does not match gate')
    ready = {key: gate[key] for key in ('schema', 'launch_id', 'root', 'gpu_uuid', 'port')}
    ready.update(pid=os.getpid(), identity=reader(os.getpid()), ready_unix=time.time())
    verify_live({'pid': ready['pid'], 'identity': ready['identity']}, reader)
    ready_path, release_path = paths(root, gate['launch_id'])
    if ready_path.exists():
        raise RuntimeError('Ready record already exists; never reuse a launch token')
    atomic_json(ready_path, ready)
    deadline = time.monotonic() + max(0, gate['expires_unix'] - time.time())
    while time.monotonic() < deadline:
        verify_live(gate['coordinator'], reader)
        verify_live(gate['primary'], reader)
        if release_path.exists():
            release = read_json(release_path)
            validate_release(root, gate, ready, release, reader=reader)
            atomic_json(root / 'processes' / f'pre_cuda_passed_{gate["launch_id"]}.json',
                        dict(ready, passed_unix=time.time(), release=release))
            return
        time.sleep(poll_seconds)
    raise TimeoutError('Pre-CUDA gate timed out; torch was not imported')

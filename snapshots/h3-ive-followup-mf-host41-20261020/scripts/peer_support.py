from pathlib import Path
import os
from common import read,save
def peers(paths, identity):
    result = []
    allowed = {Path('/data4/researcher/h3_runs')}
    for text in paths:
        root = Path(text).resolve()
        assert root.parent in allowed, 'peer root outside managed runs'
        record = root / 'processes/service.json'
        if not record.exists():
            continue
        owner = read(record); row = identity.snapshot(owner['pid'])
        if row is None:
            assert not Path('/proc', str(owner['pid'])).exists(), 'peer identity unavailable'
            continue
        actual = identity.service_record(row); runtime = read(root / 'configs/runtime.json')
        assert actual == owner['identity'] and actual['uid'] == os.getuid() == 1004
        assert runtime['uid'] == 1004 and Path(runtime['remote_root']).resolve() == root
        assert owner['gpu_uuid'] == runtime['gpu_uuid'] and owner['port'] == runtime['port']
        assert str(root / 'scripts/service_entry.py') in actual['cmdline']
        result.append({'root': str(root), 'owner': owner, 'identity': identity.hashed_record(row)})
    assert len({p['owner']['pid'] for p in result}) == len(result), 'duplicate peer'
    return result

def update_peer(peer, entry, identity, remove=False):
    owner = peer['owner']; actual = identity.snapshot(owner['pid'])
    if actual is None:
        assert not Path('/proc', str(owner['pid'])).exists(), 'peer identity disappeared'
        return
    assert identity.service_record(actual) == owner['identity'], 'peer generation changed'
    path = Path(peer['root']) / 'configs/admission.json'; value = read(path)
    assert value['scope'] == 'own_user_video_jobs'
    rows = value['permitted_compute_processes']
    if remove:
        rows[:] = [row for row in rows if row != entry]
    elif entry not in rows:
        assert all(row['pid'] != entry['pid'] for row in rows), 'peer has reused PID entry'
        rows.append(entry)
    save(path, value)

def owned_check(snapshot, known, identity, gpu, child=None):
    expected = {p['owner']['pid']: (p['identity'], p['owner']['gpu_uuid']) for p in known}
    if child:
        expected[child['pid']] = (child['identity'], gpu)
    devices = {gpu} | {p['owner']['gpu_uuid'] for p in known}
    for row in snapshot['processes']:
        if row['uid'] != os.getuid():
            continue
        assert row['pid'] in expected, 'unregistered own CUDA process'
        expected_identity, expected_gpu = expected[row['pid']]
        assert identity.hashed_record(identity.snapshot(row['pid'])) == expected_identity
        assert row['gpu_uuid'] == expected_gpu
        devices.add(row['gpu_uuid'])
    assert len(devices) <= 2, 'would exceed two own GPUs'
    assert all(p['owner']['gpu_uuid'] != gpu for p in known), 'selected GPU still reserved by own peer'
    return {'owned_devices': sorted(devices), 'peers': known}

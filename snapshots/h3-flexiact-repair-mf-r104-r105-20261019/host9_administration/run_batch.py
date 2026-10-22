"""Serial official Flex MF on an explicitly assigned .9 GPU, with exact peer admission."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import capacity_v1
from admin_common import ROOT, load, read, save, sha, verify


def peers(paths, identity):
    result = []
    allowed = {Path('/home/researcher/h3_runs'), Path('/data5/researcher/h3_runs')}
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
        assert actual == owner['identity'] and actual['uid'] == os.getuid() == 1016
        assert runtime['uid'] == 1016 and Path(runtime['remote_root']).resolve() == root
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


def cuda_pids():
    text = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
                                    '--format=csv,noheader,nounits'], text=True, timeout=10)
    return {int(line.strip()) for line in text.splitlines() if line.strip()}


def cleanup(child, bound, known, identity):
    if child.poll() is None:
        assert identity.hashed_record(identity.snapshot(child.pid)) == bound['identity'], 'child identity changed'
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            assert identity.hashed_record(identity.snapshot(child.pid)) == bound['identity']
            child.kill(); child.wait(timeout=10)
    else:
        child.wait()
    deadline = time.monotonic() + 30
    while child.pid in cuda_pids():
        assert time.monotonic() < deadline, 'own CUDA tail still live'
        time.sleep(.5)
    assert not Path('/proc', str(child.pid)).exists()
    for peer in known:
        update_peer(peer, bound, identity, remove=True)
    return {'passed': True, 'pid': child.pid, 'identity': bound['identity'],
            'returncode': child.returncode, 'process_absent': True, 'own_cuda_absent': True,
            'peer_registrations_removed': True, 'unix': time.time()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True); parser.add_argument('--gpu-uuid', required=True)
    parser.add_argument('--attempt', required=True); parser.add_argument('--review', required=True)
    parser.add_argument('--peer-root', action='append', default=[])
    args = parser.parse_args()
    assert os.getuid() == 1016
    assert args.attempt.replace('_', '').replace('-', '').isalnum(), 'invalid attempt name'
    package = verify(args.package); review = read(args.review)
    assert review['passed'] and review['GPU_execution_authorized']
    assert review['administrative_seal_sha256'] == sha(ROOT / 'ADMIN_FREEZE.json')
    assert review['gpu_uuid'] == args.gpu_uuid and args.gpu_uuid.startswith('GPU-')
    assert review['package_seals'][str(package)] == sha(package / 'CONSUMER_FREEZE.json')
    assert sorted(review['peer_roots']) == sorted(args.peer_root)
    sys.path.insert(0, str(package / 'scripts')); sys.modules['mf_capacity'] = capacity_v1
    identity = load('host9_process_identity', package / 'scripts/process_identity.py')
    resources = load('host9_resources', package / 'scripts/track_shared.py')
    plan = load('host9_tracking_plan', package / 'scripts/tracking_plan.py')
    runtime = read(package / 'configs/RUNTIME.json'); python = runtime['python']; gpu = args.gpu_uuid
    assert runtime['uid'] == 1016 and runtime['remote_root'] == str(package)
    audit = package / 'audit' / args.attempt; audit.mkdir(parents=True, exist_ok=False)
    save(audit / 'STARTED.json', {'pid': os.getpid(), 'identity': identity.hashed_record(identity.snapshot(os.getpid())),
         'review_file': args.review, 'review_sha256': sha(args.review), 'gpu_uuid': gpu, 'unix': time.time()})
    baseline = capacity_v1.snapshot(); save(audit / 'OOM_BASE.json', baseline)
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu
    def signal_stop(number, _frame):
        raise KeyboardInterrupt('signal ' + str(number))
    signal.signal(signal.SIGTERM, signal_stop)
    for method in ('reference', 'native', 'guided'):
        out = audit / method; out.mkdir()
        current = capacity_v1.snapshot(); delta = capacity_v1.oom_delta(baseline, current)
        assert delta['passed'], 'new OOM or allocation-limit failure'
        known = peers(args.peer_root, identity); memory = capacity_v1.assess(current, 12)
        hardware = resources.resource_check(gpu)
        owned_check(hardware, known, identity, gpu)
        save(out / 'PREFLIGHT.json', {'memory': memory, 'gpu': hardware, 'peers': known, 'oom_delta': delta})
        original = plan.command(method, gpu, python)
        index = original.index(python); env = dict(os.environ)
        for item in original[1:index]:
            key, value = item.split('=', 1); env[key] = value
        argv = [python, str(ROOT / 'track_entry.py'), '--package', str(package)] + original[index + 2:]
        control = Path(argv[argv.index('--control') + 1]); output = Path(argv[argv.index('--output') + 1])
        ready = None; bound = None; child = None; samples = []; error = None
        try:
            with (out / 'tracker.log').open('xb') as log:
                child = subprocess.Popen(argv, cwd=package, env=env, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, start_new_session=True)
            row = identity.bind_or_reap(child, argv)
            bound = {'pid': child.pid, 'identity': identity.hashed_record(row)}
            save(out / 'LAUNCHED.json', {'argv': argv, **bound})
            deadline = time.monotonic() + 180
            while not (control / 'ready.json').exists():
                assert child.poll() is None and time.monotonic() < deadline, 'ready timeout/exit'
                time.sleep(.2)
            ready = read(control / 'ready.json')
            assert ready['pid'] == child.pid and ready['identity'] == bound['identity']
            assert ready['CUDA_started'] is False and ready['gpu_uuid'] == gpu
            assert ready['consumer_freeze_sha256'] == sha(package / 'CONSUMER_FREEZE.json')
            assert ready['wrapper_sha256'] == sha(package / 'scripts/track_shared.py')
            assert sha(ready['input_manifest']['file']) == ready['input_manifest']['sha256']
            assert peers(args.peer_root, identity) == known, 'peers changed before GO'
            for peer in known:
                update_peer(peer, bound, identity)
            current = capacity_v1.snapshot(); delta = capacity_v1.oom_delta(baseline, current)
            assert delta['passed']
            hardware = resources.resource_check(gpu); owned_check(hardware, known, identity, gpu, bound)
            save(out / 'CAPACITY_AT_GO.json', {'memory': capacity_v1.assess(current, 12), 'gpu': hardware, 'oom_delta': delta})
            save(control / 'go.json', ready); save(out / 'GO.json', ready)
            print('GO ' + method, flush=True); deadline = time.monotonic() + 600
            while child.poll() is None:
                assert time.monotonic() < deadline, 'tracker deadline'
                state = capacity_v1.snapshot(); delta = capacity_v1.oom_delta(baseline, state)
                assert delta['passed'], 'new OOM during tracker'
                capacity_v1.assess(state, 8)
                status = Path('/proc', str(child.pid), 'status')
                item = {'capacity': state, 'unix': time.time()}
                try:
                    item['process_memory'] = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
                       for line in status.read_text().splitlines() if line.startswith(('VmRSS:', 'VmHWM:', 'RssAnon:', 'RssFile:'))}
                except FileNotFoundError:
                    item['process_exited_during_status_read'] = True
                samples.append(item); time.sleep(.25)
            child.wait(); assert child.returncode == 0, 'tracker failed'
            report = read(output / 'REPORT.json')
            assert report['passed'] and report['pid'] == child.pid
            assert report['tracks_shape'] == [3025, 49, 2] and report['nonfinite_track_values'] == 0
            assert report['tracks_sha256'] == sha(output / 'tracks.pt')
        except BaseException as exc:
            error = exc; save(out / 'ERROR.json', {'error': repr(exc), 'traceback': traceback.format_exc()})
        finally:
            # Exact child cleanup precedes optional telemetry writes.
            if bound is not None:
                released = cleanup(child, bound, known, identity); save(out / 'RELEASED.json', released)
            save(out / 'RESOURCE_OBSERVATIONS.json', {'samples': samples, 'final_snapshot': capacity_v1.snapshot()})
        if error is not None:
            raise error
        delta = capacity_v1.oom_delta(baseline, capacity_v1.snapshot()); save(out / 'OOM_DELTA.json', delta)
        assert delta['passed']
        save(out / 'COMPLETE.json', {'passed': True, 'report_sha256': sha(output / 'REPORT.json')})
        print('TRACK_COMPLETE ' + method, flush=True)
    for method in ('native', 'guided'):
        result = subprocess.run([python, str(package / 'scripts/score_one.py'), '--method', method],
             cwd=package, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1'),
             capture_output=True, text=True, timeout=600)
        (audit / (method + '_score.log')).write_text(result.stdout + '\n' + result.stderr)
        assert result.returncode == 0, 'CPU score failed'
    save(audit / 'COMPLETE.json', {'passed': True, 'all_trackers_released': True, 'gpu_uuid': gpu,
         'scores': {key: {'file': str(package / 'scores' / key / 'SCORE.json'),
                         'sha256': sha(package / 'scores' / key / 'SCORE.json')} for key in ('native', 'guided')},
         'scientific_package_seal_sha256': sha(package / 'CONSUMER_FREEZE.json'),
         'administrative_seal_sha256': sha(ROOT / 'ADMIN_FREEZE.json'), 'unix': time.time()})
    print('BATCH_COMPLETE', flush=True)


if __name__ == '__main__':
    main()

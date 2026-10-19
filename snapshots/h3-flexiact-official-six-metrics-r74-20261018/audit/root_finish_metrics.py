"""Root-owned administration after all R74 paired inference jobs finish."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data3/researcher/h3_runs/flexiact_official_six_metrics_r74_20261018')
PRODUCER = ROOT.parent / 'timing_flexiact_official_six_r74_20261018'
PEER_ROOTS = (
    ROOT.parent / 'timing_flexiact_prompt_pair_r72_20261018',
    ROOT.parent / 'timing_ivebench_body_r76_20261018',
)
GPU = 'GPU-REDACTED'
PYTHON = '/data3/researcher/ComfyUI/.venv/bin/python'
PAIRS = ['chest__game_man_5', 'chest__movie_man_7', 'crouch__movie_man_5',
         'crouch__movie_man_9', 'rotate__game_man_1', 'rotate__game_man_4']
sys.path.insert(0, str(PRODUCER / 'scripts'))
import service


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def live_peers():
    """Trust only current service records in the two explicit producer roots."""
    peers = []
    for root in PEER_ROOTS:
        path = root / 'processes/service.json'
        if not path.is_file():
            continue
        owner = read(path)
        pid = owner['pid']
        assert isinstance(pid, int) and pid > 0
        actual = service.current_identity(pid)
        if actual is None:
            assert not Path('/proc', str(pid)).exists(), 'Peer exists without a complete identity'
            continue
        runtime = read(root / 'configs/runtime.json')
        assert actual == owner['identity'], 'Recorded peer PID was reused or changed'
        assert actual['uid'] == os.getuid() == runtime['uid'], 'Peer owner differs'
        assert runtime['remote_root'] == str(root), 'Peer runtime root differs'
        assert owner['gpu_uuid'] == runtime['gpu_uuid'] and owner['port'] == runtime['port']
        assert str(root / 'scripts/service_entry.py') in actual['cmdline']
        assert str(Path(runtime['core']) / 'main.py') in actual['cmdline']
        identity = service.external_identity(pid)
        assert identity is not None
        assert identity['uid'] == actual['uid'] and identity['start_ticks'] == actual['start_ticks']
        assert service.current_identity(pid) == actual, 'Peer changed during identity binding'
        peers.append({'root': root, 'pid': pid, 'identity': identity,
                      'gpu_uuid': owner['gpu_uuid'], 'service_record_sha256': sha(path)})
    assert len({p['pid'] for p in peers}) == len(peers), 'One PID claimed by multiple producers'
    return peers


def check_owned_compute(peers, child_pid, child_identity):
    """Foreign users are allowed; every own CUDA process must be exactly bound."""
    expected = {p['pid']: (p['identity'], p['gpu_uuid']) for p in peers}
    assert child_pid not in expected
    expected[child_pid] = (child_identity, GPU)
    rows = service.compute_processes()
    owned = []
    for row in rows:
        pid = row['pid']
        uid = service.proc_uid(pid)
        if uid is None:
            assert not Path('/proc', str(pid)).exists(), 'CUDA process ownership unavailable'
            continue  # It exited after the nvidia-smi snapshot.
        if uid != os.getuid():
            continue
        assert pid in expected, f'Unregistered own CUDA process: {pid}'
        identity, gpu = expected[pid]
        assert service.external_identity(pid) == identity, f'Own CUDA identity changed: {pid}'
        assert row['gpu_uuid'] == gpu, f'Own CUDA device differs: {pid}'
        owned.append(row)
    # Count admitted live services too, even if a service has temporarily unloaded CUDA.
    devices = {GPU} | {p['gpu_uuid'] for p in peers} | {p['gpu_uuid'] for p in owned}
    assert len(devices) <= 2, 'Tracking and current peers would exceed two owned GPUs'
    return {'unix': time.time(), 'owned_compute': owned,
            'owned_gpu_uuids_including_reserved_services': sorted(devices),
            'peers': [{**p, 'root': str(p['root'])} for p in peers]}


def register(root, pid, identity, add):
    if root is None:
        return
    path = root / 'configs/admission.json'
    admission = read(path)
    assert admission.get('scope') == 'own_user_video_jobs', 'Peer admission scope differs'
    entries = admission['permitted_compute_processes']
    assert all(x['pid'] != pid or x['identity'] == identity for x in entries)
    admission['permitted_compute_processes'] = [x for x in entries if x['pid'] != pid]
    if add:
        admission['permitted_compute_processes'].append({'pid': pid, 'identity': identity})
    save(path, admission)


def wait_until_finished(audit):
    deadline = time.monotonic() + 12 * 3600
    while time.monotonic() < deadline:
        state_file = PRODUCER / 'logs/controller_state.json'
        if state_file.is_file():
            state = read(state_file)
            completed = len(state.get('completed', []))
            ready = all((ROOT / 'prepared' / key / 'READY.json').is_file() for key in PAIRS)
            save(audit / 'WAIT.json', {'unix': time.time(), 'completed_jobs': completed,
                                     'all_six_prepared': ready})
            if completed == 12 and ready:
                owner = read(PRODUCER / 'processes/service.json')
                assert owner['gpu_uuid'] == GPU and owner['port'] == 8542
                if not Path('/proc', str(owner['pid'])).exists():
                    assert owner['pid'] not in [x['pid'] for x in service.compute_processes()]
                    save(audit / 'INFERENCE_RELEASED.json', {'owner': owner, 'unix': time.time(),
                                                           'process_absent': True, 'CUDA_absent': True})
                    return
        time.sleep(20)
    raise TimeoutError('R74 all-pair completion/release not yet available')


def track(key, method, audit):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps')
    plan = json.loads(subprocess.run([PYTHON, 'scripts/tracking_plan.py', '--key', key,
                                      '--method', method, '--gpu-uuid', GPU],
                                     cwd=ROOT, env=env, check=True, capture_output=True, text=True).stdout)
    argv = plan['argv']
    control = Path(argv[argv.index('--control') + 1])
    output = Path(argv[argv.index('--output') + 1])
    assert control == ROOT / 'controls' / (method + '_' + key)
    assert output == ROOT / 'tracks' / method / key
    peers = []
    with (audit / f'{method}_{key}.log').open('xb') as log:
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True)
    identity = None
    try:
        deadline = time.monotonic() + 120
        while not (control / 'ready.json').is_file():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(.2)
        ready = read(control / 'ready.json')
        identity = service.external_identity(child.pid)
        assert ready['pid'] == child.pid and ready['identity'] == identity
        assert ready['CUDA_started'] is False and ready['gpu_uuid'] == GPU
        assert ready['consumer_freeze_sha256'] == sha(ROOT / 'CONSUMER_FREEZE.json')
        assert sha(Path(ready['input_manifest']['file'])) == ready['input_manifest']['sha256']
        peers = live_peers()
        admission = check_owned_compute(peers, child.pid, identity)
        for peer in peers:
            register(peer['root'], child.pid, identity, True)
        assert live_peers() == peers, 'Peer registry changed before tracker GO'
        admission['after_registration'] = check_owned_compute(peers, child.pid, identity)
        save(audit / f'{method}_{key}_ADMISSION.json', admission)
        save(control / 'go.json', ready)
        code = child.wait(timeout=1500)
        assert not Path('/proc', str(child.pid)).exists()
        assert child.pid not in [x['pid'] for x in service.compute_processes()]
        for peer in peers:
            register(peer['root'], child.pid, identity, False)
        assert code == 0, (key, method, code)
        report = read(output / 'REPORT.json')
        assert report['passed'] and report['pid'] == child.pid
        assert report['tracks_shape'] == [3025, 49, 2]
        assert report['nonfinite_track_values'] == 0
        assert sha(output / 'tracks.pt') == report['tracks_sha256']
        return {'key': key, 'method': method, 'pid': child.pid, 'exit_code': code,
                'process_absent': True, 'CUDA_absent': True,
                'wall_seconds': report['wall_seconds'], 'peak_reserved_bytes': report['peak_reserved_bytes']}
    except BaseException as error:
        save(audit / 'FAILURE.json', {'key': key, 'method': method, 'pid': child.pid,
                                    'identity': identity, 'error': repr(error), 'unix': time.time()})
        cleanup_errors = []
        try:
            if child.poll() is None:
                # Popen owns this unreaped child even if ready.json never appeared.
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=30)
            if identity is not None:
                assert child.pid not in [x['pid'] for x in service.compute_processes()]
                for peer in peers:
                    register(peer['root'], child.pid, identity, False)
        except BaseException as cleanup_error:
            cleanup_errors.append(repr(cleanup_error))
        save(audit / 'FAILURE_CLEANUP.json', {'pid': child.pid, 'exit_code': child.poll(),
                                           'errors': cleanup_errors, 'unix': time.time()})
        raise


def cpu_command(argv, env, audit, name):
    deadline = time.monotonic() + 2 * 3600
    attempt = 0
    while True:
        attempt += 1
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
        log = audit / f'{name}_attempt{attempt}.log'
        log.write_text(result.stdout + '\n' + result.stderr)
        if result.returncode == 0:
            return
        if ('BlockingIOError: [Errno 11]' in result.stderr and
                'flock' in result.stderr and time.monotonic() < deadline):
            time.sleep(10)
            continue
        raise RuntimeError(f'CPU command failed: {log}')


def main():
    audit = ROOT / 'audit/root_finish_metrics_attempt1'
    audit.mkdir(exist_ok=False)
    wait_until_finished(audit)
    records = []
    items = [(key, 'reference') for key in ('chest', 'crouch', 'rotate')]
    items += [(key, method) for key in PAIRS for method in ('native', 'forced')]
    for key, method in items:
        row = track(key, method, audit)
        records.append(row)
        save(audit / 'PROGRESS.json', {'tracks': records, 'unix': time.time()})
        print(json.dumps(row), flush=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
    for key in PAIRS:
        for method in ('native', 'forced'):
            cpu_command([PYTHON, 'scripts/score_one.py', '--pair', key, '--method', method],
                        env, audit, f'score_{key}_{method}')
    cpu_command([PYTHON, 'scripts/summarize.py', '--output', str(audit / 'MF_SUMMARY.json')],
                env, audit, 'summarize')
    save(audit / 'COMPLETE.json', {'passed': True, 'fresh_tracks': records, 'unix': time.time()})


if __name__ == '__main__':
    main()

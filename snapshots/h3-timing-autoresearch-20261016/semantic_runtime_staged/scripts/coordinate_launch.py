"""Explicit, host-local two-service admission handshake and lifecycle owner.

No SSH, copying models, automatic primary restart, or primary signals. Run only
after root has reviewed scientific admission and uploaded this complete bundle.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import launch_remote
import service
import startup_barrier as barrier
from primary_lifecycle import observe_primary

PRIMARY = barrier.PRIMARY
PRIMARY_GPU = 'GPU-REDACTED'
PRIMARY_PORT = 8460


def exact_primary(expected):
    barrier.verify_live(expected)
    registry = barrier.read_json(PRIMARY / 'processes/service.json')
    if registry.get('pid') != expected['pid']:
        raise RuntimeError('Primary registry now belongs to another PID')
    actual = service.current_identity(expected['pid'])
    if actual != registry['identity'] or actual['uid'] != os.getuid():
        raise RuntimeError('Primary registry identity mismatch')
    if registry.get('gpu_uuid') != PRIMARY_GPU or registry.get('port') != PRIMARY_PORT:
        raise RuntimeError('Primary GPU/port mismatch')
    cmd = actual['cmdline']
    if str(PRIMARY / 'scripts/compatibility_bootstrap.py') not in cmd or str(service.CORE / 'main.py') not in cmd:
        raise RuntimeError('Primary command does not match the reviewed service')
    queue = service.queue_at(PRIMARY_PORT)
    if not all(isinstance(queue.get(k), list) for k in ('queue_running', 'queue_pending')):
        raise RuntimeError('Invalid primary queue response')
    # Running primary work is expected and is never interrupted. This snapshot
    # is evidence only; the primary controller continues to own its queue.
    return {'primary': expected, 'registry': registry, 'queue': queue, 'observed_unix': time.time()}


def gpu_and_host_headroom():
    output = subprocess.run(
        ['nvidia-smi', '-i', service.GPU,
         '--query-gpu=uuid,name,memory.total,memory.used,memory.free,utilization.gpu',
         '--format=csv,noheader,nounits'], capture_output=True, text=True,
        check=True, timeout=20).stdout.strip()
    columns = [x.strip() for x in output.split(',')]
    if len(columns) != 6 or columns[0] != service.GPU:
        raise RuntimeError('Unexpected selected GPU report')
    total, used, free, util = map(int, columns[2:])
    processes = service.compute_processes()
    if any(row['gpu_uuid'] == service.GPU for row in processes):
        raise RuntimeError('Transfer GPU has an active compute process')
    if free < 40000 or used > 512 or util != 0:
        raise RuntimeError('Transfer GPU requires >=40000 MiB free, <=512 MiB used, and zero utilization')
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(memory['MemAvailable'].split()[0])
    if available < 40 * 1024 * 1024:
        raise RuntimeError('Parallel startup requires >=40 GiB available host RAM')
    return {'gpu_uuid': columns[0], 'gpu_name': columns[1], 'total_mib': total,
            'used_mib': used, 'free_mib': free, 'utilization_percent': util,
            'host_available_kib': available, 'compute_processes': processes,
            'observed_unix': time.time()}


def verify_bundle():
    manifest = barrier.read_json(service.RUN / 'audit/bundle_manifest.json')
    if manifest['remote_root'] != str(service.RUN) or manifest['gpu_uuid'] != service.GPU or manifest['port'] != service.PORT:
        raise RuntimeError('Bundle instance mismatch')
    for rel, expected in manifest['payload_sha256'].items():
        path = service.RUN / rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or not path.is_file() or path.is_symlink():
            raise RuntimeError('Unsafe/missing bundle payload: ' + rel)
        if barrier.sha256(path) != expected:
            raise RuntimeError('Bundle changed since review: ' + rel)
    expected_code = {k for k in manifest['payload_sha256'] if k.endswith('.py') and k.startswith(('scripts/', 'extensions/'))}
    actual_code = {str(p.relative_to(service.RUN)) for top in ('scripts', 'extensions')
                   for p in (service.RUN / top).rglob('*.py')}
    if expected_code != actual_code:
        raise RuntimeError('Unexpected or missing executable Python in bundle')
    return manifest


def add_exact_peer(old_bytes, peer):
    old = json.loads(old_bytes)
    if old.get('scope') != 'own_user_video_jobs' or old.get('existing_comfy_port') is not None:
        raise RuntimeError('Unreviewed primary admission semantics')
    rows = old['permitted_compute_processes']
    if any(row.get('pid') == peer['pid'] for row in rows):
        raise RuntimeError('New transfer PID already appears in primary admission')
    new = dict(old, permitted_compute_processes=rows + [peer])
    return (json.dumps(new, indent=2) + '\n').encode()


def compare_replace(path, expected, replacement):
    if Path(path).read_bytes() != expected:
        raise RuntimeError('Admission changed concurrently; refusing to overwrite')
    barrier.atomic_bytes(path, replacement)


def stop_process(record, child=None):
    """Signal only a task child with its exact recorded full /proc identity."""
    if child is not None and child.poll() is not None:
        return {'pid': record['pid'], 'already_exited': True, 'returncode': child.returncode}
    actual = service.current_identity(record['pid'])
    if actual is None:
        return {'pid': record['pid'], 'already_absent': True}
    if actual != record['identity'] or actual['uid'] != os.getuid() or str(service.RUN) not in actual['cmdline']:
        raise RuntimeError('Refusing to signal changed/unowned child PID')
    os.kill(record['pid'], signal.SIGTERM)
    if child is not None:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if service.current_identity(record['pid']) != record['identity']:
                raise RuntimeError('Child changed identity before forceful cleanup')
            os.kill(record['pid'], signal.SIGKILL)
            child.wait(timeout=10)
    elif not service.wait_absent(record['pid'], 10):
        if service.current_identity(record['pid']) != record['identity']:
            raise RuntimeError('Child changed identity before forceful cleanup')
        os.kill(record['pid'], signal.SIGKILL)
        if not service.wait_absent(record['pid'], 10):
            raise RuntimeError('Task child cleanup unverified')
    return {'pid': record['pid'], 'stopped': True}


def run(expected, decision_note):
    if service.RUN.resolve() != barrier.RUN or Path(__file__).resolve().parents[1] != service.RUN:
        raise RuntimeError('Run only from the pinned remote transfer directory')
    verify_bundle()
    for name in ('processes', 'logs'):
        (service.RUN / name).mkdir(exist_ok=True)
    launch_id = uuid.uuid4().hex
    journal_path = service.RUN / 'processes' / f'coordinator_{launch_id}.json'
    coordinator = {'pid': os.getpid(), 'identity': barrier.process_identity(os.getpid())}
    journal = {'schema': 1, 'launch_id': launch_id, 'coordinator': coordinator,
               'primary': expected, 'root': str(service.RUN), 'gpu_uuid': service.GPU,
               'port': service.PORT, 'decision_note': decision_note, 'started_unix': time.time(),
               'status': 'starting', 'children': [], 'cleanup': []}
    children = []
    owner = None
    old_admission = None
    installed_admission = None
    primary_path = PRIMARY / 'configs/admission.json'
    own_admission_path = service.RUN / 'configs/admission.json'
    primary_lock = None
    own_lock = None
    completed = False
    own_lock_held = False
    primary_registry = None

    def save(**updates):
        journal.update(updates)
        barrier.atomic_json(journal_path, journal)
        barrier.atomic_json(service.RUN / 'processes/coordinator.json', journal)

    def guard():
        status = observe_primary(expected, primary_registry, PRIMARY)
        # The initial authorization already captured the HTTP queue. During
        # natural shutdown the listener may close before the PID disappears;
        # lifecycle checks must not mistake that normal ordering for failure.
        if status == 'complete' and not journal.get('primary_naturally_complete'):
            save(primary_naturally_complete=True, primary_completed_observed_unix=time.time())
        if installed_admission is not None and primary_path.read_bytes() != installed_admission:
            raise RuntimeError('Primary admission changed during transfer; stopping transfer only')
        barrier.require_admitted(own_admission_path, expected)

    def spawn(role, name):
        child, record = launch_remote.spawn(role, name)
        children.append((child, record))
        journal['children'].append(record)
        save()
        return child

    def interrupt(signum, frame):
        raise InterruptedError('Coordinator interrupted by signal ' + str(signum))

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        own_lock = (service.RUN / 'processes/coordinator.lock').open('a')
        fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        own_lock_held = True
        # Cooperative writer lock: primary job readers need no lock because
        # each replacement is atomic. Root must not bypass this lock to edit.
        primary_lock = (PRIMARY / 'configs/admission.parallel_transfer.lock').open('a')
        fcntl.flock(primary_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        primary_snapshot = exact_primary(expected)
        primary_registry = primary_snapshot['registry']
        save(primary_snapshot=primary_snapshot, resources_before=gpu_and_host_headroom())
        service.refuse_existing_service()
        if list((service.RUN / 'logs').glob('*_job.json')):
            raise RuntimeError('Existing job records: this bundle is single-launch; do not overwrite/retry')
        old_admission = primary_path.read_bytes()
        barrier.atomic_bytes(service.RUN / 'processes' / f'primary_admission_before_{launch_id}.json', old_admission)
        transfer_admission = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': [expected],
                              'existing_comfy_port': None,
                              'note': 'Exact primary PID, UID, start ticks, and command SHA; no restart authorization.'}
        barrier.atomic_json(own_admission_path, transfer_admission)
        service.check_admission(transfer_admission, service.compute_processes(), service.queue_at(None))
        launch_remote.prepare()
        now = time.time()
        gate = {'schema': 1, 'launch_id': launch_id, 'root': str(service.RUN),
                'gpu_uuid': service.GPU, 'port': service.PORT, 'primary_root': str(PRIMARY),
                'primary': expected, 'coordinator': coordinator,
                'primary_registry': primary_registry,
                'created_unix': now, 'expires_unix': now + 180}
        barrier.atomic_json(service.RUN / 'processes/pre_cuda_gate.json', gate)
        supervisor = spawn('supervisor', 'supervise_service.py')
        ready_path, release_path = barrier.paths(service.RUN, launch_id)
        while time.time() < gate['expires_unix']:
            guard()
            if supervisor.poll() is not None:
                raise RuntimeError('Supervisor exited before barrier handshake')
            registry = service.RUN / 'processes/service.json'
            if ready_path.exists() and registry.exists():
                ready = barrier.read_json(ready_path)
                owner = barrier.read_json(registry)
                service.assert_owned(owner)
                peer = {'pid': owner['pid'], 'identity': barrier.process_identity(owner['pid'])}
                if ready['pid'] != peer['pid'] or ready['identity'] != peer['identity'] or ready['launch_id'] != launch_id:
                    raise RuntimeError('Barrier PID/identity differs from registered service')
                break
            time.sleep(0.1)
        else:
            raise TimeoutError('No pre-CUDA ready record within 180 seconds')
        save(transfer=peer, status='waiting_to_release', resources_before_release=gpu_and_host_headroom())
        guard()
        service.check_admission(transfer_admission, service.compute_processes(), service.queue_at(None))
        installed_admission = add_exact_peer(old_admission, peer)
        compare_replace(primary_path, old_admission, installed_admission)
        barrier.atomic_bytes(service.RUN / 'processes' / f'primary_admission_installed_{launch_id}.json', installed_admission)
        # Watchdog starts before release. If coordinator dies, its exact identity
        # becomes absent and the watchdog terminates only the transfer service.
        watchdog = spawn('watchdog', 'lease_watchdog.py')
        guard()
        release = {k: ready[k] for k in ('schema', 'launch_id', 'root', 'gpu_uuid', 'port', 'pid', 'identity')}
        release.update(primary=expected, coordinator=coordinator, expires_unix=gate['expires_unix'],
                       primary_admission_sha256=barrier.sha256(primary_path),
                       transfer_admission_sha256=barrier.sha256(own_admission_path))
        barrier.validate_release(service.RUN, gate, ready, release)
        barrier.atomic_json(release_path, release)
        save(status='released_waiting_for_readiness', primary_admission_sha256=barrier.sha256(primary_path))
        launch_remote.wait_readiness(supervisor, guard)
        controller = spawn('controller', 'run_queue.py')
        save(status='running')
        deadline = time.monotonic() + 8 * 3600 + 300
        while time.monotonic() < deadline:
            guard()
            if controller.poll() is not None:
                if controller.returncode != 0:
                    raise RuntimeError('Transfer controller failed: ' + str(controller.returncode))
                state = barrier.read_json(service.RUN / 'logs/controller_state.json')
                if state.get('status') != 'all_queued_jobs_complete':
                    raise RuntimeError('Controller exited without completing the sealed queue')
                completed = True
                break
            if watchdog.poll() is not None or supervisor.poll() is not None:
                # The controller stops the service in its finally block; allow
                # both supervisor and watchdog to finish first in that normal
                # race. Next loop checks controller success + sealed queue.
                try:
                    controller.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('Service/watchdog exited while controller still active')
                continue
            time.sleep(5)
        else:
            raise TimeoutError('Coordinator batch deadline exceeded')
        save(status='jobs_complete')
    except BaseException as exc:
        if own_lock_held:
            save(status='failed', error=repr(exc))
        raise
    finally:
        # Block any late barrier release and prevent new queue submissions first.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        errors = []
        for child, record in reversed(children):
            if record['role'] == 'controller':
                try:
                    journal['cleanup'].append(stop_process(record, child))
                except BaseException as exc:
                    errors.append('controller: ' + repr(exc))
        registry = service.RUN / 'processes/service.json'
        try:
            if registry.exists():
                current = barrier.read_json(registry)
                # Never clean an old unrelated registry when launch failed early.
                related = owner is not None and current['pid'] == owner['pid'] and current['identity'] == owner['identity']
                if not related:
                    ready_path, _ = barrier.paths(service.RUN, launch_id)
                    if ready_path.exists():
                        ready = barrier.read_json(ready_path)
                        related = ready['pid'] == current['pid'] and ready['identity'] == barrier.process_identity(current['pid'])
                if related:
                    journal['cleanup'].append(service.stop())
        except BaseException as exc:
            errors.append('service: ' + repr(exc))
        for child, record in reversed(children):
            if record['role'] != 'controller':
                try:
                    journal['cleanup'].append(stop_process(record, child))
                except BaseException as exc:
                    errors.append(record['role'] + ': ' + repr(exc))
        # A killed coordinator cannot execute this path; its watchdog still
        # releases GPU. Exact stale permissions then need root audit/removal.
        # Cover an interruption immediately after atomic replacement but before
        # any Python bookkeeping assignment. Never overwrite third-party edits.
        if installed_admission is not None and old_admission is not None:
            try:
                current_bytes = primary_path.read_bytes()
                if current_bytes == installed_admission:
                    peer_pid = journal.get('transfer', {}).get('pid')
                    if (peer_pid is None or service.current_identity(peer_pid) is not None
                            or any(p['pid'] == peer_pid for p in service.compute_processes())):
                        raise RuntimeError('Transfer process/compute absence unverified; retaining exact permission')
                    compare_replace(primary_path, installed_admission, old_admission)
                    journal['primary_admission_restored'] = True
                elif current_bytes == old_admission:
                    journal['primary_admission_already_original_or_never_installed'] = True
                else:
                    raise RuntimeError('Primary admission changed externally; preserved without overwriting')
            except BaseException as exc:
                errors.append('admission_restore: ' + repr(exc))
        if own_lock_held:
            save(cleanup_errors=errors, ended_unix=time.time(),
                 status='complete' if completed and not errors else 'failed_or_cleanup_incomplete')
        if primary_lock:
            primary_lock.close()
        if own_lock:
            own_lock.close()
        if errors:
            raise RuntimeError('Cleanup incomplete; inspect coordinator journal: ' + '; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    inspect = sub.add_parser('inspect', help='read-only identity/queue/GPU/headroom report; no torch')
    inspect.add_argument('--primary-pid', type=int, required=True)
    start = sub.add_parser('run', help='explicitly start the reviewed transfer instance')
    start.add_argument('--expected-primary-file', type=Path, required=True)
    start.add_argument('--decision-note', required=True, help='root scientific go/no-go evidence')
    start.add_argument('--execute', action='store_true', required=True)
    args = parser.parse_args()
    if args.action == 'inspect':
        peer = {'pid': args.primary_pid, 'identity': barrier.process_identity(args.primary_pid)}
        print(json.dumps(dict(exact_primary(peer), resources=gpu_and_host_headroom()), indent=2))
    else:
        value = barrier.read_json(args.expected_primary_file)
        expected = value.get('primary', value)
        if len(args.decision_note.strip()) < 12:
            raise SystemExit('Supply a concrete reviewed scientific decision, not an empty activation')
        run(expected, args.decision_note)


if __name__ == '__main__':
    main()

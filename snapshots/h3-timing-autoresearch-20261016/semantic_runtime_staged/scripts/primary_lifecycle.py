"""Accept only the pinned live primary or its fully verified natural completion."""
from pathlib import Path
import time

import startup_barrier as barrier


class CleanupPending(RuntimeError):
    pass


def primary_state(expected, initial_registry, root, *, reader=barrier.process_identity,
                  pid_exists=lambda pid: (Path('/proc') / str(pid)).exists()):
    root = Path(root)
    registry = barrier.read_json(root / 'processes/service.json')
    if registry != initial_registry or registry.get('pid') != expected['pid']:
        raise RuntimeError('Primary registry changed/restarted; new authorization required')
    actual = reader(expected['pid'])
    if actual is not None:
        if actual != expected['identity']:
            raise RuntimeError('Primary PID identity changed')
        return 'live'
    state = barrier.read_json(root / 'logs/controller_state.json')
    if state.get('status') != 'all_queued_jobs_complete':
        raise RuntimeError('Primary exited without completing its queue')
    if pid_exists(expected['pid']):
        raise CleanupPending('Completed primary process still awaits reaping')
    try:
        cleanup = barrier.read_json(root / 'processes/cleanup.json')
    except FileNotFoundError as exc:
        raise CleanupPending('Primary completion cleanup not yet persisted') from exc
    if (cleanup.get('service_record') != initial_registry or cleanup.get('pid') != expected['pid']
            or cleanup.get('process_absent') is not True or cleanup.get('own_compute_absent') is not True):
        raise CleanupPending('Primary natural completion cleanup is not exact/verified')
    return 'complete'


def observe_primary(expected, initial_registry, root, *, timeout=45, **kwargs):
    """Wait only for the documented stop/reap journal race, never for a restart."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return primary_state(expected, initial_registry, root, **kwargs)
        except CleanupPending:
            if time.monotonic() >= deadline:
                raise RuntimeError('Primary completion cleanup remained unverified')
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))

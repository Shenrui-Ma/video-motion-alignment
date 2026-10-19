"""Let current observers run first; completed failed generations cannot wait."""
import json
import hashlib
from pathlib import Path


def identity(pid):
    p = Path('/proc') / str(pid)
    try:
        return {'uid': p.stat().st_uid,
                'start_ticks': p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]}
    except FileNotFoundError:
        return None


def terminal_failure(root, step, get_identity=identity):
    try:
        failure = json.loads((step / 'failure.json').read_text())
        request = json.loads((step / 'request.json').read_text())
        state = json.loads((root / 'logs/controller_state.json').read_text())
        service = json.loads((root / 'processes/service.json').read_text())
        if (not failure.get('error')
                or failure.get('request_sha256') != hashlib.sha256((step / 'request.json').read_bytes()).hexdigest()
                or state.get('status') != 'failed' or state.get('current') != request.get('run_id')):
            return False
        expected = service['identity']
        if not all(k in expected for k in ('uid', 'start_ticks')):
            return False
        current = get_identity(service['pid'])
        return current is None or (current['uid'], str(current['start_ticks'])) != (expected['uid'], str(expected['start_ticks']))
    except (OSError, ValueError, KeyError, IndexError):
        return False


def pending(roots, get_identity=identity):
    for root in map(Path, roots):
        for step in (root / 'audit/observations').glob('step*'):
            waiting = ((step / 'request.json').exists() and (step / 'native.json').exists()
                       and not (step / 'pose_complete.json').exists() and not (step / 'response.json').exists())
            if waiting and not terminal_failure(root, step, get_identity):
                return True
    return False

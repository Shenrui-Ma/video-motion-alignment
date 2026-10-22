"""Bind a newly spawned direct child only after Linux publishes its complete argv."""
import hashlib
import os
from pathlib import Path
import subprocess
import time


def snapshot(pid, proc_root=Path('/proc')):
    """None means no bindable identity; an empty cmdline is never a valid hash."""
    path = Path(proc_root) / str(int(pid))
    try:
        before = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
        owner = path.stat().st_uid
        command = (path / 'cmdline').read_bytes()
        after = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
        if before[0] == 'Z' or after[0] == 'Z' or not command:
            return None
        if before[19] != after[19] or path.stat().st_uid != owner:
            return None
        return {'pid': int(pid), 'uid': owner, 'start_ticks': int(after[19]),
                'command': command, 'cmdline_sha256': hashlib.sha256(command).hexdigest()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def service_record(row):
    if row is None:
        raise ProcessLookupError('process has no complete live identity')
    return {'uid': row['uid'], 'start_ticks': str(row['start_ticks']),
            'cmdline': row['command'].replace(b'\0', b' ').decode()}


def hashed_record(row, include_pid=False):
    if row is None:
        return None
    result = {'uid': row['uid'], 'start_ticks': str(row['start_ticks']),
              'cmdline_sha256': row['cmdline_sha256']}
    if include_pid:
        result.update(pid=row['pid'], start_ticks=row['start_ticks'])
    return result


def bind_launched_child(process, command, *, timeout=3, lookup=None,
                        clock=time.monotonic, sleep=time.sleep):
    expected = b'\0'.join(os.fsencode(value) for value in command) + b'\0'
    deadline = clock() + timeout
    generation = None
    while process.poll() is None and clock() < deadline:
        row = (lookup or snapshot)(process.pid)
        if row is not None:
            current = (row['pid'], row['uid'], row['start_ticks'])
            if row['pid'] != process.pid or row['uid'] != os.getuid():
                raise RuntimeError('launched direct child owner/PID differs')
            if generation is None:
                generation = current
            if current != generation:
                raise RuntimeError('launched child generation changed before argv binding')
            if row['command'] == expected:
                return row
        sleep(.01)
    raise RuntimeError('unable to bind launched child to complete expected argv')


def bind_or_reap(process, command, **kwargs):
    """On a binding failure, reap this unregistered direct Popen child only.

    Popen.poll first establishes that this unreaped direct child still exists;
    Popen's wait/terminate guards prevent operations on a subsequently reused PID.
    This helper is exclusively for the immediate post-Popen binding boundary.
    Registered service lifetimes keep their exact identity/ownership guards.
    """
    try:
        return bind_launched_child(process, command, **kwargs)
    except BaseException as primary:
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
        except BaseException as cleanup:
            if hasattr(primary, 'add_note'):
                primary.add_note('unregistered direct-child cleanup: ' + repr(cleanup))
        raise

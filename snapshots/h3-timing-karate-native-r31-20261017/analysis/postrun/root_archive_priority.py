"""Give one archived GPU batch a CPU slot, then resume the exact R27 coordinator."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
R27 = Path('/Users/researcher/DevProjects/h3-timing-auto-controller-r27-20261017/analysis/postrun')
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
PID = 80029

def identity():
    return subprocess.check_output(['/bin/ps', '-p', str(PID), '-o', 'uid=,lstart=,command='], text=True).strip()

def save(record):
    dst = HERE / 'ROOT_ARCHIVE_PRIORITY.json'
    tmp = dst.with_suffix('.tmp')
    tmp.write_text(json.dumps(record, indent=2) + '\n')
    tmp.replace(dst)

original = identity()
assert int(original.split()[0]) == os.getuid()
assert str(R27 / 'consume.py') + ' --start' in original
assert json.loads((R27 / 'CONSUMER_IDENTITY.json').read_text())['pid'] == PID
record = dict(consumer_pid=PID, identity=original, guard_pid=os.getpid(), started=time.time(), maximum_child_seconds=930, reason='One R31 CPU phase before GPU2 release; R32 online observer keeps priority')
save(record)
paused = False
try:
    with LOCK.open('a') as lock:
        deadline = time.monotonic() + 180
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError('CPU phase boundary wait exceeded')
                time.sleep(.1)
        assert identity() == original
        os.kill(PID, signal.SIGSTOP)
        paused = True
        record.update(status='paused_at_free_CPU_boundary', paused=time.time())
        save(record)
        fcntl.flock(lock, fcntl.LOCK_UN)
    with (HERE / 'logs/root_archive_priority_phase.log').open('w') as log:
        result = subprocess.run(['python3', str(HERE / 'one_phase.py'), '--execute'], cwd=HERE, stdout=log, stderr=subprocess.STDOUT, timeout=930)
    record['child_returncode'] = result.returncode
    if (HERE / 'LAST_ONE_PHASE.json').exists():
        value = json.loads((HERE / 'LAST_ONE_PHASE.json').read_text())
        record['phase_result'] = {k: value[k] for k in ('status', 'scope', 'phase') if k in value}
finally:
    if paused:
        assert identity() == original
        os.kill(PID, signal.SIGCONT)
        record.update(status='resumed', resumed=time.time())
    save(record)
    print(json.dumps(record))

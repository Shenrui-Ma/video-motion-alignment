"""Read-only final task process/VRAM check; run on the experiment host."""
import json
import subprocess
import time
from pathlib import Path

ROOT = '/data5/researcher/h3_runs/event_emphasis_pilot_20261013'
EXPECTED = {49769: '2592931766', 34913: '2593008314',
            54731: '2592937844', 49756: '2592931746'}


def identity(pid):
    p = Path('/proc') / str(pid)
    try:
        tail = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'uid': p.stat().st_uid, 'start_ticks': tail[19],
                'state': tail[0], 'ppid': tail[1], 'sid': tail[3]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def command(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    return {'rc': p.returncode, 'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()}


d = {'observed_unix': time.time(), 'host': '192.0.2.1', 'identity_checks': {}}
for pid, ticks in EXPECTED.items():
    i = identity(pid)
    d['identity_checks'][str(pid)] = {
        'expected_uid': 1016, 'expected_start_ticks': ticks, 'current': i,
        'original_identity_absent': i is None or i['uid'] != 1016 or i['start_ticks'] != ticks}
d['task_matching_processes'] = []
for p in Path('/proc').iterdir():
    if not p.name.isdigit():
        continue
    try:
        if p.stat().st_uid != 1016:
            continue
        cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        if ROOT in cmd:
            d['task_matching_processes'].append({'identity': identity(int(p.name)), 'command': cmd})
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
d['port_8446_listeners'] = []
for name in ('tcp', 'tcp6'):
    for line in (Path('/proc/net') / name).read_text().splitlines()[1:]:
        fields = line.split()
        if int(fields[1].rsplit(':', 1)[1], 16) == 8446 and fields[3] == '0A':
            d['port_8446_listeners'].append({'table': name, 'entry': line.strip()})
d['listener_probe'] = '/proc/net/tcp,tcp6 (ss unavailable)'
d['compute'] = command(['/usr/bin/nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory', '--format=csv,noheader'])
d['selected_gpu'] = command(['/usr/bin/nvidia-smi', '-i', 'GPU-REDACTED',
                             '--query-gpu=uuid,memory.used,memory.free', '--format=csv,noheader'])
d['pass'] = (all(x['original_identity_absent'] for x in d['identity_checks'].values())
             and not d['task_matching_processes'] and not d['port_8446_listeners']
             and d['compute']['rc'] == 0 and d['selected_gpu']['rc'] == 0)
print(json.dumps(d))

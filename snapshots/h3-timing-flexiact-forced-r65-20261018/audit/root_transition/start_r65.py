"""Root's bounded handoff from completed R55 to the first R65 Native/ON pair."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018')
OUT = ROOT / 'audit/root_transition'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def run(*args):
    result = subprocess.run(list(args), cwd=ROOT, check=True, timeout=720,
                            capture_output=True, text=True)
    print(result.stdout, end='', flush=True)
    return result


def main():
    deadline = time.monotonic() + 7200
    while not (OUT / 'R55_RELEASED.json').exists():
        assert not (OUT / 'FAILURE.json').exists(), 'R55 handoff verification failed'
        assert time.monotonic() < deadline, 'R55 release wait exceeded two hours'
        time.sleep(15)
    released = read(OUT / 'R55_RELEASED.json')
    assert released['status'] == 'pass'
    assert released['cleanup']['pid'] == 111012
    assert released['cleanup']['service_record']['identity']['start_ticks'] == '1494784'
    assert released['runtime_gate_sha256'] == hashlib.sha256((OUT / 'R55_RUNTIME_GATE_RESIDENT.json').read_bytes()).hexdigest()
    assert not Path('/proc/111012').exists()
    assert not (ROOT / 'processes/service.json').exists(), 'R65 launch already registered'
    sys.path.insert(0, str(ROOT / 'scripts'))
    import service
    rows = service.compute_processes()
    own = [p for p in rows if service.proc_uid(p['pid']) == os.getuid()]
    assert not own, 'Unexpected own GPU process before the reserved R65 handoff'
    snapshot = run('nvidia-smi', '--id=' + service.GPU,
                   '--query-gpu=index,uuid,name,memory.free,temperature.gpu',
                   '--format=csv,noheader,nounits').stdout.strip().split(',')
    assert len(snapshot) == 5 and int(snapshot[0]) == 1 and snapshot[1].strip() == service.GPU
    assert float(snapshot[3]) >= 20480 and 0 <= float(snapshot[4]) < 85
    write(OUT / 'R65_LIVE_RESOURCE.json', {'unix': time.time(), 'gpu': snapshot, 'processes': rows})
    admission = read(ROOT / 'configs/admission.json')
    assert admission['scope'] == 'own_user_video_jobs'
    admission.update(ready_for_launch=True, existing_comfy_port=None, permitted_compute_processes=[])
    write(ROOT / 'configs/admission.json', admission)
    run('python3', str(ROOT / 'scripts/preflight.py'))
    run('python3', str(ROOT / 'scripts/execution_gate.py'), 'seal')
    run('python3', str(ROOT / 'scripts/execution_gate.py'), 'approve-first-pair', '--root-admitted')
    run('python3', str(ROOT / 'scripts/launch_remote.py'), '--service-only')
    ready = read(ROOT / 'processes/cuda_gate_ready.json')
    owner = read(ROOT / 'processes/service.json')
    service.assert_owned(owner)
    assert ready['pid'] == owner['pid'] and ready['identity'] == service.external_identity(owner['pid'])
    write(ROOT / 'processes/cuda_gate_go.json', ready)
    deadline = time.monotonic() + 600
    while True:
        service.assert_owned(owner)
        try:
            with urllib.request.urlopen('http://127.0.0.1:8535/object_info/H3TemporalRouter', timeout=5) as response:
                if 'H3TemporalRouter' in json.load(response):
                    break
        except OSError:
            pass
        assert time.monotonic() < deadline, 'R65 HTTP startup exceeded ten minutes'
        time.sleep(2)
    run('python3', str(ROOT / 'scripts/start_controller.py'), '--pid', str(owner['pid']),
        '--start-ticks', str(owner['identity']['start_ticks']))
    write(OUT / 'R65_STARTED.json', {'unix': time.time(), 'owner': owner,
          'controller': read(ROOT / 'processes/controller.json'),
          'launch_scope': 'first fitness Native and fixed ON pair; rest awaits actual pair review'})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        write(OUT / 'R65_START_FAILURE.json', {'unix': time.time(), 'error': repr(exc)})
        raise

"""Root's bounded handoff from completed R55 to the first R66 Native/ON pair."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018')
PEER = Path('/data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018')
OUT = ROOT / 'audit/root_launch'


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
    assert read(PEER/'audit/root_transition/SOURCE_TRACKING_DONE.json')['passed']
    assert not (ROOT/'processes/service.json').exists(), 'R66 already registered'
    sys.path.insert(0,str(ROOT/'scripts'))
    import service
    peer=read(PEER/'processes/service.json')
    assert peer['pid']==201359 and peer['identity']['start_ticks']=='3125873'
    peer_identity=service.external_identity(peer['pid'])
    assert peer_identity['uid']==os.getuid()
    rows=service.compute_processes()
    own=[r for r in rows if service.proc_uid(r['pid'])==os.getuid()]
    assert {r['pid'] for r in own} <= {peer['pid']}, 'Unexpected own compute process'
    snapshot = run('nvidia-smi', '--id=' + service.GPU,
                   '--query-gpu=index,uuid,name,memory.free,temperature.gpu',
                   '--format=csv,noheader,nounits').stdout.strip().split(',')
    assert len(snapshot) == 5 and int(snapshot[0]) == 2 and snapshot[1].strip() == service.GPU
    assert float(snapshot[3]) >= 20480 and 0 <= float(snapshot[4]) < 85
    write(OUT / 'R66_LIVE_RESOURCE.json', {'unix': time.time(), 'gpu': snapshot, 'processes': rows})
    admission = read(ROOT / 'configs/admission.json')
    assert admission['scope'] == 'own_user_video_jobs'
    admission.update(ready_for_launch=True, existing_comfy_port=None, permitted_compute_processes=[{'pid':peer['pid'],'identity':peer_identity}])
    write(ROOT / 'configs/admission.json', admission)
    run('python3', str(ROOT / 'scripts/preflight.py'))
    run('python3', str(ROOT / 'scripts/execution_gate.py'), 'seal')
    run('python3', str(ROOT / 'scripts/execution_gate.py'), 'approve-first-pair', '--root-admitted')
    run('python3', str(ROOT / 'scripts/launch_remote.py'), '--service-only')
    ready = read(ROOT / 'processes/cuda_gate_ready.json')
    owner = read(ROOT / 'processes/service.json')
    service.assert_owned(owner)
    assert ready['pid'] == owner['pid'] and ready['identity'] == service.external_identity(owner['pid'])
    peer_admission=read(PEER/'configs/admission.json')
    peer_admission['permitted_compute_processes'].append({'pid':owner['pid'],'identity':ready['identity']})
    write(PEER/'configs/admission.json',peer_admission)
    write(ROOT / 'processes/cuda_gate_go.json', ready)
    deadline = time.monotonic() + 600
    while True:
        service.assert_owned(owner)
        try:
            with urllib.request.urlopen('http://127.0.0.1:8536/object_info/H3TemporalRouter', timeout=5) as response:
                if 'H3TemporalRouter' in json.load(response):
                    break
        except OSError:
            pass
        assert time.monotonic() < deadline, 'R66 HTTP startup exceeded ten minutes'
        time.sleep(2)
    run('python3', str(ROOT / 'scripts/start_controller.py'), '--pid', str(owner['pid']),
        '--start-ticks', str(owner['identity']['start_ticks']))
    write(OUT / 'R66_STARTED.json', {'unix': time.time(), 'owner': owner,
          'controller': read(ROOT / 'processes/controller.json'),
          'launch_scope': 'first human2animal_1__movie_man_11 Native and fixed ON pair; rest awaits actual pair review'})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        write(OUT / 'R66_START_FAILURE.json', {'unix': time.time(), 'error': repr(exc)})
        raise

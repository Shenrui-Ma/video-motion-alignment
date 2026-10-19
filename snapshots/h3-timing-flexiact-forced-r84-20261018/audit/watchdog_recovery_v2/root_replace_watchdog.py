"""Replace only this run's watchdog after checking the live service and old owner."""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import service

HERE = Path(__file__).resolve().parent


def main():
    if ROOT != Path(service.RUNTIME['remote_root']):
        raise RuntimeError('This operation requires the remote run directory')
    owner = json.loads((ROOT / 'processes/service.json').read_text())
    if owner['pid'] != 857566 or str(owner['identity']['start_ticks']) != '8690132':
        raise RuntimeError('The original R84 service generation has changed')
    service.assert_owned(owner)
    receipt = HERE / 'ROOT_REPLACEMENT.json'
    if receipt.exists():
        raise RuntimeError('Replacement already recorded; inspect before retrying')
    previous = json.loads((ROOT / 'processes/watchdog.json').read_text())
    actual = service.current_identity(previous['pid'])
    if actual is not None:
        if actual != previous['identity'] or actual['uid'] != os.getuid():
            raise RuntimeError('Old watchdog identity has changed')
        if str(ROOT / 'scripts/lease_watchdog.py') not in actual['cmdline']:
            raise RuntimeError('The registered process is not the original watchdog')
    service.write_json(HERE / 'ORIGINAL_WATCHDOG.json', previous)
    if actual is not None:
        os.kill(previous['pid'], signal.SIGTERM)
        if not service.wait_absent(previous['pid'], 10):
            raise RuntimeError('Old watchdog remains live; no replacement started')
    service.assert_owned(owner)
    command = ['python3', '-u', str(HERE / 'watchdog_v2.py'),
               '--expected-pid', str(owner['pid']),
               '--expected-start-ticks', str(owner['identity']['start_ticks'])]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
    with (HERE / 'watchdog_v2.log').open('ab', buffering=0) as log:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True)
    identity = service.bind_child(child, command)
    replacement = {'pid': child.pid, 'identity': identity, 'role': 'watchdog_v2',
                   'service_pid': owner['pid'], 'service_identity': owner['identity']}
    service.write_json(ROOT / 'processes/watchdog.json', replacement)
    deadline = time.monotonic() + 15
    while not (HERE / 'STARTED.json').exists():
        if child.poll() is not None:
            raise RuntimeError('Replacement watchdog exited before startup')
        if time.monotonic() >= deadline:
            raise TimeoutError('Replacement watchdog startup receipt pending')
        time.sleep(.2)
    started = json.loads((HERE / 'STARTED.json').read_text())
    if started['watchdog_pid'] != child.pid or started['watchdog_identity'] != identity:
        raise RuntimeError('Startup receipt belongs to another watchdog')
    service.assert_owned(owner)
    result = {'original': previous, 'replacement': replacement, 'service': owner,
              'watchdog_sha256': hashlib.sha256((HERE / 'watchdog_v2.py').read_bytes()).hexdigest(),
              'service_preserved': True, 'unix': time.time()}
    service.write_json(receipt, result)
    print(json.dumps({'watchdog_pid': child.pid, 'service_pid': owner['pid'],
                      'service_preserved': True}))


if __name__ == '__main__':
    main()

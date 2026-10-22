"""Exact administrative guard handoff; never signals the inference service."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import service
from review_wait import read, sha

EXPECTED_BOOT = 'd91ff997-68e0-48b1-8ca8-ba54ca504903'
SERVICE = {'pid': 21744, 'uid': 1016, 'start_ticks': '2656249078', 'cmdline_sha256': '079bf8c0ffd06019cdf280c6fba18d90e2fed8398c9066f9f6088f6e43039abb'}
OLD = {'pid': 21745, 'uid': 1016, 'start_ticks': '2656249092', 'cmdline_sha256': 'cdcdade07a0f4ee9d3870b443f75a9d2f8ae0cf3de8c3fcbf395bef7774096a8'}
OLD_SHA = 'ce0991abe2663ae09c534b42d698696de86241f3a6607a7a7ba9cb123d7e8ef0'


def exact(record, expected):
    return (record['pid'] == expected['pid'] and
            service.current_identity(record['pid']) == record['identity'] and
            service.external_identity(record['pid']) == {k: expected[k] for k in ('uid', 'start_ticks', 'cmdline_sha256')})


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    assert ROOT == Path(service.RUNTIME['remote_root'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == EXPECTED_BOOT
    owner = read(ROOT/'processes/service.json'); old = read(ROOT/'processes/watchdog.json')
    assert exact(owner, SERVICE) and exact(old, OLD)
    assert sha(ROOT/'scripts/lease_watchdog.py') == OLD_SHA
    assert sha(ROOT/'deploy_manifest.json') == '7d07363e88de9fa10f521e95daa7cc720a7e09b43aa6d9b731bd76e497e73996'
    state = read(ROOT/'logs/controller_state.json')
    assert state['status'] in ('pending_or_running', 'waiting_native_visual_review', 'arm_verified')
    record = {'schema':'r150-native-review-watchdog-handoff-v1', 'boot_id':EXPECTED_BOOT,
              'owner':owner, 'old_watchdog':old, 'old_watchdog_hashed':OLD,
              'original_lease_sha256':OLD_SHA, 'original_producer_seal_sha256':sha(ROOT/'deploy_manifest.json'),
              'overlay_files':{p.name:sha(p) for p in HERE.glob('*.py')},
              'before_controller_state':state, 'before_unix':time.time(),
              'scope':'Only idle expiration during owner-bound valid Native review; sealed files unchanged.'}
    if not args.execute:
        print(json.dumps({'dry_run_passed':True,'owner':SERVICE,'old_watchdog':OLD,'controller_state':state})); return
    assert not (HERE/'HANDOFF.json').exists()
    service.write_json(HERE/'BEFORE.json',record)
    command=['python3','-u',str(HERE/'watchdog.py'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
    with (HERE/'watchdog.log').open('xb',buffering=0) as log:
        child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,start_new_session=True)
    retired=False
    try:
        new={'pid':child.pid,'identity':service.bind_child(child,command),'role':'watchdog','administrative_overlay':str(HERE)}
        deadline=time.monotonic()+45
        ready_path=HERE/'runtime/READY.json'
        while time.monotonic()<deadline and not ready_path.exists():
            assert child.poll() is None and exact(owner,SERVICE)
            time.sleep(.1)
        ready=read(ready_path)
        assert ready['passed'] and ready['pid']==new['pid'] and ready['identity']==new['identity'] and ready['owner']==owner
        assert ready['first_state']['reason'] is None
        assert service.current_identity(child.pid)==new['identity'] and exact(owner,SERVICE) and exact(old,OLD)
        # Only the reviewed old administrative watchdog is signalled.
        os.kill(old['pid'],signal.SIGTERM);retired=True
        deadline=time.monotonic()+10
        while service.current_identity(old['pid'])==old['identity'] and time.monotonic()<deadline:time.sleep(.05)
        assert service.current_identity(old['pid'])!=old['identity']
        assert service.current_identity(child.pid)==new['identity'] and exact(owner,SERVICE)
        service.write_json(ROOT/'processes/watchdog.json',new)
        record.update(passed=True,new_watchdog=new,new_watchdog_hashed=service.external_identity(child.pid),
                      old_generation_absent=True,service_same_generation=True,
                      ready_sha256=sha(ready_path),after_unix=time.time(),
                      after_controller_state=read(ROOT/'logs/controller_state.json'))
        service.write_json(HERE/'HANDOFF.json',record)
        print(json.dumps({'passed':True,'old_pid':old['pid'],'new_pid':child.pid,'service_pid':owner['pid'],'service_same_generation':True,'handoff_sha256':sha(HERE/'HANDOFF.json')}))
    except BaseException as error:
        service.write_json(HERE/'HANDOFF_ERROR.json',{'error':repr(error),'old_retired':retired,'new_pid':child.pid,'unix':time.time()})
        if not retired and child.poll() is None:
            child.terminate();child.wait(timeout=10)
        raise


if __name__=='__main__':
    main()

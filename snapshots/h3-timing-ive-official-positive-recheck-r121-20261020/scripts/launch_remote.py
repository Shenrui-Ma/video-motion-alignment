"""Admit only our isolated process and preserve runtime provenance."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
import service
import preflight

def created_owner(root, supervisor_pid, supervisor_identity):
    """Return only the child recorded by this exact launch, never a registry substitute."""
    record_path=Path(root)/f'processes/supervisor_{supervisor_pid}.json'
    if not record_path.exists():return None
    record=json.loads(record_path.read_text())
    if record.get('pid')!=supervisor_pid or record.get('identity')!=supervisor_identity:return None
    owner=record.get('service_record')
    if owner is None:return None
    if record.get('service_pid')!=owner.get('pid') or record.get('service_identity')!=owner.get('identity'):
        raise ValueError('supervisor child identity is inconsistent')
    current_path=Path(root)/'processes/service.json'
    if not current_path.exists():return None
    current=json.loads(current_path.read_text())
    if current.get('pid')!=owner.get('pid') or current.get('identity')!=owner.get('identity'):return None
    return owner


def cleanup_created_owner(root, supervisor_pid, supervisor_identity):
    owner=created_owner(root,supervisor_pid,supervisor_identity)
    if owner is None:return {'stopped':False,'reason':'no_current_child_owned_by_this_launch'}
    return service.stop(expected_record=owner)


def wait_service_gate(root,supervisor,supervisor_identity,*,timeout=660,clock=time.monotonic,sleep=time.sleep):
    if type(timeout) not in (int,float) or not 0<timeout<=660:raise ValueError('invalid launcher admission/start budget')
    root=Path(root);deadline=clock()+timeout
    while clock()<deadline:
        if supervisor.poll() is not None:raise RuntimeError('supervisor exited before pre-CUDA ready')
        if service.current_identity(supervisor.pid)!=supervisor_identity:raise RuntimeError('launcher supervisor generation changed')
        ready=root/'processes/cuda_gate_ready.json';registered=root/'processes/service.json'
        if ready.exists() and registered.exists():
            gate=json.loads(ready.read_text());owner=created_owner(root,supervisor.pid,supervisor_identity)
            if owner is not None:
                service.assert_owned(owner)
                if gate['pid']!=owner['pid'] or gate['identity']!=service.external_identity(owner['pid']):raise ValueError('pre-CUDA gate differs from service PID')
                if gate.get('supervisor')!={'pid':supervisor.pid,'identity':service.external_identity(supervisor.pid)}:raise ValueError('pre-CUDA supervisor binding differs')
                if clock()>=deadline:raise TimeoutError('pre-CUDA readiness arrived after launcher deadline')
                return gate,owner
        sleep(min(.1,max(0,deadline-clock())))
    raise TimeoutError('pre-CUDA service gate not reached after resource admission budget')


def cleanup_launch(root,supervisor,supervisor_identity):
    """Stop this launch's admission waiter before any later child can be created."""
    actual=service.current_identity(supervisor.pid)
    if actual is not None and actual!=supervisor_identity:raise RuntimeError('refusing to stop replaced supervisor generation')
    if actual is not None:
        supervisor.terminate()
        try:supervisor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if service.current_identity(supervisor.pid)!=supervisor_identity:raise RuntimeError('supervisor changed before bounded kill')
            supervisor.kill();supervisor.wait(timeout=10)
    if service.current_identity(supervisor.pid)==supervisor_identity:raise RuntimeError('original supervisor still live')
    child=cleanup_created_owner(root,supervisor.pid,supervisor_identity)
    result={'supervisor_pid':supervisor.pid,'supervisor_identity':supervisor_identity,'original_supervisor_absent':True,'child':child,'pre_CUDA_unregistered_child_guard':'service_entry requires this exact live supervisor before and throughout root-go wait'}
    service.write_json(Path(root)/f'processes/launch_cleanup_{supervisor.pid}.json',result)
    return result


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--service-only',action='store_true',required=True);args=p.parse_args()
    r=service.RUN
    preflight.check(r,live=True)
    for name in ['custom_nodes','input','output','temp','user','logs','processes','audit','analysis']:
        (r/name).mkdir(exist_ok=True)
    for name in ['H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout']:
        target=r/'extensions'/name
        assert (target/'__init__.py').is_file(),target
        link=r/'custom_nodes'/name
        if not link.exists():link.symlink_to(target,target_is_directory=True)
    kj=r/'custom_nodes/ComfyUI-KJNodes'
    if not kj.exists():kj.symlink_to(service.RUNTIME['kj_nodes'],target_is_directory=True)
    from r121_contract import registry,prepare_loader_inputs
    for name in registry(r)[1]:prepare_loader_inputs(name,r)

    prov={'runtime':service.RUNTIME,'observed_unix':time.time(),'core_matches':{}}
    for rel,digest in json.loads((r/'configs/parent_core_hashes.json').read_text()).items():
        prov['core_matches'][rel]=hashlib.sha256((service.CORE/rel).read_bytes()).hexdigest()==digest
    if not all(prov['core_matches'].values()):raise ValueError('actual core differs from R54')
    service.write_json(r/'configs/runtime_provenance.json',prov)
    env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(r/'temp'),TMP=str(r/'temp'),TEMP=str(r/'temp'))
    with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
        supervisor_command=['python3','-u',str(r/'scripts/supervise_service.py')]
        supervisor=subprocess.Popen(supervisor_command,cwd=r/'scripts',
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
    supervisor_identity=service.bind_child(supervisor,supervisor_command)
    print(json.dumps({'supervisor_pid':supervisor.pid}),flush=True)
    try:
        gate,owner=wait_service_gate(r,supervisor,supervisor_identity)
        with (r/'logs/watchdog.log').open('ab',buffering=0) as log:
            watchdog_command=['python3','-u',str(r/'scripts/lease_watchdog.py'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]
            child=subprocess.Popen(watchdog_command,cwd=r/'scripts',stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
        service.write_json(r/'processes/watchdog.json',{'pid':child.pid,'identity':service.bind_child(child,watchdog_command),'role':'watchdog'})
        print(json.dumps({'service_only':True,'service':owner,'gate_ready':gate,'controller_started':False,'next':'root register this PID in peer admission; copy exact ready JSON atomically to cuda_gate_go.json; wait HTTP readiness then start_controller'}),flush=True)
    except BaseException as primary:
        try:
            cleanup_launch(r,supervisor,supervisor_identity)
        except BaseException as cleanup:
            try:
                service.write_json(r/f'processes/launch_cleanup_error_{supervisor.pid}.json',
                    {'primary':repr(primary),'cleanup':repr(cleanup),'supervisor_pid':supervisor.pid})
            except BaseException:pass  # Cleanup receipt failure must preserve the launch exception.
        raise

if __name__=='__main__':main()

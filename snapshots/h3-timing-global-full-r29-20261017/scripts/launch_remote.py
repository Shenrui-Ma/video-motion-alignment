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
    if not kj.exists():kj.symlink_to('/data5/researcher/h3_runs/short_event_pilot_20261013/custom_nodes/ComfyUI-KJNodes',target_is_directory=True)
    from r29_contract import registry,prepare_loader_inputs
    for name in registry(r)[1]:prepare_loader_inputs(name,r)

    parent=json.loads((r/'configs/parent_runtime_provenance.json').read_text())
    hashes=json.loads((r/'configs/model_hashes_host9.json').read_text())
    prov={'models':{},'core_matches':{},'code':{},'observed_unix':time.time()}
    for name,old in parent['models'].items():
        p=Path(service.MODELS)/name
        s=p.stat()
        assert (s.st_size,s.st_mtime_ns)==(old['bytes'],old['mtime_ns']),name
        assert hashes[name]['sha256']==old['prior_full_sha256'],name
        prov['models'][name]=dict(old,path=str(p),full_hash_recomputed=False,size_mtime_match=True)
    for rel,h in json.loads((r/'configs/parent_core_hashes.json').read_text()).items():
        actual=hashlib.sha256((service.CORE/rel).read_bytes()).hexdigest()
        prov['core_matches'][rel]=actual==h
    assert all(prov['core_matches'].values())
    for p in list((r/'scripts').glob('*.py'))+list((r/'extensions').rglob('*.py')):
        prov['code'][str(p.relative_to(r))]=hashlib.sha256(p.read_bytes()).hexdigest()
    service.write_json(r/'configs/runtime_provenance.json',prov)
    env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1')
    with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
        supervisor=subprocess.Popen(['python3','-u',str(r/'scripts/supervise_service.py')],cwd=r/'scripts',
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
    supervisor_identity=service.identity(supervisor.pid)
    print(json.dumps({'supervisor_pid':supervisor.pid}),flush=True)
    try:
        # Return exact future CUDA identity before importing torch or loading Comfy.
        for _ in range(100):
            if supervisor.poll() is not None:raise RuntimeError('supervisor exited')
            ready=r/'processes/cuda_gate_ready.json';registered=r/'processes/service.json'
            if ready.exists() and registered.exists():
                gate=json.loads(ready.read_text());owner=created_owner(r,supervisor.pid,supervisor_identity)
                if owner is None:
                    time.sleep(.1);continue
                service.assert_owned(owner)
                if gate['pid']!=owner['pid'] or gate['identity']!=service.external_identity(owner['pid']):raise ValueError('pre-CUDA gate differs from service PID')
                break
            time.sleep(.1)
        else:raise TimeoutError('pre-CUDA service gate not reached')
        with (r/'logs/watchdog.log').open('ab',buffering=0) as log:
            child=subprocess.Popen(['python3','-u',str(r/'scripts/lease_watchdog.py')],cwd=r/'scripts',stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
        service.write_json(r/'processes/watchdog.json',{'pid':child.pid,'identity':service.identity(child.pid),'role':'watchdog'})
        print(json.dumps({'service_only':True,'service':owner,'gate_ready':gate,'controller_started':False,'next':'root register this PID in peer admission; copy exact ready JSON atomically to cuda_gate_go.json; wait HTTP readiness then start_controller'}),flush=True)
    except BaseException:
        cleanup_created_owner(r,supervisor.pid,supervisor_identity)
        raise

if __name__=='__main__':main()

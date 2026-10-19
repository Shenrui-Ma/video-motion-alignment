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
import argparse

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
    parser=argparse.ArgumentParser();parser.add_argument("--service-only",action="store_true");args=parser.parse_args()
    from preflight import check as check_preflight

    check_preflight(service.RUN)

    r=service.RUN
    for name in ['custom_nodes','input','output','temp','user','logs','processes','audit','analysis']:
        (r/name).mkdir(exist_ok=True)
    for name in ['H3EventAudit','H3PairAudit','H3X0Readout','H3TemporalRouter','H3AutomaticWindowRouter']:
        target=r/'extensions'/name
        assert (target/'__init__.py').is_file(),target
        link=r/'custom_nodes'/name
        if not link.exists():link.symlink_to(target,target_is_directory=True)
    kj=r/'custom_nodes/ComfyUI-KJNodes'
    if not kj.exists():kj.symlink_to('/data5/researcher/h3_runs/short_event_pilot_20261013/custom_nodes/ComfyUI-KJNodes',target_is_directory=True)
    for p in (r/'inputs').iterdir():
        if p.suffix in ('.mp4','.jpg','.png','.webp'):
            dest=r/'input'/p.name
            assert not dest.is_symlink()
            shutil.copy2(p,dest)

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
    env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(r/'temp'),TMP=str(r/'temp'),TEMP=str(r/'temp'))
    with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
        supervisor_command=['python3','-u',str(r/'scripts/supervise_service.py')]
        supervisor=subprocess.Popen(supervisor_command,cwd=r/'scripts',
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
    supervisor_identity=service.bind_launched_child(supervisor,supervisor_command)
    print(json.dumps({'supervisor_pid':supervisor.pid}),flush=True)
    try:
        for _ in range(150):
            if supervisor.poll() is not None:raise RuntimeError('supervisor exited')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3AutomaticWindowRouter',timeout=2) as f:
                    info=json.load(f)
                assert 'H3AutomaticWindowRouter' in info
                with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3X0Readout',timeout=2) as f:
                    readout_info=json.load(f)
                assert 'H3X0Readout' in readout_info
                break
            except Exception:time.sleep(2)
        else:raise TimeoutError('readiness timeout')
        roles=[('watchdog','lease_watchdog.py')]
        owner=created_owner(r,supervisor.pid,supervisor_identity)
        if owner is None:raise RuntimeError('this launch has no current registered child')
        service.assert_owned(owner)
        for role,name in roles:
            command=['python3','-u',str(r/'scripts'/name)]
            if role=='controller':command+=['--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]
            with (r/'logs'/f'{role}.log').open('ab',buffering=0) as log:
                child=subprocess.Popen(command,cwd=r/'scripts',
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
            rec={'pid':child.pid,'identity':service.bind_launched_child(child,command),'role':role}
            service.write_json(r/'processes'/f'{role}.json',rec)
            print(json.dumps(rec),flush=True)
        if not args.service_only:
            subprocess.run(['python3','-u',str(r/'scripts/start_controller.py'),'--pid',str(owner['pid']),'--start-ticks',str(owner['identity']['start_ticks'])],cwd=r/'scripts',env=env,check=True)
        print(json.dumps({'service_only':args.service_only,'service':owner,'controller_started':not args.service_only}),flush=True)
    except BaseException as primary:
        try:cleanup_created_owner(r,supervisor.pid,supervisor_identity)
        except Exception as cleanup:
            service.write_json(r/'logs/launch_cleanup_error.json',{'primary_error':repr(primary),'cleanup_error':repr(cleanup)})
        raise

if __name__=='__main__':main()

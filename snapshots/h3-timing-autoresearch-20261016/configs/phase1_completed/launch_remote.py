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

r=service.RUN
for name in ['custom_nodes','input','output','temp','user','logs','processes','audit','analysis']:
    (r/name).mkdir(exist_ok=True)
for name in ['H3EventAudit','H3PairAudit','H3EventEmphasis','H3TemporalRouter']:
    target=r/'extensions'/name
    assert (target/'__init__.py').is_file(),target
    link=r/'custom_nodes'/name
    if not link.exists():link.symlink_to(target,target_is_directory=True)
kj=r/'custom_nodes/ComfyUI-KJNodes'
if not kj.exists():kj.symlink_to('/data5/researcher/h3_runs/short_event_pilot_20261013/custom_nodes/ComfyUI-KJNodes',target_is_directory=True)
for p in (r/'inputs').iterdir():
    if p.suffix in ('.mp4','.jpg','.png'):
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
env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1')
with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
    supervisor=subprocess.Popen(['python3','-u',str(r/'scripts/supervise_service.py')],cwd=r/'scripts',
        stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
print(json.dumps({'supervisor_pid':supervisor.pid}),flush=True)
try:
    for _ in range(150):
        if supervisor.poll() is not None:raise RuntimeError('supervisor exited')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3TemporalRouter',timeout=2) as f:
                info=json.load(f)
            assert 'H3TemporalRouter' in info
            break
        except Exception:time.sleep(2)
    else:raise TimeoutError('readiness timeout')
    for role,name in [('watchdog','lease_watchdog.py'),('controller','run_queue.py')]:
        with (r/'logs'/f'{role}.log').open('ab',buffering=0) as log:
            child=subprocess.Popen(['python3','-u',str(r/'scripts'/name)],cwd=r/'scripts',
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
        rec={'pid':child.pid,'identity':service.identity(child.pid),'role':role}
        service.write_json(r/'processes'/f'{role}.json',rec)
        print(json.dumps(rec),flush=True)
except BaseException:
    if (r/'processes/service.json').exists():service.stop()
    raise

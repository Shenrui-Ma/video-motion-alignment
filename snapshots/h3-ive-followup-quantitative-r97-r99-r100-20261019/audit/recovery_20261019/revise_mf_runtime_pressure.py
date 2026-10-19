"""Apply root-approved PSI telemetry after initial short-tracker admission."""
from pathlib import Path
import ast,hashlib,json,shutil,subprocess,os
H=Path(__file__).resolve().parent;PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['r111_long_0174_spatial','r108_short_0392','r110_short_0114_plain','r102_short_0126_native']:
 old=H/(name+'_capacity2');r=H/(name+'_capacity3');assert not r.exists()
 seal=json.loads((old/'SEAL.json').read_text())
 for rel,h in seal['files'].items():
  if rel!='audit/TARGET_CPU_CHECK.json':assert sha(old/rel)==h,rel
 shutil.copytree(old,r,ignore=shutil.ignore_patterns('actual_host41','CAPACITY_RESULTS.tar.gz'))
 (r/'SEAL.json').rename(r/'audit/CAPACITY2_SEAL.json')
 p=r/'scripts/mf_capacity.py';s=p.read_text();s=s.replace("assert isinstance(x,(int,float)) and 0<=x<=5,'startup memory pressure'","assert isinstance(x,(int,float)) and x>=0 and x<float('inf'),'invalid memory pressure'\n   if raw_required_gib==12:assert x<=5,'startup memory pressure'");ast.parse(s);p.write_text(s)
 p=r/'audit/run_authorized.py';s=p.read_text().replace('_capacity_attempt2','_capacity_attempt3');ast.parse(s);p.write_text(s)
 p=r/'configs/RUNTIME.json';v=json.loads(p.read_text());v['remote_root']=v['remote_root'].replace('_capacity2','_capacity3');p.write_text(json.dumps(v,indent=2)+'\n')
 p=r/'audit/CAPACITY_REVISION.json';v=json.loads(p.read_text());v['revision']='PSI checked at 12GiB initial admission; 8GiB post-import check records PSI and retains hard memory checks';v['prior_capacity2_seal_sha256']=sha(old/'SEAL.json');p.write_text(json.dumps(v,indent=2)+'\n')
 for rel,h in seal['files'].items():
  if rel.startswith(('cases/','runtime/')):assert sha(r/rel)==h
 result=json.loads(subprocess.check_output([PY,str(H/'check_mf_capacity_boundaries.py'),str(r)],text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')));(r/'audit/CAPACITY_BOUNDARY_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
 files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};(r/'SEAL.json').write_text(json.dumps({'schema':'ive-short-mf-capacity-v3','files':files},indent=2)+'\n')
 subprocess.run([PY,str(r/'audit/check_package.py'),str(r)],check=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES=''))
 print(json.dumps({'package':str(r),'seal':sha(r/'SEAL.json'),'input':sha(next((r/'cases').iterdir())/'INPUTS.json')}))

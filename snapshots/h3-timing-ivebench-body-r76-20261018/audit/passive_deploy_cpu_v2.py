"""Install exact R76 CPU bundles and verify. Starts no server or GPU process."""
import os,json,hashlib,subprocess,tarfile,time
from pathlib import Path
base=Path('/data3/researcher/h3_runs')
python='/data3/researcher/ComfyUI/.venv/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=base/'timing_ivebench_body_r76_20261018';c=base/'ivebench_body_metrics_r76_20261018'
a=p/'audit/seal_fixture_revision2';a.mkdir(exist_ok=True)
with tarfile.open(base/'r76_fixture_overlay_v2.tar.gz') as t:
 info=json.load(t.extractfile('audit/seal_fixture_revision2/OVERLAY.json'))
 for rel,h in info['before'].items():
  assert sha(p/rel)==h,'before SHA differs'
  dest=a/'before'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  with dest.open('xb') as f:f.write((p/rel).read_bytes())
 for member in t.getmembers():
  assert member.isfile() and '..' not in Path(member.name).parts and not Path(member.name).is_absolute()
  raw=t.extractfile(member).read();dest=p/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 for rel,h in info['after'].items():assert sha(p/rel)==h,'after SHA differs'
records=[]
def run(root,name,args):
 log=root/'audit'/name
 assert not log.exists(),'preserve prior CPU validation'
 with log.open('x') as f:result=subprocess.run([python]+args,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 records.append({'root':str(root),'command':[python]+args,'exit_code':result.returncode,'log_sha256':sha(log)})
 assert result.returncode==0,str(log)
run(p,'HOST41_PREFLIGHT_v2.json',['scripts/preflight.py'])
run(p,'HOST41_TESTS_v2.txt',['-m','unittest','discover','-s','tests','-v'])
run(c,'HOST41_MATERIALIZE_v2.json',['scripts/materialize_inputs.py','--producer-root',str(p)])
run(c,'HOST41_TESTS_v2.txt',['-m','unittest','discover','-s','tests','-v'])
for sid in ['short_0131','short_0178','short_0090','short_0055','short_0321']:
 run(c,sid+'_HOST41_CHECK_ONLY_v2.log',['scripts/track_one.py','--source',sid,'--method','source','--check-only'])
for root in [p,c]:
 manifest=root/('deploy_manifest.json' if root==p else 'CONSUMER_FREEZE.json')
 frozen=json.loads(manifest.read_text())['files']
 for rel,row in frozen.items():assert sha(root/rel)==(row['sha256'] if isinstance(row,dict) else row),rel
 record={'passed':True,'bundle_and_frozen_files_verified':True,'commands':records,'GPU_started':False,'producer_service_started':False,'launch_admission':False,'unix':time.time(),'manifest_sha256':sha(manifest)}
 with (root/'audit/HOST41_CPU_DEPLOYMENT_v2.json').open('x') as f:json.dump(record,f,indent=2)
print(json.dumps({'producer':str(p),'consumer':str(c),'passed':True,'GPU_started':False}))

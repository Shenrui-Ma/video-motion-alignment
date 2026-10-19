"""Install exact R76 CPU bundles and verify. Starts no server or GPU process."""
import os,json,hashlib,subprocess,tarfile,time
from pathlib import Path
base=Path('/data3/researcher/h3_runs')
python='/data3/researcher/ComfyUI/.venv/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def install(name,bundle,digest):
 root=base/name;archive=base/bundle
 assert sha(archive)==digest,'bundle SHA differs'
 root.mkdir(exist_ok=True)
 assert not (root/'processes/service.json').exists(),'existing producer service registration'
 with tarfile.open(archive) as t:
  for m in t.getmembers():
   assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
   p=root/m.name;p.parent.mkdir(parents=True,exist_ok=True);data=t.extractfile(m).read()
   if p.exists():assert not p.is_symlink() and p.read_bytes()==data,'existing deployed bytes differ'
   else:
    with p.open('xb') as f:f.write(data)
 for folder in ['audit','inputs','prepared','incoming','tracks','results','controls','preflight','logs','processes']:(root/folder).mkdir(exist_ok=True)
 return root
p=install('timing_ivebench_body_r76_20261018','r76_producer_cpu_bundle_20261018.tar.gz','e37bbd5d4d35117f00b6293dbe278f275bbd1e758161e6a2ce6fd21d3536d4bf')
c=install('ivebench_body_metrics_r76_20261018','r76_consumer_cpu_bundle_20261018.tar.gz','54e88a81990bf44281e3a68925eb67d3ddfcf9dd019068b6b33df2d9f42a99bb')
records=[]
def run(root,name,args):
 log=root/'audit'/name
 assert not log.exists(),'preserve prior CPU validation'
 with log.open('x') as f:result=subprocess.run([python]+args,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 records.append({'root':str(root),'command':[python]+args,'exit_code':result.returncode,'log_sha256':sha(log)})
 assert result.returncode==0,str(log)
run(p,'HOST41_PREFLIGHT.json',['scripts/preflight.py'])
run(p,'HOST41_TESTS.txt',['-m','unittest','discover','-s','tests','-v'])
run(c,'HOST41_MATERIALIZE.json',['scripts/materialize_inputs.py','--producer-root',str(p)])
run(c,'HOST41_TESTS.txt',['-m','unittest','discover','-s','tests','-v'])
for sid in ['short_0131','short_0178','short_0090','short_0055','short_0321']:
 run(c,sid+'_HOST41_CHECK_ONLY.log',['scripts/track_one.py','--source',sid,'--method','source','--check-only'])
for root in [p,c]:
 manifest=root/('deploy_manifest.json' if root==p else 'CONSUMER_FREEZE.json')
 frozen=json.loads(manifest.read_text())['files']
 for rel,row in frozen.items():assert sha(root/rel)==(row['sha256'] if isinstance(row,dict) else row),rel
 record={'passed':True,'bundle_and_frozen_files_verified':True,'commands':records,'GPU_started':False,'producer_service_started':False,'launch_admission':False,'unix':time.time(),'manifest_sha256':sha(manifest)}
 with (root/'audit/HOST41_CPU_DEPLOYMENT.json').open('x') as f:json.dump(record,f,indent=2)
print(json.dumps({'producer':str(p),'consumer':str(c),'passed':True,'GPU_started':False}))

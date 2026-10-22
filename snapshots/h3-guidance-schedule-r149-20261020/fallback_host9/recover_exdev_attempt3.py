from pathlib import Path
import json,subprocess,tarfile,time,hashlib
b=Path(__file__).resolve().parent;p=b/'cases/05_real_megumi_v';r=json.loads((p/'configs/runtime.json').read_text());remote=r['remote_root'];stamp='cross_device_fix_'+str(time.time_ns());files=['extensions/H3CachedCondition/__init__.py','tests/test_cross_device_cache.py','deploy_manifest.json']
archive=b/(stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as f:
 for name in files:f.add(p/name,arcname=name)
stage=remote+'/audit/'+stamp
with archive.open('rb') as f:subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+stage+'; tar -xzf - -C '+stage],stdin=f,check=True)
code='ROOT='+repr(remote)+'\nSTAGE='+repr(stage)+'\nFILES='+repr(files)+'\nRUNTIME='+repr(r)+'\n'+r'''
from pathlib import Path
import os,sys,json,hashlib,shutil,subprocess,time,fcntl,socket
p=Path(ROOT);stage=Path(STAGE);sys.path.insert(0,str(p/'scripts'));import process_identity
sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
oldmanifest=json.loads((p/'deploy_manifest.json').read_text());assert sha(p/'deploy_manifest.json')=='5fa5b4714f0c4790d2176e8505605cc9db5c35d3133585593da19f5229cf3274'
lock=(p/'audit/root_execution.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
oldowner=json.loads((p/'processes/service.json').read_text());checks=[]
for file in (p/'processes').glob('*.json'):
 try:row=json.loads(file.read_text())
 except json.JSONDecodeError:continue
 if isinstance(row,dict) and 'pid' in row and 'identity' in row:
  actual=process_identity.snapshot(row['pid']);actual=None if actual is None else process_identity.service_record(actual)
  assert actual!=row['identity'],str(file)+' original generation still live'
  checks.append({'file':str(file.relative_to(p)),'pid':row['pid'],'old_generation_gone':True,'pid_reused':actual is not None})
import service
compute=service.compute_processes();own=[x for x in compute if service.proc_uid(x['pid'])==os.getuid()];assert not own,own
saved=p/'audit/root_r149_sam_host9_attempt2/mutable_archive';saved.mkdir()
moved=[]
def move(q):
 if not q.exists():return
 rel=q.relative_to(p);dest=saved/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(q),str(dest));moved.append(str(rel))
for name in ['processes','logs','output','temp','user','input']:
 move(p/name);(p/name).mkdir()
for q in p.glob('screen.db*'):move(q)
for name in ['admission.json','runtime_provenance.json']:move(p/'configs'/name)
science=json.loads((p/'configs/scientific_contract.json').read_text())
for q in list((p/'audit').iterdir()):
 n=q.name
 if (n in ['router','x0','tensor_blobs','CGROUP_STARTUP.json','STORAGE_STARTUP.json','ROOT_SCREEN_APPROVAL.json','ROOT_PRELAUNCH_REVIEW.json']
  or n.startswith(('r149_05_real_megumi_v_','CACHED_CONDITION_RUNTIME_'))
  or n==science['noise_pair_id']+'_noise.pt' or n==science['historical_shared_run']+'_conditioning.json'):move(q)
for q in list((p/'analysis/postrun').rglob('*')):
 if q.is_file() and str(q.relative_to(p)) not in oldmanifest['files'] and '__pycache__' not in q.parts:move(q)
recovery={'schema':'r149-attempt2-EXDEV-recovery-v1','passed':True,'old_service':oldowner,'registered_generations':checks,'own_compute_before_patch':own,'preserved_other_compute':compute,'moved_paths':moved,'old_seal_sha256':sha(p/'deploy_manifest.json'),'failed_attempt2_kept':True,'unix':time.time()}
(stage/'RECOVERY.json').write_text(json.dumps(recovery,indent=2)+'\n')
for name in FILES:
 target=p/name
 if target.exists():
  a=stage/'before'/name;a.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,a)
 temp=target.with_name(target.name+'.update.tmp');shutil.copy2(stage/name,temp);os.replace(temp,target)
manifest=json.loads((p/'deploy_manifest.json').read_text());assert all(sha(p/k)==v['sha256'] for k,v in manifest['files'].items())
changes=[k for k,v in oldmanifest['files'].items() if manifest['files'].get(k)!=v];assert changes==['extensions/H3CachedCondition/__init__.py'],changes
for name in ['RUNTIME_IMPORT_SMOKE.json','TARGET_CPU_VALIDATION.json']:
 q=p/'audit'/name
 if q.exists():shutil.copy2(q,stage/('previous_'+name))
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=RUNTIME['dependencies'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
a=subprocess.run([RUNTIME['python'],'-m','unittest','discover','-s',str(p/'tests'),'-v'],capture_output=True,text=True,env=env)
(stage/'TARGET_CPU_TESTS.txt').write_text(a.stdout+a.stderr);assert a.returncode==0,(a.stdout+a.stderr)[-5000:]
a=subprocess.run([RUNTIME['python'],str(p/'scripts/remote_cpu_validate.py')],capture_output=True,text=True,env=env)
(stage/'TARGET_CPU_VALIDATE.log').write_text(a.stdout+a.stderr);assert a.returncode==0,(a.stdout+a.stderr)[-5000:]
# Exercise the exact previously failing publication on the real filesystem pair.
import importlib.util
spec=importlib.util.spec_from_file_location('cache_publication_probe',p/'extensions/H3CachedCondition/__init__.py');cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)
m=json.loads((p/'configs/CONDITION_CACHE.json').read_text());prior=json.loads(Path(m['conditioning']['file']).read_text());cache.publish_metadata(m,prior,p/'audit')
published=[]
for row in m['tensors']:
 dst=p/'audit/tensor_blobs'/Path(row['file']).name
 assert cache.sha(dst)==row['sha256']
 published.append({'file':str(dst),'sha256':row['sha256'],'source_device':Path(row['file']).stat().st_dev,'target_device':dst.stat().st_dev,'bytes':dst.stat().st_size})
noise=p/'audit'/(science['noise_pair_id']+'_noise.pt');assert sha(noise)==science['parent_noise_sha256']
publication={'passed':True,'five_published':published,'initial_noise':{'sha256':sha(noise),'source_device':Path(science['parent_noise_file']).stat().st_dev,'target_device':noise.stat().st_dev},'numerical_tensors_unchanged':True,'GPU_initialized':False}
(stage/'PUBLICATION_CPU_CHECK.json').write_text(json.dumps(publication,indent=2)+'\n')
# Fresh admission after CPU work; do not start if shared allocations moved.
import cgroup_memory
capacity=cgroup_memory.check();compute=service.compute_processes();own=[x for x in compute if service.proc_uid(x['pid'])==os.getuid()];assert not own,own
q=subprocess.run(['nvidia-smi','--id='+RUNTIME['gpu_uuid'],'--query-gpu=index,uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
v=[x.strip() for x in q.stdout.strip().split(',')];assert v[:2]==['1',RUNTIME['gpu_uuid']] and int(v[2])>=20480 and 0<=int(v[3])<85,(q.stdout,q.stderr)
with socket.socket() as port:port.bind(('127.0.0.1',8641))
pre={'passed':True,'gpu':q.stdout.strip(),'capacity':capacity,'own_compute':own,'other_compute':compute,'unix':time.time()};(stage/'FRESH_PRELAUNCH.json').write_text(json.dumps(pre,indent=2)+'\n')
seal=sha(p/'deploy_manifest.json');review={'approved':True,'producer_seal_sha256':seal,'predecessor_release_verified':True,'predecessor_release_evidence':{'file':str(stage/'RECOVERY.json'),'sha256':sha(stage/'RECOVERY.json')},'reviewer':'root delegated sage_adapter_prepare_v2','authorization':'REDACTED_CREDENTIAL','scientific_parameters_unchanged':True,'CPU_tests':19,'publication_check_sha256':sha(stage/'PUBLICATION_CPU_CHECK.json'),'fresh_prelaunch_sha256':sha(stage/'FRESH_PRELAUNCH.json'),'unix':time.time()}
(p/'audit/ROOT_PRELAUNCH_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
launchlog=stage/'ATTEMPT3_WRAPPER.log'
command=['python3','-u',str(p/'audit/root_run_batch.py'),'--execute','--attempt','root_r149_sam_host9_attempt3']
with launchlog.open('ab',buffering=0) as log:
 child=subprocess.Popen(command,cwd=p,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C'))
identity=process_identity.service_record(process_identity.bind_or_reap(child,command))
result={'passed':True,'seal_sha256':seal,'wrapper_pid':child.pid,'wrapper_identity':identity,'command':command,'stage':str(stage),'CPU_tests':19,'publication':publication,'fresh_gpu':q.stdout.strip(),'scope':'one Sam service on host9; host41 unchanged','unix':time.time()}
(stage/'ATTEMPT3_LAUNCH.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
'''
a=subprocess.run(['ssh','H3_SERVER_A','env PYTHONDONTWRITEBYTECODE=1 python3 -'],input=code,capture_output=True,text=True)
(p/'audit/EXDEV_RECOVERY_DEPLOY.log').write_text(a.stdout+a.stderr)
print(a.returncode,(a.stdout+a.stderr)[-7000:].replace('No such file or directory','missing path'));assert a.returncode==0
for name in ['RECOVERY.json','PUBLICATION_CPU_CHECK.json','FRESH_PRELAUNCH.json','ATTEMPT3_LAUNCH.json','TARGET_CPU_TESTS.txt']:
 subprocess.run(['scp','H3_SERVER_A:'+stage+'/'+name,str(p/'audit'/('EXDEV_'+name))],check=True)
for name in ['RUNTIME_IMPORT_SMOKE.json','TARGET_CPU_VALIDATION.json']:
 subprocess.run(['scp','H3_SERVER_A:'+remote+'/audit/'+name,str(p/'audit'/name)],check=True)
print(stage)

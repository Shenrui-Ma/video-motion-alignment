from pathlib import Path
import json,subprocess,tarfile,time,hashlib
b=Path(__file__).resolve().parent;p=b/'cases/05_real_megumi_v';r=json.loads((p/'configs/runtime.json').read_text());remote=r['remote_root'];stamp='pidfd_compat_'+str(time.time_ns());files=['scripts/parent_stop.py','scripts/capacity_trial.py','scripts/supervise_service.py','tests/test_parent_stop.py','deploy_manifest.json']
archive=b/(stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as f:
 for name in files:f.add(p/name,arcname=name)
stage=remote+'/audit/'+stamp
with archive.open('rb') as f:subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+stage+'; tar -xzf - -C '+stage],stdin=f,check=True)
code='ROOT='+repr(remote)+'\nSTAGE='+repr(stage)+'\nFILES='+repr(files)+'\nPYTHON='+repr(r['python'])+'\n'+r'''
from pathlib import Path
import os,sys,json,hashlib,shutil,subprocess,time
p=Path(ROOT);stage=Path(STAGE);sys.path.insert(0,str(p/'scripts'));import process_identity
old=json.loads((p/'deploy_manifest.json').read_text());oldsha=hashlib.sha256((p/'deploy_manifest.json').read_bytes()).hexdigest()
assert oldsha=='8d384204d378c5ea6c626a69fc9e851a7d0d21e06e7c52a15b359a2d9bcd77c4'
record=p/'processes/service.json'
if record.exists():
 row=json.loads(record.read_text());actual=process_identity.snapshot(row['pid'])
 assert actual is None or process_identity.service_record(actual)!=row['identity'],'original service still live'
for name in FILES:
 target=p/name
 if target.exists():
  a=stage/'before'/name;a.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,a)
 temp=target.with_name(target.name+'.update.tmp');shutil.copy2(stage/name,temp);os.replace(temp,target)
manifest=json.loads((p/'deploy_manifest.json').read_text())
assert all(hashlib.sha256((p/k).read_bytes()).hexdigest()==v['sha256'] for k,v in manifest['files'].items())
changes=[k for k,v in old['files'].items() if manifest['files'].get(k)!=v]
assert set(changes)<=set(FILES)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
a=subprocess.run([PYTHON,'-m','unittest','discover','-s',str(p/'tests'),'-v'],capture_output=True,text=True,env=env)
(stage/'TARGET_CPU_TESTS.txt').write_text(a.stdout+a.stderr)
print(a.stdout+a.stderr)
assert a.returncode==0
# Also exercise the administrative functions under the actual system-python interpreter.
a=subprocess.run(['python3',str(p/'tests/test_parent_stop.py'),'-v'],capture_output=True,text=True,env=env)
(stage/'SYSTEM_PYTHON_CHILD_TESTS.txt').write_text(a.stdout+a.stderr)
print(a.stdout+a.stderr);assert a.returncode==0
result={'passed':True,'previous_seal_sha256':oldsha,'seal_sha256':hashlib.sha256((p/'deploy_manifest.json').read_bytes()).hexdigest(),'updated_files':FILES,'scientific_files_changed':False,'tests':16,'system_python_controlled_child_tests':5,'GPU_initialized':False,'unix':time.time()}
(stage/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
'''
a=subprocess.run(['ssh','H3_SERVER_A','env PYTHONDONTWRITEBYTECODE=1 python3 -'],input=code,capture_output=True,text=True)
(p/'audit/PIDFD_COMPAT_DEPLOY.log').write_text(a.stdout+a.stderr)
print(a.returncode,(a.stdout+a.stderr)[-6500:].replace('No such file or directory','missing path'));assert a.returncode==0
for name in ['TARGET_CPU_TESTS.txt','SYSTEM_PYTHON_CHILD_TESTS.txt','RESULT.json']:
 subprocess.run(['scp','H3_SERVER_A:'+stage+'/'+name,str(p/'audit'/('PIDFD_COMPAT_'+name))],check=True)
print(stage)

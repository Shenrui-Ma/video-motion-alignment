from pathlib import Path
import json,shutil,subprocess,hashlib,shlex
P=Path('/Users/researcher/DevProjects/h3-guidance-schedule-r150-20261021')
source=P/'host9/cases/short_0274/scripts/parent_stop.py'
for cid in ['musk05','sam07']:
 root=P/'host9/cases'/cid
 archive=root/'producer/PRE_PARENT_STOP_FIX';archive.mkdir(exist_ok=False)
 shutil.copy2(root/'deploy_manifest.json',archive/'deploy_manifest.json')
 shutil.copy2(root/'scripts/cpu_runtime_smoke.py',archive/'cpu_runtime_smoke.py')
 shutil.copy2(source,root/'scripts/parent_stop.py')
 p=root/'scripts/cpu_runtime_smoke.py';s=p.read_text();needle=" require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','smoke must hide CUDA')";assert s.count(needle)==1;s=s.replace(needle,needle+"\n import supervise_service, parent_stop  # exact runtime supervisor dependencies, no launch")
 compile(s,str(p),'exec');p.write_text(s)
 subprocess.run(['python3','scripts/execution_gate.py','seal'],cwd=root,check=True)
 rt=json.loads((root/'configs/runtime.json').read_text());remote=rt['remote_root']
 payload={rel:(root/rel).read_text() for rel in ['scripts/parent_stop.py','scripts/cpu_runtime_smoke.py','deploy_manifest.json']}
 code='''from pathlib import Path
import json,sys,hashlib,time
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts'));import service
assert not (root/'processes/service.json').exists(), 'unexpected registered GPU service'
if (root/'audit/ATTEMPT1_LAUNCH.json').exists():
 old=json.loads((root/'audit/ATTEMPT1_LAUNCH.json').read_text());assert service.current_identity(old['pid'])!=old['identity']
for p in (root/'audit/x0').glob('*'):raise AssertionError('unexpected sampler output '+str(p))
archive=root/'audit/PRE_PARENT_STOP_FIX';archive.mkdir(exist_ok=False)
(root/'deploy_manifest.json').rename(archive/'deploy_manifest.json')
(root/'scripts/cpu_runtime_smoke.py').rename(archive/'cpu_runtime_smoke.py')
for rel in ['audit/ROOT_PRELAUNCH_REVIEW.json','audit/ROOT_SCREEN_APPROVAL.json','audit/ATTEMPT1_LAUNCH.json','audit/TARGET_CPU_VALIDATION.json','audit/RUNTIME_IMPORT_SMOKE.json','configs/admission.json']:
 p=root/rel
 if p.exists():q=archive/rel;q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)
for folder in ['logs','processes']:
 for p in (root/folder).iterdir():
  q=archive/folder/p.name;q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)
for rel,value in json.loads(sys.stdin.read()).items():(root/rel).write_text(value)
print(json.dumps({'root':str(root),'old_runtime_archived':str(archive),'seal':hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest()}))
'''
 subprocess.run(['ssh','H3_SERVER_A','python3 -c '+shlex.quote(code)+' '+shlex.quote(remote)],input=json.dumps(payload).encode(),check=True)
 command='cd '+shlex.quote(remote)+" && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="+shlex.quote(rt['dependencies'])+' '+shlex.quote(rt['python'])+' scripts/remote_cpu_validate.py'
 with (root/'producer/CPU_PARENT_STOP_FIX.log').open('x') as f:subprocess.run(['ssh','H3_SERVER_A',command],stdout=f,stderr=subprocess.STDOUT,check=True)
 for rel in ['audit/TARGET_CPU_VALIDATION.json','audit/RUNTIME_IMPORT_SMOKE.json']:(root/rel).write_bytes(subprocess.check_output(['ssh','H3_SERVER_A','cat '+shlex.quote(remote+'/'+rel)]))
 print(cid,hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest(),flush=True)
# Future builders carry the runtime dependency with the existing host9 supervisor.
p=P/'producer/build_dance_case.py';s=p.read_text();needle=" cp(CACHED/'extensions/H3CachedCondition/__init__.py',root/'extensions/H3CachedCondition/__init__.py')";assert s.count(needle)==1;s=s.replace(needle," if args.host9:cp(admin/'scripts/parent_stop.py',root/'scripts/parent_stop.py')\n"+needle);p.write_text(s)

"""Collect only completed, released evaluation results and verify every byte."""
from pathlib import Path
import hashlib, json, shlex, subprocess, sys, tarfile

here=Path(__file__).resolve().parent
case=sys.argv[1]
assert case == 'r102_short_0092_native'
root=here/case
remote=json.loads((root/'configs/RUNTIME.json').read_text())['remote_root']
code="""
from pathlib import Path
import json,hashlib,tarfile,subprocess
r=Path(REMOTE)
c=r/'cases'/CASE
b=r/'audit'/('actual_'+CASE+'_attempt1')
complete=json.loads((b/'COMPLETE.json').read_text())
assert complete['passed'] is True and complete['all_trackers_released'] is True
nv={int(x.strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()}
for role in ['source','native']:
 d=json.loads((b/role/'RELEASED.json').read_text())
 assert d['process_absent'] and d['own_cuda_absent'] and d['returncode']==0
 assert not Path('/proc/'+str(d['pid'])).exists() and d['pid'] not in nv
files=[]
for p in [b,c/'controls',c/'tracks',c/'results',c/'preflight']:
 files.extend(x for x in p.rglob('*') if x.is_file())
files.extend([r/'audit/PASSIVE_DEPLOYMENT.json',c/'INPUTS.json',c/'SPEC.json'])
manifest={str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files}
(r/'audit/RETURN_SHA.json').write_text(json.dumps(manifest,indent=2))
with tarfile.open(r/'audit/ACTUAL_RESULTS.tar.gz','w:gz') as t:
 for x in files:t.add(x,arcname=str(x.relative_to(r)))
 t.add(r/'audit/RETURN_SHA.json',arcname='audit/RETURN_SHA.json')
print(json.dumps({'passed':True,'files':len(files),'all_trackers_released':True}))
""".replace('REMOTE',repr(remote)).replace('CASE',repr(case))
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B','python3 - <<\'PY\'\n'+code+'\nPY'],check=True,capture_output=True,text=True)
print(p.stdout.strip())
archive=root/'ACTUAL_RESULTS.tar.gz'
subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B:'+remote+'/audit/ACTUAL_RESULTS.tar.gz',str(archive)],check=True)
dest=root/'actual_host41'
dest.mkdir(exist_ok=False)
with tarfile.open(archive) as t:t.extractall(dest,filter='data')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((dest/'audit/RETURN_SHA.json').read_text())
for rel,h in manifest.items():assert sha(dest/rel)==h,rel
c=dest/'cases'/case
scores={role:json.loads((c/'results'/f'{role}.json').read_text()) for role in ('native',)}
result={'case':case,'benchmark':'IVEBench','native':scores['native']['motion_fidelity'],'algorithm_benefit_comparison':False,'task_status':'PARTIAL; small desk and shelf plants retained','valid_frames':scores['native']['valid_frames'],'fps':24,'verified_returned_files':len(manifest),'scores':{role:{'file':str(c/'results'/f'{role}.json'),'sha256':sha(c/'results'/f'{role}.json')} for role in scores},'tracks':{}}
for role in ('source','native'):
 report=json.loads((c/'tracks'/role/'REPORT.json').read_text())
 released=json.loads((dest/'audit'/('actual_'+case+'_attempt1')/role/'RELEASED.json').read_text())
 result['tracks'][role]={k:report.get(k) for k in ('pid','tracking_seconds','wall_seconds','peak_reserved_bytes','tracks_shape','torch_version','cuda_version')}
 result['tracks'][role]['released']=released
assert scores['native']['actual_gate_sha256']==json.loads((c/'INPUTS.json').read_text())['gate_sha256']
assert scores['native']['case_inputs_sha256']==sha(c/'INPUTS.json')
result['scope']='Official MF only; basic task acceptance and physical event timing are recorded separately.'
(root/'RESULT_VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))

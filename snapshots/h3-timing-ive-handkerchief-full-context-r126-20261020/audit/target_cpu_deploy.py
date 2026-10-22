import hashlib,json,pathlib,shutil,socket,subprocess,sys,tarfile,time
r=pathlib.Path('/home/researcher/h3_runs/timing_ive_handkerchief_full_context_r126_20261020')
assert not r.exists(), 'remote target already exists; inspect before reuse'
r.mkdir()
with tarfile.open('/home/researcher/h3_runs/r126_deployment_payload.tar.gz','r:gz') as t:
 for m in t.getmembers():
  assert not pathlib.Path(m.name).is_absolute() and '..' not in pathlib.Path(m.name).parts
 t.extractall(r)
for d in ['input','output','temp','user','processes','logs','audit/router','audit/x0','custom_nodes']:(r/d).mkdir(parents=True,exist_ok=True)
manifest=json.loads((r/'deploy_manifest.json').read_text())
for f,row in manifest['files'].items():assert hashlib.sha256((r/f).read_bytes()).hexdigest()==row['sha256'],f
import torch
old=pathlib.Path('/home/researcher/h3_runs/timing_ive_official_prompt_r120_20261019/audit/r120_long_0059_seed2026101701_noise.pt')
new=r/'audit/r126_long_0059_seed2026101701_noise.pt'
shutil.copyfile(old,new)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(old)==sha(new)
v=torch.load(new,map_location='cpu',weights_only=True)
e=json.loads((r/'audit/PROMPT_CONTROL_BINDING.json').read_text())['raw_noise_expected']
assert v['signature']==e['signature']
hashes=[hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest() for t in v['tensors']]
assert hashes==[x['sha256'] for x in e['actual_noise_streams']]
noise={'passed':True,'source':str(old),'target':str(new),'file_sha256':sha(new),'signature':v['signature'],'actual_tensor_sha256':hashes,'unix':time.time()}
(r/'audit/ACTUAL_R120_NOISE_REUSE.json').write_text(json.dumps(noise,indent=2)+'\n')
result=subprocess.run([sys.executable,'scripts/preflight.py'],cwd=r,text=True,capture_output=True)
(r/'audit/TARGET_PREFLIGHT.txt').write_text(result.stdout+result.stderr)
assert result.returncode==0,result.stderr
result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=r,text=True,capture_output=True)
(r/'audit/TARGET_TESTS.txt').write_text(result.stdout+result.stderr)
assert result.returncode==0,result.stderr
s=socket.socket();assert s.connect_ex(('127.0.0.1',8598))!=0;s.close()
ready={'passed':True,'files':len(manifest['files']),'seal_sha256':sha(r/'deploy_manifest.json'),'noise_sha256':sha(r/'audit/ACTUAL_R120_NOISE_REUSE.json'),'preflight':True,'tests':True,'port8598_empty':True,'GPU_started':False,'unix':time.time()}
(r/'audit/TARGET_CPU_READY.json').write_text(json.dumps(ready,indent=2)+'\n')
print(json.dumps(ready));print(result.stderr[-500:])

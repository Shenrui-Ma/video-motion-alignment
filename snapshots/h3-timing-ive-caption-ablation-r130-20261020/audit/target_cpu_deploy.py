import hashlib,json,pathlib,shutil,socket,subprocess,sys,tarfile,time
r=pathlib.Path('/home/researcher/h3_runs/timing_ive_caption_ablation_r130_20261020');assert not r.exists();r.mkdir()
with tarfile.open('/home/researcher/h3_runs/r130_deployment_payload.tar.gz','r:gz') as t:
 for m in t.getmembers():assert not pathlib.Path(m.name).is_absolute() and '..' not in pathlib.Path(m.name).parts
 t.extractall(r)
for d in ['input','output','temp','user','processes','logs','audit/router','audit/x0','custom_nodes']:(r/d).mkdir(parents=True,exist_ok=True)
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((r/'deploy_manifest.json').read_text())
for f,row in manifest['files'].items():assert H(r/f)==row['sha256'],f
import torch
plan=json.loads((r/'design/NOISE_REUSE_PLAN.json').read_text());old=pathlib.Path(plan['source_remote']);new=pathlib.Path(plan['target_remote']);assert not new.exists();shutil.copyfile(old,new);assert H(old)==H(new)
v=torch.load(new,map_location='cpu',weights_only=True);e=plan['actual_noise_receipt'];assert v['signature']==e['signature'];hashes=[hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest() for t in v['tensors']];assert hashes==[x['sha256'] for x in e['actual_noise_streams']]
noise={'passed':True,'source':str(old),'target':str(new),'file_sha256':H(new),'signature':v['signature'],'actual_tensor_sha256':hashes,'unix':time.time()};(r/'audit/ACTUAL_R124_NOISE_REUSE.json').write_text(json.dumps(noise,indent=2)+'\n')
for name,cmd in [('PREFLIGHT',[sys.executable,'scripts/preflight.py']),('TESTS',[sys.executable,'-m','unittest','discover','-s','tests'])]:
 q=subprocess.run(cmd,cwd=r,text=True,capture_output=True);(r/'audit'/('TARGET_'+name+'.txt')).write_text(q.stdout+q.stderr);assert q.returncode==0,q.stderr
s=socket.socket();assert s.connect_ex(('127.0.0.1',8606))!=0;s.close()
ready={'passed':True,'files':len(manifest['files']),'seal_sha256':H(r/'deploy_manifest.json'),'noise_receipt_sha256':H(r/'audit/ACTUAL_R124_NOISE_REUSE.json'),'preflight':True,'tests':True,'port8606_empty':True,'GPU_started':False,'unix':time.time()};(r/'audit/TARGET_CPU_READY.json').write_text(json.dumps(ready,indent=2)+'\n');print(json.dumps(ready))

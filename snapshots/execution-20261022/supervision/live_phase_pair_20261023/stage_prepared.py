"""Prepare only isolated small runtime files; never import torch or start a service."""
from pathlib import Path
import json,hashlib,subprocess
D=Path(__file__).parent;E=D.parents[1];OLD=E/'supervision/signed_phase_replay_resource_20261023';P=E/'innovation/signed_phase_calibration_20261023/replay_live_pair';R='/data/research-user/h3_inference_20261023/live_phase_pair_20261023'
files={}
for folder in ['runtime_scripts','runtime_sources']:
 for p in (OLD/folder).rglob('*.py'):
  key=('scripts/' if folder=='runtime_scripts' else 'custom_nodes/')+str(p.relative_to(OLD/folder));b=p.read_bytes()
  if p.name=='manage_service.py':
   s=b.decode().replace('PORT=8679','PORT=8685');a=s.index("'--whitelist-custom-nodes'");z=s.index("'--input-directory'",a)
   s=s[:a]+"'--whitelist-custom-nodes','ComfyUI-KJNodes','H3Study','H3TrustedConditionCache','H3LivePhase',"+s[z:]
   s=s.replace("st=Path('/proc')/str(r['pid']);return st.stat().st_uid==os.getuid() and (st/'stat').read_text().split()[21]==r['start_ticks'] and str(ROOT).encode() in (st/'cmdline').read_bytes()","st=Path('/proc')/str(r['pid']);parts=(st/'stat').read_text().rsplit(')',1)[1].split();return st.stat().st_uid==os.getuid() and parts[19]==str(r['start_ticks']) and parts[0]!='Z' and str(ROOT).encode() in (st/'cmdline').read_bytes()")
   s=s.replace("  result=stop(r)\n  if not result['stopped']:raise RuntimeError('Unresponsive own service could not be stopped')","  raise RuntimeError('Existing service needs identity/status review; no automatic restart')")
   compile(s,'manage_service','exec');b=s.encode()
  files[key]=b
# Draft contracts/graphs are tagged PREPARED_ONLY and must be re-pinned after READY.
for p in (P/'plans').glob('*.json'):files['review_staging/'+p.name]=p.read_bytes()
files['RESOURCE_PLAN.json']=(D/'RESOURCE_PLAN.json').read_bytes()
# Copy exact validated policy schema rather than guessing bootstrap keys.
code=r'''
from pathlib import Path
import sys,json,hashlib,os,time
r=Path(ROOT);old=r.parent/'signed_phase_calibration_20261023';data=json.load(sys.stdin)
assert not (r/'STARTED.json').exists() and not (r/'SUBMISSION_INTENT.json').exists()
r.mkdir(exist_ok=True)
for k,v in data.items():
 p=r/k;p.parent.mkdir(parents=True,exist_ok=True);b=bytes.fromhex(v);p.write_bytes(b);assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(b).hexdigest()
for name in ['gpu.json','shared_gpu_authorization.json','MODEL_REHASH.json']:
 (r/name).write_bytes((old/name).read_bytes())
policy=json.loads((r/'shared_gpu_authorization.json').read_text());policy['scope']='independent live0358 native then global_weak control pair; prepare only until matched READY review and root release';policy['maximum_attempts']=1;(r/'shared_gpu_authorization.json').write_text(json.dumps(policy,indent=2)+'\n')
link=r/'custom_nodes/ComfyUI-KJNodes'
if not link.exists():link.symlink_to((old/'custom_nodes/ComfyUI-KJNodes').resolve())
model=json.loads((r/'MODEL_REHASH.json').read_text());st=Path(model['path']).stat();assert (st.st_ino,st.st_mtime_ns,st.st_size)==(model['inode'],model['mtime_ns'],model['bytes'])
vaes=[]
for name in ['minimax_h3_video_vae_fp16.safetensors','minimax_h3_audio_vae_fp32.safetensors']:
 p=r.parent/'models/vae'/name;assert p.is_file(),str(p);s=p.stat();vaes.append({'path':str(p),'bytes':s.st_size,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns})
out={'status':'prepared_only_not_submitted','time':time.time(),'root':str(r),'files':{k:hashlib.sha256((r/k).read_bytes()).hexdigest() for k in data},'reused_policy':json.loads((r/'shared_gpu_authorization.json').read_text()),'model_stat_matches_last_full_sha':True,'vaes_present':vaes}
(r/'PREPARED_ONLY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh','H3_HOST_RTX4090','python3 -c '+__import__('shlex').quote(code)],input=json.dumps({k:v.hex() for k,v in files.items()}),text=True,capture_output=True,timeout=60);p.check_returncode();result=json.loads(p.stdout);(D/'STAGED_PREPARED.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'files':len(result['files']),'vaes':result['vaes_present']}))

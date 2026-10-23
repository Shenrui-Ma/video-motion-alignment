"""Activate exactly the independently reviewed pair under unique ownership."""
from pathlib import Path
import hashlib,json,subprocess,shlex,time
D=Path(__file__).parent;E=D.parents[1];P=E/'innovation/signed_phase_calibration_20261023/replay_live_pair';S=E/'innovation/adaptive_strength_20261023/review_0837/LIVE_PAIR_SIGNOFF.json';R='/data/research-user/h3_inference_20261023/live_phase_pair_20261023';H='H3_HOST_RTX4090';sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((D/'ROOT_RELEASE.json').read_bytes())=='ea1808a044576138dba75ce2b0aaca2a3c630c9aac92298ccf8e84b64fb37827'
assert sha(S.read_bytes())=='d85d16490ce8df40dc46ca1a5aae077ef80ab97724b82056ec0dfcb73a1aa4d0'
assert sha((P/'READY.json').read_bytes())=='7e562c75a3e89a1c7cda0274fd421f4ddff7d478b2cf40c0ffe3f2e22096ed0a'
assert json.loads((D/'DEPLOY_CPU_READY.json').read_text())['passed'] and json.loads((D/'PLANS_CHECK.json').read_text())['passed']
assets=json.loads((D/'DEPLOY_ASSETS.json').read_text())
release={'scope':'only_live0358_native_and_global_weak','cohort':'phase_calibration_pair','science_ready_sha256':sha((P/'READY.json').read_bytes()),'signoff_sha256':sha(S.read_bytes()),'root_release_sha256':sha((D/'ROOT_RELEASE.json').read_bytes()),'assets':assets,'maximum_attempts_each':1,'time':time.time()}
files={'INDEPENDENT_SIGNOFF.json':S.read_bytes().hex(),'ROOT_RELEASE.json':(D/'ROOT_RELEASE.json').read_bytes().hex(),'LAUNCH_RELEASE.json':(json.dumps(release,indent=2)+'\n').encode().hex()}
code=r'''
from pathlib import Path
import json,sys,fcntl,socket,subprocess,hashlib,os,time,urllib.request
r=Path(ROOT);data=json.load(sys.stdin)
with (r/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not (r/'STARTED.json').exists() and not (r/'jobs').exists()
 for n,h in data['release']['assets'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
 # Match generation and UID, including old passive and every task-local video service.
 live=[]
 for p in r.parent.glob('*/service.json'):
  d=json.loads(p.read_text());q=Path('/proc')/str(d.get('pid',0))
  if not q.exists():continue
  st=(q/'stat').read_text().rsplit(')',1)[1].split()
  if st[19]==str(d.get('start_ticks')) and st[0]!='Z' and q.stat().st_uid==1016:live.append({'file':str(p),'pid':d['pid'],'gpu_uuid':d.get('gpu_uuid')})
 assert not [x for x in live if x['gpu_uuid']=='GPU-REPLACE-WITH-DEVICE-UUID'],live
 policy=json.loads((r/'shared_gpu_authorization.json').read_text());assert (policy['minimum_free_mib'],policy['torch_allocator_cap_gib'],policy['reserve_vram_gib'],policy['post_context_external_headroom_mib'])==(22500,19.5,6,1536)
 rows=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
 row=next(x for x in rows.splitlines() if policy['gpu_uuid'] in x);assert float(row.split(',')[2])>=22500,row
 gpu_lock=open('/tmp/h3-video-inference-research-user-'+policy['gpu_uuid']+'.lock','a');fcntl.flock(gpu_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);gpu_lock.close()
 with socket.socket() as sock:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',8685))
 model=json.loads((r/'MODEL_REHASH.json').read_text());st=Path(model['path']).stat();assert (st.st_ino,st.st_mtime_ns,st.st_size)==(model['inode'],model['mtime_ns'],model['bytes'])
 other=[]
 for line in subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).splitlines():
  if policy['gpu_uuid'] not in line:continue
  parts=[z.strip() for z in line.split(',')];q=Path('/proc')/parts[1];st=(q/'stat').read_text().rsplit(')',1)[1].split();other.append({'pid':int(parts[1]),'uid':q.stat().st_uid,'start_ticks':st[19],'used_memory_mib':parts[2]})
 for n,b in data['files'].items():(r/n).write_bytes(bytes.fromhex(b))
 (r/'logs').mkdir(exist_ok=True)
 with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(['python3','-u',str(r/'scripts/live_pair_supervisor.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 st=(Path('/proc')/str(p.pid)/'stat').read_text().rsplit(')',1)[1].split()
 rec={'schema':'h3-live-pair-owner-receipt-v1','owner':'host81_live_phase_pair','host':'H3_HOST_RTX4090','root':str(r),'cohort':'phase_calibration_pair','pid':p.pid,'uid':os.getuid(),'start_ticks':st[19],'time':time.time(),'gpu':row,'protected_other_processes':other,'jobs':[j['id'] for j in json.loads((r/'jobs.json').read_text())['jobs']],'maximum_attempts_each':1,'science_ready_sha256':data['release']['science_ready_sha256'],'root_release_sha256':data['release']['root_release_sha256']}
 (r/'STARTED.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh',H,'python3 -c '+shlex.quote(code)],input=json.dumps({'files':files,'release':release}),text=True,capture_output=True,timeout=60);p.check_returncode();out=json.loads(p.stdout);(D/'STARTED.json').write_text(json.dumps(out,indent=2)+'\n');(D/'LAUNCH_RELEASE.json').write_text(json.dumps(release,indent=2)+'\n');print(json.dumps(out))

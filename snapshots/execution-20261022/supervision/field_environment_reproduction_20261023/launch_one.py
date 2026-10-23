"""Activate one independently reviewed field reproduction under unique ownership."""
from pathlib import Path
import hashlib,json,subprocess,shlex,time
D=Path(__file__).parent;E=D.parents[1];P=E/'innovation/feature_gain_field';S=D/'INDEPENDENT_SIGNOFF.json';R='/data/research-user/h3_inference_20261023/field_environment_reproduction_20261023';H='H3_HOST_CONFIGURE_LOCALLY';sha=lambda b:hashlib.sha256(b).hexdigest()
# ROOT_RELEASE and copied independent signoff are pinned by an explicit activation authorization.
authorization=json.loads((D/'ACTIVATION_AUTHORIZATION.json').read_text())
for name in ['ROOT_RELEASE.json','INDEPENDENT_SIGNOFF.json','READY.json']:
 assert sha((D/name).read_bytes())==authorization['file_sha256'][name],name
ready=json.loads((D/'READY.json').read_text())
for n,h in ready['files_sha256'].items():assert sha((D/n).read_bytes())==h,n
assert authorization['scope']=='only_original_field0358_same_live_environment'
assert json.loads((D/'DEPLOY_CPU_READY.json').read_text())['passed']
assets=json.loads((D/'DEPLOY_ASSETS.json').read_text())
release={'scope':'only_original_field0358_same_live_environment','cohort':'field_environment_reproduction','science_ready_sha256':sha((P/'READY.json').read_bytes()),'signoff_sha256':sha(S.read_bytes()),'root_release_sha256':sha((D/'ROOT_RELEASE.json').read_bytes()),'assets':assets,'maximum_attempts_each':1,'time':time.time()}
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
 row=next(x for x in rows.splitlines() if policy['gpu_uuid'] in x) # CPU supervisor waits for minimum22500; no model is loaded here
 gpu_lock=open('/tmp/h3-video-inference-research-user-'+policy['gpu_uuid']+'.lock','a');fcntl.flock(gpu_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);gpu_lock.close()
 with socket.socket() as sock:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',8687))
 model=json.loads((r/'MODEL_REHASH.json').read_text());st=Path(model['path']).stat();assert (st.st_ino,st.st_mtime_ns,st.st_size)==(model['inode'],model['mtime_ns'],model['bytes'])
 other=[]
 for line in subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).splitlines():
  if policy['gpu_uuid'] not in line:continue
  parts=[z.strip() for z in line.split(',')];q=Path('/proc')/parts[1];st=(q/'stat').read_text().rsplit(')',1)[1].split();other.append({'pid':int(parts[1]),'uid':q.stat().st_uid,'start_ticks':st[19],'used_memory_mib':parts[2]})
 for n,b in data['files'].items():(r/n).write_bytes(bytes.fromhex(b))
 sys.path.insert(0,str(r/'scripts'));from field_gate import verify_inputs;verify_inputs(r)
 (r/'logs').mkdir(exist_ok=True)
 with (r/'logs/supervisor.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(['python3','-u',str(r/'scripts/field_supervisor.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 st=(Path('/proc')/str(p.pid)/'stat').read_text().rsplit(')',1)[1].split()
 rec={'schema':'h3-field-environment-owner-receipt-v1','owner':'host81_field_environment_reproduction','host':'H3_HOST_CONFIGURE_LOCALLY','root':str(r),'cohort':'field_environment_reproduction','pid':p.pid,'uid':os.getuid(),'start_ticks':st[19],'time':time.time(),'gpu':row,'protected_other_processes':other,'jobs':[j['id'] for j in json.loads((r/'jobs.json').read_text())['jobs']],'maximum_attempts_each':1,'science_ready_sha256':data['release']['science_ready_sha256'],'root_release_sha256':data['release']['root_release_sha256']}
 (r/'STARTED.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh','-o','ConnectTimeout=20','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=1',H,'python3 -'],input=code.replace('data=json.load(sys.stdin)', 'data='+repr({'files':files,'release':release})),text=True,capture_output=True,timeout=60);(D/'LAST_LAUNCH_TRANSPORT.json').write_text(json.dumps({'time':time.time(),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n');p.check_returncode();out=json.loads(p.stdout);(D/'STARTED.json').write_text(json.dumps(out,indent=2)+'\n');(D/'LAUNCH_RELEASE.json').write_text(json.dumps(release,indent=2)+'\n');print(json.dumps(out))

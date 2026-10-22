"""Root-authorized four-arm schedule launch after actual MF release."""
import hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service,cgroup_memory
SEAL='3c2740dae3c8637f0c4813a20c8fb718cfb1f536ac2d9b5feadb07f3c2a1f997'
PARTIAL='020b46eb67db9a286c95de99cad193b23673d40483027d95df9f48c915d3301e'
ATTEMPT='root_r150_long0039_host41_attempt1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
require(sys.argv[1:]==['--execute'],'explicit execution flag required')
require(ROOT==Path(service.RUNTIME['remote_root']),'actual target root required')
require(sha(ROOT/'deploy_manifest.json')==SEAL,'approved producer seal differs')
for rel,item in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(ROOT/rel)==item['sha256'],'sealed file changed: '+rel)
require(read(ROOT/'audit/TARGET_CPU_VALIDATION.json')['passed'],'CPU validation incomplete')
p=Path('/data4/researcher/h3_runs/guidance_schedule_mf_r149_20261020/short_0358/audit/FINAL_RELEASE_VERIFIED.json');release=read(p)
require(sha(p)==PARTIAL,'prior MF release differs')
require(release['passed'] and release['exact_processes_absent'] and release['exact_CUDA_allocations_absent'] and release['fresh_task_cuda_absent'],'MF release incomplete')
for item in release['wrapper_identities']+release['tracker_identities']:
 actual=service.external_identity(item['pid'])
 require(actual is None or str(actual.get('start_ticks'))!=str(item['start_ticks']) or actual.get('uid')!=item['uid'],'prior MF generation remains')
peer=read(ROOT/'configs/readonly_peer.json')
require(peer['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'peer boot changed')
require(service.external_identity(peer['pid'])==peer['identity'],'peer generation changed')
require(peer['gpu_uuid']!=service.GPU,'peer uses selected GPU')
rows=service.compute_processes()
for row in rows:
 if service.proc_uid(row['pid'])==os.getuid():
  require(row['pid']==peer['pid'] and row['gpu_uuid']==peer['gpu_uuid'] and service.external_identity(row['pid'])==peer['identity'],'unexpected own compute identity '+str(row['pid']))
own_video=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdecimal():continue
 pid=int(proc.name)
 if service.proc_uid(pid)!=os.getuid() or pid==peer['pid']:continue
 actual=service.current_identity(pid)
 if actual and ('/scripts/service_entry.py' in actual['cmdline'] or 'ComfyUI/main.py' in actual['cmdline']):own_video.append({'pid':pid,'identity':actual})
require(not own_video,'another experimental video service is live')
row=subprocess.run(['nvidia-smi','-i','6','--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True,timeout=15).stdout.strip()
parts=[x.strip() for x in row.split(',')]
require(parts[0]=='6' and parts[1]==service.GPU and int(parts[2])>=40960,'GPU6 free memory insufficient')
health=subprocess.run(['nvidia-smi','-i','6','-q','-d','PERFORMANCE,POWER,TEMPERATURE'],text=True,capture_output=True,check=True,timeout=20).stdout
require('requires reset' not in health.lower(),'GPU6 requires reset')
capacity=cgroup_memory.check(ROOT);require(capacity['admitted'],'fresh cgroup admission failed')
sock=socket.socket()
try:require(sock.connect_ex(('127.0.0.1',8650))!=0,'port 8650 occupied')
finally:sock.close()
subprocess.run(['python3',str(ROOT/'producer/check_fresh_paths.py')],cwd=ROOT,check=True)
require(not(ROOT/'audit'/ATTEMPT).exists(),'attempt already exists')
fresh={'observed_unix':time.time(),'gpu_row':row,'gpu_health':health,'capacity':capacity,'own_experimental_video':own_video,'compute_rows':rows,'readonly_peer':peer,'predecessor_release':{'file':str(p),'sha256':sha(p)}}
service.write_json(ROOT/'audit/FRESH_START_CHECK.json',fresh)
review={'approved':True,'producer_seal_sha256':SEAL,'predecessor_release_verified':True,'predecessor_release_evidence':fresh['predecessor_release'],'fresh_gpu':row,'fresh_capacity':capacity,'boot_id':peer['boot_id'],'host41_max_own_video_processes':1,'readonly_peer':peer,'source_gpu5_release':'Exact processes exited; CUDA allocation remains unknown due to requires reset','authorization':'REDACTED_CREDENTIAL','unix':time.time()}
service.write_json(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json',review)
command=['python3','-u',str(ROOT/'audit/root_run_batch.py'),'--execute','--attempt',ATTEMPT]
with (ROOT/'logs/root_launch_attempt1.log').open('xb',buffering=0) as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
identity=service.bind_child(child,command)
receipt={'pid':child.pid,'identity':identity,'command':command,'attempt':ATTEMPT,'producer_seal_sha256':SEAL,'review_sha256':sha(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json'),'unix':time.time()}
service.write_json(ROOT/'audit/ATTEMPT1_LAUNCH.json',receipt)
print(json.dumps({'fresh_gpu':row,'capacity_admitted':capacity['admitted'],'launch':receipt}))

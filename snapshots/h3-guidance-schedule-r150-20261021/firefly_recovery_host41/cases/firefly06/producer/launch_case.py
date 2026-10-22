"""Root-authorized dance schedule launch after exact predecessor release."""
import argparse,hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service,cgroup_memory
parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.add_argument('--seal',required=True);parser.add_argument('--attempt',required=True);parser.add_argument('--predecessor-root',required=True);parser.add_argument('--predecessor-attempt',required=True);args=parser.parse_args()
SEAL=args.seal;ATTEMPT=args.attempt
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
require(ROOT==Path(service.RUNTIME['remote_root']),'actual target root required')
require(sha(ROOT/'deploy_manifest.json')==SEAL,'approved producer seal differs')
for rel,item in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(ROOT/rel)==item['sha256'],'sealed file changed: '+rel)
require(read(ROOT/'audit/TARGET_CPU_VALIDATION.json')['passed'],'CPU validation incomplete')
pr=Path(args.predecessor_root)
require(str(pr)=="/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/firefly06",'original Native root required')
p=pr/'processes/cleanup.json';release=read(p)
cp=pr/'audit'/args.predecessor_attempt/'FAILURE.json';complete=read(cp)
partial=read(ROOT/'producer/PREFIX_PARTIAL_RELEASE.json')
require(partial['passed'] and partial['native_visual_review_passed'] and partial['CUDA_allocation_absent'],'Native partial release incomplete')
require(release['process_absent'] and release['own_compute_absent'],'original Native service release incomplete')
for rel,item in partial['source_evidence'].items():require(sha(pr/rel)==item['sha256'],'original Native evidence changed: '+rel)
owner=read(pr/'processes/service.json');require(service.current_identity(owner['pid'])!=owner['identity'],'original Native service remains')
old_wrapper=read(pr/'audit/ATTEMPT1_LAUNCH.json');require(service.current_identity(old_wrapper['pid'])!=old_wrapper['identity'],'predecessor wrapper remains')
require(not any(x['pid']==owner['pid'] for x in service.compute_processes()),'predecessor CUDA allocation remains')
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
row=subprocess.run(['nvidia-smi','-i','0','--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True,timeout=15).stdout.strip()
parts=[x.strip() for x in row.split(',')]
require(parts[0]=='0' and parts[1]==service.GPU and int(parts[2])>=40960,'GPU0 free memory insufficient')
health=subprocess.run(['nvidia-smi','-i','0','-q','-d','PERFORMANCE,POWER,TEMPERATURE'],text=True,capture_output=True,check=True,timeout=20).stdout
require('requires reset' not in health.lower(),'GPU0 requires reset')
capacity=cgroup_memory.check(ROOT);require(capacity['admitted'],'fresh cgroup admission failed')
sock=socket.socket()
try:require(sock.connect_ex(('127.0.0.1',service.PORT))!=0,'selected port occupied')
finally:sock.close()
subprocess.run(['python3',str(ROOT/'producer/check_fresh_paths.py')],cwd=ROOT,check=True)
require(not(ROOT/'audit'/ATTEMPT).exists(),'attempt already exists')
fresh={'observed_unix':time.time(),'gpu_row':row,'gpu_health':health,'capacity':capacity,'own_experimental_video':own_video,'compute_rows':rows,'readonly_peer':peer,'predecessor_release':{'file':str(p),'sha256':sha(p),'complete_file':str(cp),'complete_sha256':sha(cp)}}
service.write_json(ROOT/'audit/FRESH_START_CHECK.json',fresh)
review={'approved':True,'producer_seal_sha256':SEAL,'predecessor_release_verified':True,'completed_native_partial_receipt_sha256':sha(ROOT/'producer/PREFIX_PARTIAL_RELEASE.json'),'predecessor_release_evidence':fresh['predecessor_release'],'fresh_gpu':row,'fresh_capacity':capacity,'boot_id':peer['boot_id'],'host41_max_own_video_processes':1,'readonly_peer':peer,'source_gpu6_release':'Exact processes exited; CUDA allocation remains unknown due to requires reset','authorization':'REDACTED_CREDENTIAL','unix':time.time()}
service.write_json(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json',review)
command=['python3','-u',str(ROOT/'audit/root_run_batch.py'),'--execute','--attempt',ATTEMPT]
with (ROOT/'logs/root_launch_attempt1.log').open('xb',buffering=0) as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
identity=service.bind_child(child,command)
receipt={'pid':child.pid,'identity':identity,'command':command,'attempt':ATTEMPT,'producer_seal_sha256':SEAL,'review_sha256':sha(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json'),'unix':time.time()}
service.write_json(ROOT/'audit/ATTEMPT1_LAUNCH.json',receipt)
print(json.dumps({'fresh_gpu':row,'capacity_admitted':capacity['admitted'],'launch':receipt}))

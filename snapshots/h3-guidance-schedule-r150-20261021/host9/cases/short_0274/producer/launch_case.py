"""Fresh, exact-owner admission for one authorized R150 schedule case."""
import argparse,hashlib,importlib.util,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,cgroup_memory
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.add_argument('--attempt',required=True);p.add_argument('--seal',required=True);p.add_argument('--predecessor-root');p.add_argument('--predecessor-attempt');a=p.parse_args()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
require(ROOT==Path(service.RUNTIME['remote_root']),'actual remote root required');require(sha(ROOT/'deploy_manifest.json')==a.seal,'seal differs')
for rel,v in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(ROOT/rel)==v['sha256'],'sealed file differs: '+rel)
require(read(ROOT/'audit/TARGET_CPU_VALIDATION.json')['passed'],'CPU gate missing')
spec=importlib.util.spec_from_file_location('root_batch',ROOT/'audit/root_run_batch.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
peer_paths=[f'/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/{x}' for x in ['short_0252','short_0358','05_real_megumi_v']]
peers=driver.live_peers(peer_paths);allowed={p['owner']['pid']:p for p in peers}
require(len(peers)<=1,'at most one R151 peer')
rows=service.compute_processes()
for x in rows:
 if service.proc_uid(x['pid'])==os.getuid():require(x['pid'] in allowed and x['gpu_uuid']==allowed[x['pid']]['owner']['gpu_uuid'],'unregistered own CUDA process')
video=[]
for d in Path('/proc').iterdir():
 if not d.name.isdecimal():continue
 pid=int(d.name)
 if service.proc_uid(pid)!=os.getuid():continue
 ident=service.current_identity(pid)
 if ident and ('/scripts/service_entry.py' in ident['cmdline'] or 'ComfyUI/main.py' in ident['cmdline']):
  require(pid in allowed and ident==allowed[pid]['owner']['identity'],'unregistered own video service');video.append(pid)
predecessor={'kind':'fresh_initial_host9_process_scan','own_video_pids':video,'all_own_CUDA_accounted_for':True}
if a.predecessor_root:
 require(a.predecessor_attempt,'predecessor attempt missing');pr=Path(a.predecessor_root);er=pr/'audit'/a.predecessor_attempt/'ROOT_EXIT_RECEIPT.json';cr=pr/'audit'/a.predecessor_attempt/'COMPLETE.json';exit=read(er);complete=read(cr)
 require(exit['passed'] and complete['passed'] and complete['GPU_released'],'predecessor incomplete')
 old=exit['owner'];require(service.current_identity(old['pid'])!=old['identity'],'predecessor exact generation alive')
 require(not any(x['pid']==old['pid'] for x in rows),'predecessor CUDA remains');predecessor={'root_exit_file':str(er),'root_exit_sha256':sha(er),'complete_file':str(cr),'complete_sha256':sha(cr)}
row=subprocess.run(['nvidia-smi','-i','2','--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15).stdout.strip();v=[x.strip() for x in row.split(',')]
require(v[0]=='2' and v[1]==service.GPU and int(v[2])>=40960,'GPU2 capacity insufficient')
health=subprocess.run(['nvidia-smi','-i','2','-q','-d','PERFORMANCE,POWER,TEMPERATURE'],capture_output=True,text=True,check=True,timeout=20).stdout;require('requires reset' not in health.lower(),'GPU requires reset')
capacity=cgroup_memory.check(ROOT);require(capacity['admitted'],'capacity admission failed')
s=socket.socket()
try:require(s.connect_ex(('127.0.0.1',service.PORT))!=0,'port occupied')
finally:s.close()
subprocess.run(['python3',str(ROOT/'producer/check_fresh_paths.py')],check=True,cwd=ROOT)
require(not (ROOT/'audit'/a.attempt).exists(),'attempt already exists')
review={'approved':True,'producer_seal_sha256':a.seal,'predecessor_release_verified':True,'predecessor_release_evidence':predecessor,'fresh_gpu':row,'fresh_health':health,'fresh_capacity':capacity,'existing_compute_rows':rows,'exact_R151_peers':peers,'host9_max_own_gpu_cards':2,'authorization':'REDACTED_CREDENTIAL','unix':time.time()}
service.write_json(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json',review)
command=['python3','-u',str(ROOT/'audit/root_run_batch.py'),'--execute','--attempt',a.attempt]
for x in peers:command+=['--peer-root',x['root']]
with (ROOT/'logs/root_launch_attempt1.log').open('xb',buffering=0) as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C'))
receipt={'pid':child.pid,'identity':service.bind_child(child,command),'command':command,'attempt':a.attempt,'producer_seal_sha256':a.seal,'review_sha256':sha(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json'),'unix':time.time()};service.write_json(ROOT/'audit/ATTEMPT1_LAUNCH.json',receipt)
print(json.dumps({'fresh_gpu':row,'capacity_admitted':capacity['admitted'],'peer_count':len(peers),'launch':receipt}))

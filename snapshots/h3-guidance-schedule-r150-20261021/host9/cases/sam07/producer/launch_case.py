"""Fresh, exact-owner admission for one authorized R150 schedule case."""
import argparse,hashlib,importlib.util,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,cgroup_memory
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.add_argument('--attempt',required=True);p.add_argument('--seal',required=True);p.add_argument('--predecessor-root');p.add_argument('--predecessor-attempt');p.add_argument('--mf-release-sha',required=True);a=p.parse_args()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
require(ROOT==Path(service.RUNTIME['remote_root']),'actual remote root required');require(sha(ROOT/'deploy_manifest.json')==a.seal,'seal differs')
for rel,v in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(ROOT/rel)==v['sha256'],'sealed file differs: '+rel)
require(read(ROOT/'audit/TARGET_CPU_VALIDATION.json')['passed'],'CPU gate missing')
spec=importlib.util.spec_from_file_location('root_batch',ROOT/'audit/root_run_batch.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
peer_paths=[f'/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/{x}' for x in ['short_0085','short_0274','musk05']]+['/home/researcher/h3_runs/guidance_schedule_r150_sam_tail_host9_20261021/cases/sam07']
peers=driver.live_peers(peer_paths);allowed={p['owner']['pid']:p for p in peers}
require(len(peers)<=1,'at most one R150 GPU2 peer')
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

mf_root=Path('/home/researcher/h3_runs/reference_feedback_mf_r151_20261021')
mf_file=mf_root/'audit/FINAL_RELEASE_VERIFIED.json'
require(sha(mf_file)==a.mf_release_sha,'R151 MF release SHA differs')
mf=read(mf_file)
for key in ['passed','all_spawned_trackers_released','exact_processes_absent','exact_CUDA_allocations_absent','peer_registrations_removed']:
 require(mf.get(key) is True,'R151 MF release incomplete: '+key)
require(mf.get('completed_generated_scores')==6,'R151 six MF results required')
require(read(mf_root/'configs/RUNTIME.json')['gpu_uuid']==service.GPU,'R151 MF GPU differs')
for bound in mf['child_release_receipts']+[mf['final_complete'],mf['seal']]:
 require(sha(Path(bound['file']))==bound['sha256'],'R151 release bound evidence differs')
for old in mf['wrapper_identities']+mf['tracker_identities']:
 actual=service.external_identity(old['pid'])
 require(actual is None or (actual['uid'],str(actual['start_ticks']),actual['cmdline_sha256'])!=(old['uid'],str(old['start_ticks']),old['cmdline_sha256']),'R151 MF exact process remains')
 require(not any(x['pid']==old['pid'] for x in rows),'R151 MF CUDA allocation remains')
predecessor={'root_release_file':str(mf_file),'root_release_sha256':sha(mf_file),'completed_generated_scores':6,'actual_release_verified':True}

row=subprocess.run(['nvidia-smi','-i','3','--query-gpu=index,uuid,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15).stdout.strip();v=[x.strip() for x in row.split(',')]
require(v[0]=='3' and v[1]==service.GPU and int(v[2])>=40960,'GPU3 capacity insufficient')
health=subprocess.run(['nvidia-smi','-i','3','-q','-d','PERFORMANCE,POWER,TEMPERATURE'],capture_output=True,text=True,check=True,timeout=20).stdout;require('requires reset' not in health.lower(),'GPU requires reset')
capacity=cgroup_memory.check(ROOT);require(capacity['admitted'],'capacity admission failed')
s=socket.socket()
try:require(s.connect_ex(('127.0.0.1',service.PORT))!=0,'port occupied')
finally:s.close()
subprocess.run(['python3',str(ROOT/'producer/check_fresh_paths.py')],check=True,cwd=ROOT)
require(not (ROOT/'audit'/a.attempt).exists(),'attempt already exists')
review={'approved':True,'producer_seal_sha256':a.seal,'predecessor_release_verified':True,'predecessor_release_evidence':predecessor,'fresh_gpu':row,'fresh_health':health,'fresh_capacity':capacity,'existing_compute_rows':rows,'exact_R150_peers':peers,'host9_max_own_gpu_cards':2,'authorization':'REDACTED_CREDENTIAL','unix':time.time()}
service.write_json(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json',review)
command=['python3','-u',str(ROOT/'audit/root_run_batch.py'),'--execute','--attempt',a.attempt]
for x in peers:command+=['--peer-root',x['root']]
with (ROOT/'logs/root_launch_attempt1.log').open('xb',buffering=0) as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C'))
receipt={'pid':child.pid,'identity':service.bind_child(child,command),'command':command,'attempt':a.attempt,'producer_seal_sha256':a.seal,'review_sha256':sha(ROOT/'audit/ROOT_PRELAUNCH_REVIEW.json'),'unix':time.time()};service.write_json(ROOT/'audit/ATTEMPT1_LAUNCH.json',receipt)
print(json.dumps({'fresh_gpu':row,'capacity_admitted':capacity['admitted'],'peer_count':len(peers),'launch':receipt}))

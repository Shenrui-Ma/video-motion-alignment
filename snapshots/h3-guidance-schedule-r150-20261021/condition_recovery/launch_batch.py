"""Run authorized one-load condition restoration after the preceding video release."""
from pathlib import Path
import hashlib,json,os,socket,subprocess,sys,time
ROOT=Path(__file__).resolve().parent
T=Path('/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/long_0059')
sys.path.insert(0,str(T/'scripts'));import service,cgroup_memory
assert sys.argv[1:]==['--execute']
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert service.GPU=='GPU-REDACTED'
pr=Path('/data4/researcher/h3_runs/guidance_schedule_r150_final_global_host41_20261021/cases/long_0039');ar=pr/'audit/root_r150_book_final_global_host41_attempt2'
release=read(ar/'ROOT_EXIT_RECEIPT.json');complete=read(ar/'COMPLETE.json');assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent'] and complete['GPU_released']
assert service.current_identity(release['owner']['pid']) is None
assert service.current_identity(read(pr/'audit/ATTEMPT1_LAUNCH.json')['pid']) is None
peer=read(T/'configs/readonly_peer.json');assert peer['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and service.external_identity(peer['pid'])==peer['identity']
rows=service.compute_processes()
for row in rows:
 if service.proc_uid(row['pid'])==os.getuid():assert row['pid']==peer['pid'] and row['gpu_uuid']==peer['gpu_uuid'] and service.external_identity(row['pid'])==peer['identity']
for proc in Path('/proc').iterdir():
 if proc.name.isdecimal() and service.proc_uid(int(proc.name))==os.getuid() and int(proc.name)!=peer['pid']:
  ident=service.current_identity(int(proc.name))
  assert not ident or '/scripts/service_entry.py' not in ident['cmdline']
raw=subprocess.check_output(['nvidia-smi','-i','0','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip();parts=[x.strip() for x in raw.split(',')];assert parts[1]==service.GPU and int(parts[2])>=40960
health=subprocess.check_output(['nvidia-smi','-i','0','-q','-d','PERFORMANCE,POWER,TEMPERATURE'],text=True);assert 'requires reset' not in health.lower()
capacity=cgroup_memory.check(T);assert capacity['admitted']
assert not(ROOT/'BATCH_RESULT.json').exists() and not(ROOT/'BATCH_PROCESS.json').exists()
for cid in ['musk05','firefly06','sam07']:
 p=ROOT/cid;cpu=read(p/'RECOVERY_CPU_CHECK.json');assert cpu['passed'] and not cpu['cuda_initialized'];assert cpu['config_sha256']==sha(p/'config.json') and cpu['worker_sha256']==sha(p/'encode_historical_condition.py')
 approval={'approved':True,'config_sha256':sha(p/'config.json'),'worker_sha256':sha(p/'encode_historical_condition.py'),'authorization':'REDACTED_CREDENTIAL','unix':time.time()};service.write_json(p/'ENCODE_APPROVAL.json',approval)
service.write_json(ROOT/'BATCH_APPROVAL.json',{'approved':True,'worker_sha256':sha(ROOT/'run_shared_encoder.py'),'fresh_gpu':raw,'health':health,'capacity':capacity,'readonly_peer':peer,'predecessor_release_sha256':sha(ar/'ROOT_EXIT_RECEIPT.json'),'one_load_three_encodes':True,'unix':time.time()})
cmd=[service.RUNTIME['python'],'-u',str(ROOT/'run_shared_encoder.py'),'--execute'];env=dict(os.environ,CUDA_VISIBLE_DEVICES=service.GPU,PYTHONDONTWRITEBYTECODE='1')
with (ROOT/'BATCH_LOG.txt').open('xb',buffering=0) as log:
 child=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True,env=env)
 ident=service.bind_child(child,cmd);service.write_json(ROOT/'BATCH_PROCESS.json',{'pid':child.pid,'identity':ident,'gpu_uuid':service.GPU,'command':cmd,'unix':time.time()});print(json.dumps({'started':True,'pid':child.pid,'identity':ident}),flush=True)
 code=child.wait()
checks={'exit_code':code,'process_absent':service.current_identity(child.pid)!=ident,'CUDA_allocation_absent':not any(x['pid']==child.pid for x in service.compute_processes()),'pid':child.pid,'identity':ident,'unix':time.time()}
checks['passed']=code==0 and checks['process_absent'] and checks['CUDA_allocation_absent'] and read(ROOT/'BATCH_RESULT.json')['passed'];service.write_json(ROOT/'BATCH_RELEASE.json',checks);print(json.dumps(checks),flush=True);assert checks['passed']

from pathlib import Path
import os,sys,json,time,socket,hashlib,subprocess
r=Path('/home/researcher/h3_runs/timing_ive_handkerchief_full_context_r126_20261020');sys.path.insert(0,str(r/'scripts'));import service
assert json.loads((r/'audit/TARGET_CPU_READY.json').read_text())['passed']
prior=[]
for name,a in [('timing_ive_full_context_r124_20261020','root_full_context_attempt1'),('timing_ive_board_edit_r125_20261020','root_board_edit_attempt1')]:
 p=r.parent/name/'audit'/a/'ROOT_EXIT_RECEIPT.json';v=json.loads(p.read_text());assert v['passed'] and v['process_absent'] and v['CUDA_allocation_absent'];assert service.current_identity(v['owner']['pid']) is None
 prior.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True)
rows=[x.split(', ') for x in raw.strip().splitlines()];gpu=next(x for x in rows if x[0]=='3');assert int(gpu[2])>=40960
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],text=True)
own=[]
for line in apps.strip().splitlines():
 pid=int(line.split(',')[0]);identity=service.current_identity(pid)
 if identity and identity['uid']==os.getuid():own.append({'pid':pid,'identity':identity,'line':line})
assert not own,own
s=socket.socket();assert s.connect_ex(('127.0.0.1',8598))!=0;s.close()
assert not (r/'processes/service.json').exists()
v={'passed':True,'prior_release':prior,'gpu':gpu,'own_compute':own,'port8598_empty':True,'unix':time.time(),'attempt':'root_handkerchief_full_context_attempt1'}
(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n')
env=dict(os.environ,PATH=str(Path(sys.executable).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:p=subprocess.Popen([sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt','root_handkerchief_full_context_attempt1'],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'wrapper_pid':p.pid,'dispatch':v}))

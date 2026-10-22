from pathlib import Path
import os,sys,json,time,socket,hashlib,subprocess
r=Path('/home/researcher/h3_runs/timing_ive_book_color_r128_20261020');sys.path.insert(0,str(r/'scripts'));import service
assert json.loads((r/'audit/TARGET_CPU_READY.json').read_text())['passed']
peer=r.parent/'timing_ive_handkerchief_full_context_r126_20261020';owner=json.loads((peer/'processes/service.json').read_text());assert owner['pid']==65253 and owner['identity']['start_ticks']=='2647176800';assert service.current_identity(owner['pid'])==owner['identity']
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True);rows=[x.split(', ') for x in raw.strip().splitlines()];gpu=next(x for x in rows if x[0]=='2');assert int(gpu[2])>=40960
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],text=True);own=[]
for line in apps.strip().splitlines():
 pid=int(line.split(',')[0]);identity=service.current_identity(pid)
 if identity and identity['uid']==os.getuid():own.append({'pid':pid,'identity':identity,'line':line})
assert {v['pid'] for v in own}<={owner['pid']},own
s=socket.socket();assert s.connect_ex(('127.0.0.1',8602))!=0;s.close();assert not (r/'processes/service.json').exists()
v={'passed':True,'peer':owner,'gpu':gpu,'own_compute':own,'port8602_empty':True,'unix':time.time(),'attempt':'root_book_color_attempt1'};(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n')
env=dict(os.environ,PATH=str(Path(sys.executable).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:p=subprocess.Popen([sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt','root_book_color_attempt1','--peer-root',str(peer)],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'wrapper_pid':p.pid,'gpu':gpu,'peer_pid':owner['pid'],'attempt':v['attempt']}))

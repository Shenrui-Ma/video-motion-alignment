from pathlib import Path
import json,hashlib,subprocess,os,sys,time,socket
r=Path('/home/researcher/h3_runs/timing_ive_hand_gesture_r139_20261020'); peer=r.parent/'timing_ive_position_edit_r137_20261020';sys.path.insert(0,str(r/'scripts'));import service
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(r/'deploy_manifest.json')=='5c663b12da5050ba81b5065efa01d9bb5d5c40f9c4ffa30a277434304e608252'
assert json.loads((r/'audit/TARGET_CPU_READY.json').read_text())['passed']
p=json.loads((peer/'processes/service.json').read_text());assert p['pid']==36340 and p['identity']['start_ticks']=='2648773174';assert service.current_identity(p['pid'])==p['identity']
gpu=subprocess.check_output(['nvidia-smi','-i','3','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip();uuid,free=[v.strip() for v in gpu.split(',')];assert uuid==service.GPU and int(free)>=40960
rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).strip().splitlines();own=[]
for line in rows:
 u,pid,mem=[v.strip() for v in line.split(',')];identity=service.current_identity(int(pid))
 if identity and identity['uid']==os.getuid():own.append({'gpu_uuid':u,'pid':int(pid),'identity':identity})
assert {v['pid'] for v in own}=={36340},own
s=socket.socket();assert s.connect_ex(('127.0.0.1',8618))!=0;s.close()
releases=[]
for rel,expected in [('timing_ive_otter_color_r136_20261020/audit/root_otter_color_attempt1/ROOT_EXIT_RECEIPT.json','a94eaa88fada971d8cd85c2d49d89b86bb30c1d54b4df2cc6d701e9750b2c335'),('ive_otter_mf_r136_20261020/audit/FINAL_RELEASE_VERIFIED.json','3ab293cfb13df8aadcf5381cdd0ba30a86268a3e2efa0b47505e585e6204b525')]:
 f=r.parent/rel;assert h(f)==expected;releases.append({'file':str(f),'sha256':expected})
a='root_hand_gesture_attempt1';assert not (r/'audit'/a).exists()
v={'unix':time.time(),'gpu':gpu,'own_compute':own,'peer':p,'prior_release':releases,'port':8618,'port_empty':True,'attempt':a};(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n')
env=dict(os.environ,PATH='/home/researcher/miniconda3/envs/comfyui/bin:'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:
 proc=subprocess.Popen([sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt',a,'--peer-root',str(peer)],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'wrapper_pid':proc.pid,'attempt':a,'gpu_free_mib':int(free),'peer_pid':36340}))

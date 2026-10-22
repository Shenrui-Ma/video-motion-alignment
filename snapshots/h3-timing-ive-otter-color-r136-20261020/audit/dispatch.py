from pathlib import Path
import json,hashlib,subprocess,os,sys,time,socket
r=Path('/home/researcher/h3_runs/timing_ive_otter_color_r136_20261020'); peer=r.parent/'timing_ive_subject_replacement_r135_20261020';sys.path.insert(0,str(r/'scripts'));import service
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(r/'deploy_manifest.json')=='813e6493cc423e43aa19292481680a01dd0d4d2fd835ceb0390a7d33313101b6'
assert json.loads((r/'audit/TARGET_CPU_READY.json').read_text())['passed']
p=json.loads((peer/'processes/service.json').read_text());assert p['pid']==21602 and p['identity']['start_ticks']=='2648509732';assert service.current_identity(p['pid'])==p['identity']
gpu=subprocess.check_output(['nvidia-smi','-i','3','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip();uuid,free=[v.strip() for v in gpu.split(',')];assert uuid==service.GPU and int(free)>=40960
rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).strip().splitlines();own=[]
for line in rows:
 u,pid,mem=[v.strip() for v in line.split(',')];identity=service.current_identity(int(pid))
 if identity and identity['uid']==os.getuid():own.append({'gpu_uuid':u,'pid':int(pid),'identity':identity})
assert {v['pid'] for v in own}=={21602},own
s=socket.socket();assert s.connect_ex(('127.0.0.1',8614))!=0;s.close()
releases=[]
for rel,expected in [('timing_ive_caption_ablation_r130_20261020/audit/root_caption_ablation_attempt1/ROOT_EXIT_RECEIPT.json','31ec52f39073e7651dfae6d0c47638babb0a61bc242f5535d81fee0a9cc69e2f'),('ive_caption_scrubs_mf_host9_20261020/audit/FINAL_RELEASE_VERIFIED.json','6898f3855df0bc9956cb36904f1ced534bba0d4a084ff189f3a825cfddecfd67')]:
 f=r.parent/rel;assert h(f)==expected;releases.append({'file':str(f),'sha256':expected})
a='root_otter_color_attempt1';assert not (r/'audit'/a).exists()
v={'unix':time.time(),'gpu':gpu,'own_compute':own,'peer':p,'prior_release':releases,'port':8614,'port_empty':True,'attempt':a};(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n')
env=dict(os.environ,PATH='/home/researcher/miniconda3/envs/comfyui/bin:'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:
 proc=subprocess.Popen([sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt',a,'--peer-root',str(peer)],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'wrapper_pid':proc.pid,'attempt':a,'gpu_free_mib':int(free),'peer_pid':21602}))

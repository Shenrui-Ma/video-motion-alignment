from pathlib import Path
import json,hashlib,subprocess,os,sys,time,socket
r=Path('/home/researcher/h3_runs/timing_ive_position_edit_r137_20261020'); peer=r.parent/'timing_ive_otter_color_r136_20261020';sys.path.insert(0,str(r/'scripts'));import service
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert h(r/'deploy_manifest.json')=='ea359c1310acd03034a79a0a5c37b822def8b28b56639d0458f465092f08f524'
assert json.loads((r/'audit/TARGET_CPU_READY.json').read_text())['passed']
p=json.loads((peer/'processes/service.json').read_text());assert p['pid']==2969 and p['identity']['start_ticks']=='2648616990';assert service.current_identity(p['pid'])==p['identity']
gpu=subprocess.check_output(['nvidia-smi','-i','2','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip();uuid,free=[v.strip() for v in gpu.split(',')];assert uuid==service.GPU and int(free)>=40960
rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).strip().splitlines();own=[]
for line in rows:
 u,pid,mem=[v.strip() for v in line.split(',')];identity=service.current_identity(int(pid))
 if identity and identity['uid']==os.getuid():own.append({'gpu_uuid':u,'pid':int(pid),'identity':identity})
assert {v['pid'] for v in own}=={2969},own
s=socket.socket();assert s.connect_ex(('127.0.0.1',8616))!=0;s.close()
releases=[]
for rel,expected in [('timing_ive_subject_replacement_r135_20261020/audit/root_subject_replacement_attempt1/ROOT_EXIT_RECEIPT.json','7a2a51aa23afe9b9cdd56ede7c4acc30bd7da24c9129e1b26e03fed29febc22c'),('ive_subject_mf_r135_20261020/audit/FINAL_RELEASE_VERIFIED.json','b6c29476287785f557a222a4eda9322f8805881b7eff606c8401d7067da5752e')]:
 f=r.parent/rel;assert h(f)==expected;releases.append({'file':str(f),'sha256':expected})
a='root_position_edit_attempt1';assert not (r/'audit'/a).exists()
v={'unix':time.time(),'gpu':gpu,'own_compute':own,'peer':p,'prior_release':releases,'port':8616,'port_empty':True,'attempt':a};(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n')
env=dict(os.environ,PATH='/home/researcher/miniconda3/envs/comfyui/bin:'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:
 proc=subprocess.Popen([sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt',a,'--peer-root',str(peer)],cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'wrapper_pid':proc.pid,'attempt':a,'gpu_free_mib':int(free),'peer_pid':2969}))

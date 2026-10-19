import json,os,pathlib,hashlib,subprocess
root=pathlib.Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017/analysis/last_step_recovery/final_same_host')
manifest=root/'MANIFEST.json';assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='2aea51bccc778e169e4d339af1d8be947dd3314a8448273c7bb76d64db218b9b'
for name,row in json.loads(manifest.read_text())['files'].items():
 p=root/name;assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],name
gpu='GPU-REDACTED'
raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
for line in raw.splitlines():
 if not line.strip():continue
 uuid,pid=line.split(',');pid=int(pid);p=pathlib.Path('/proc')/str(pid);assert not p.exists() or p.stat().st_uid!=os.getuid(),'own GPU peer requires explicit accounting'
mem=subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True);assert int(mem.strip())*1024**2>=8172601344,'insufficient measured full141 headroom'
admission=root/'ROOT_ADMISSION.json'
with admission.open('x') as f:json.dump({'root_approved':True,'gpu_uuid':gpu,'permitted_peers':[],'required_free_bytes':8172601344},f)
log=root/'root_final_host9_v1.log'
with log.open('xb') as f:
 proc=subprocess.Popen(['/home/researcher/miniconda3/envs/comfyui/bin/python',str(root/'launch_final.py'),'--run-name','final_host9_v1','--admission',str(admission),'--root-admitted'],cwd=root,stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)
print(json.dumps({'supervisor_pid':proc.pid,'log':str(log)}))

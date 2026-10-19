import json,os,pathlib,hashlib,subprocess
root=pathlib.Path('/data3/researcher/h3_runs/timing_signed_source6980766_r53_recovery_20261017/final_slice')
manifest=root/'MANIFEST.json';assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='31e32d654cad2ed94e9de74a3cb0f62af242ce2692abe26876b698e01af5ff5d'
for name,row in json.loads(manifest.read_text())['files'].items():
 p=root/name;assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],name
gpu='GPU-REDACTED'
raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
for line in raw.splitlines():
 if not line.strip():continue
 uuid,pid=line.split(',');pid=int(pid);assert uuid.strip()!=gpu,'selected GPU occupied';p=pathlib.Path('/proc')/str(pid);assert not p.exists() or p.stat().st_uid!=os.getuid(),'own GPU peer requires explicit accounting'
admission=root/'ROOT_ADMISSION.json'
with admission.open('x') as f:json.dump({'root_approved':True,'gpu_uuid':gpu,'permitted_peers':[]},f)
log=root/'root_final_host41_v1.log'
with log.open('xb') as f:
 proc=subprocess.Popen(['/data3/researcher/ComfyUI/.venv/bin/python',str(root/'launch_final.py'),'--run-name','final_host41_v1','--admission',str(admission),'--root-admitted'],cwd=root,stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)
print(json.dumps({'supervisor_pid':proc.pid,'log':str(log)}))

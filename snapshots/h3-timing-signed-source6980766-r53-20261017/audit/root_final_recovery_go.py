import json,os,pathlib,hashlib,subprocess
root=pathlib.Path('/data3/researcher/h3_runs/timing_signed_source6980766_r53_recovery_20261017/final_slice');out=root/'runs/final_host41_v1'
r=json.loads((out/'ready.json').read_text());assert r['CUDA_initialized'] is False
expected='31e32d654cad2ed94e9de74a3cb0f62af242ce2692abe26876b698e01af5ff5d'
assert r['manifest_sha256']==expected==hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()
assert r['admission_sha256']==hashlib.sha256((root/'ROOT_ADMISSION.json').read_bytes()).hexdigest()
identity=r['identity'];p=pathlib.Path('/proc')/str(identity['pid']);cur={'pid':identity['pid'],'uid':p.stat().st_uid,'start_ticks':int((p/'stat').read_text().split(') ')[1].split()[19]),'cmdline_sha256':hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()};assert cur==identity and cur['uid']==os.getuid()
assert r['gpu_uuid']=='GPU-REDACTED'
raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
for line in raw.splitlines():
 if not line.strip():continue
 uuid,pid=line.split(',');pid=int(pid);assert uuid.strip()!=r['gpu_uuid'];q=pathlib.Path('/proc')/str(pid);assert not q.exists() or q.stat().st_uid!=os.getuid()
go={k:r[k] for k in ['identity','gpu_uuid','admission_sha256','manifest_sha256']};go['root_approved']=True
with (out/'go.json').open('x') as f:json.dump(go,f)
print(json.dumps({'approved_identity':identity,'manifest_sha256':expected}))

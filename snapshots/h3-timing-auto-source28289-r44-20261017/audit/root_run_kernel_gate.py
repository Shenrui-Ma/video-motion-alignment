from pathlib import Path
import os,json,hashlib,subprocess,time,signal
r=Path('/data5/researcher/h3_runs/timing_auto_source28289_r44_20261017')
gpu='GPU-REDACTED';peer=37646
peer_start='2624194169';peer_cmd='05667e23441d611739d29d67bdb900096945db12d67416812f6671ef9a4d3b05'
def ident(pid):
 p=Path('/proc')/str(pid);s=(p/'stat').read_text()
 return dict(pid=pid,uid=p.stat().st_uid,start_ticks=s.rsplit(')',1)[1].split()[19],cmdline_sha256=hashlib.sha256((p/'cmdline').read_bytes()).hexdigest())
def compute():
 out=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits'],text=True,timeout=15)
 rows=[]
 for ln in out.splitlines():
  a=ln.split(',');pid=int(a[0]);row=dict(pid=pid,gpu_uuid=a[1].strip(),used_mib=a[2].strip());row.update(ident(pid));rows.append(row)
 return rows
assert ident(peer)==dict(pid=peer,uid=1016,start_ticks=peer_start,cmdline_sha256=peer_cmd)
rows=compute();own=[x for x in rows if x['uid']==1016]
assert len(own)==1 and own[0]['pid']==peer and own[0]['gpu_uuid']=='GPU-REDACTED'
assert not [x for x in rows if x['gpu_uuid']==gpu]
assert not (r/'audit/gpu_dynamic_union_gate.json').exists()
manifest=json.loads((r/'deploy_manifest.json').read_text())
for name,e in manifest['files'].items():
 b=(r/name).read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],name
stamp=str(time.time_ns());log=r/('audit/root_kernel_attempt_'+stamp+'.log');rec=r/('audit/root_kernel_attempt_'+stamp+'.json')
env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps')
cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python','-u',str(r/'scripts/gpu_dynamic_union_smoke.py'),'--root-admitted','--output',str(r/'audit/gpu_dynamic_union_gate.json')]
record=dict(unix=time.time(),pre_compute=rows,command=cmd,log=str(log),scope='0NFE model-free actual87366 numerical check')
with log.open('x') as f:
 p=subprocess.Popen(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 time.sleep(.05);owner=ident(p.pid);record['owner']=owner;rec.write_text(json.dumps(record,indent=2)+'\n')
 try:code=p.wait(timeout=240)
 except subprocess.TimeoutExpired:
  assert ident(p.pid)==owner;p.terminate()
  try:code=p.wait(timeout=15)
  except subprocess.TimeoutExpired:
   assert ident(p.pid)==owner;p.kill();code=p.wait(timeout=15)
  record['timed_out']=True
record['returncode']=code;record['end_unix']=time.time();record['process_absent']=not (Path('/proc')/str(p.pid)).exists();record['post_compute']=compute();record['target_compute_absent']=not [x for x in record['post_compute'] if x['gpu_uuid']==gpu]
g=r/'audit/gpu_dynamic_union_gate.json'
if g.exists():
 record['gate_sha256']=hashlib.sha256(g.read_bytes()).hexdigest();record['gate_passed']=json.loads(g.read_text())['passed']
rec.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record.get(k) for k in ['returncode','timed_out','process_absent','target_compute_absent','gate_passed','gate_sha256']}),flush=True)
assert code==0 and record['process_absent'] and record['target_compute_absent'] and record['gate_passed']

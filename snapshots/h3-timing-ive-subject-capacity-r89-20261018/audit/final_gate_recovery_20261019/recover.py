from pathlib import Path
import json,hashlib,subprocess,os,time
R=Path('/data5/researcher/h3_runs/timing_ive_subject_capacity_r89_20261018');A=R/'audit/final_gate_recovery_20261019';A.mkdir(exist_ok=True)
Q=Path('/data5/researcher/h3_runs/timing_ive_glasses_schedule_r97_20261018');expected={'pid':36315,'start_ticks':'2635074861'}
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(n,d):p=A/n;assert not p.exists(),n;p.write_text(json.dumps(d,indent=2)+'\n')
def proc(pid):
 p=Path('/proc')/str(pid)
 if not p.exists():return None
 stat=(p/'stat').read_text().rsplit(')',1)[1].split();return {'start_ticks':stat[19],'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(),'uid':p.stat().st_uid}
def gpu():
 out=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,timeout=30)
 return [x.strip() for x in out.splitlines() if x.strip()]
assert os.getuid()==1016
owner=read(R/'processes/service.json');assert owner['pid']==expected['pid'] and owner['identity']['start_ticks']==expected['start_ticks']
assert proc(expected['pid']) is None,'old PID still exists';alloc=gpu();assert not any(x.split(',')[0].strip()==str(expected['pid']) for x in alloc),'old CUDA allocation remains'
dest=R/'analysis/postrun/short_0178/PAIR_RUNTIME_GATE.json';err=dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json');assert not dest.exists() and not err.exists(),'existing gate requires review'
seal=read(R/'deploy_manifest.json');assert all(sha(R/p)==v['sha256'] for p,v in seal['files'].items()),'sealed source changed'
s=read(R/'configs/scientific_contract.json');jobs=s['case_order'];assert len(jobs)==14
records={}
for run in jobs:
 j=R/'logs'/(run+'_job.json');h=R/'logs'/(run+'_history.json');a=read(j);b=read(h);assert a['status']=='success' and b['status']['completed'] is True and b['status']['status_str']=='success';records[run]={'job_sha256':sha(j),'history_sha256':sha(h)}
r97path=Q/'processes/service.json';r97=read(r97path) if r97path.exists() else None;r97sha=sha(r97path) if r97 else None;r97proc=proc(r97['pid']) if r97 else None
if r97:
 assert r97['pid']!=expected['pid'] and r97proc is not None and r97proc['start_ticks']==r97['identity']['start_ticks'],'R97 actual generation mismatch'
pre={'passed':True,'old_owner':owner,'old_PID_absent':True,'old_CUDA_absent':True,'nvidia_compute':alloc,'producer_seal_sha256':sha(R/'deploy_manifest.json'),'all14_success':records,'old_wrapper_failure':read(R/'audit/root_first_capacity_trial/FAILURE.json'),'old_wrapper_failure_sha256':sha(R/'audit/root_first_capacity_trial/FAILURE.json'),'r97_owner':r97,'r97_owner_file_sha256':r97sha,'r97_actual_identity':r97proc,'unix':time.time()};write('PRECONDITIONS.json',pre)
runtime=read(R/'configs/runtime.json');argv=[runtime['python'],'analysis/postrun/verify_pair.py','--source','short_0178'];env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=runtime['dependencies'],LC_ALL='C',LANG='C');start=time.monotonic()
try:
 with (A/'verifier.log').open('xb') as log:result=subprocess.run(argv,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 gate=read(dest) if dest.exists() else None
 assert result.returncode==0 and gate and gate['passed'] is True,'final verifier did not pass'
 assert not err.exists()
 assert proc(expected['pid']) is None
 assert r97 is None or sha(r97path)==r97sha,'R97 service record changed during CPU-only recovery'
 write('COMPLETE.json',{'passed':True,'argv':argv,'CUDA_VISIBLE_DEVICES':'','threads':1,'timeout_seconds':600,'wall_seconds':time.monotonic()-start,'gate_sha256':sha(dest),'gate_schema':gate['schema'],'source_id':'short_0178','gate_passed':True,'r97_owner_file_unchanged':True,'r97_current_identity':proc(r97['pid']) if r97 else None,'signals_sent':[],'GPU_started':False,'old_failure_preserved':sha(R/'audit/root_first_capacity_trial/FAILURE.json')==pre['old_wrapper_failure_sha256'],'unix':time.time()});print(json.dumps(read(A/'COMPLETE.json')))
except BaseException as e:
 write('RECOVERY_FAILURE.json',{'error':repr(e),'argv':argv,'seconds':time.monotonic()-start,'unix':time.time()});raise

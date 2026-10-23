"""Run the released native→weak pair once, advancing only after complete provenance gates."""
from pathlib import Path
import fcntl,json,os,time,sys,hashlib,urllib.request,subprocess,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import manage_service as service
from trajectory_gate import bind,sha
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def atomic(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def api(path,data=None):
 req=urllib.request.Request(f'http://127.0.0.1:{service.PORT}/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with OPENER.open(req,timeout=30) as r:return json.load(r)
def check_assets(release):
 for p,h in release['assets'].items():assert sha(ROOT/p)==h,p
 assert sha(ROOT/'SCIENCE_READY.json')==release['science_ready_sha256']
 assert sha(ROOT/'INDEPENDENT_SIGNOFF.json')==release['signoff_sha256']
def wait_budget(method):
 policy=json.loads((ROOT/'shared_gpu_authorization.json').read_text())
 while True:
  rows=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=20)
  free=next(float(s.split(',')[1]) for s in rows.splitlines() if s.split(',')[0].strip()==policy['gpu_uuid'])
  if free>=policy['minimum_free_mib']:return
  atomic(ROOT/'STATUS.json',{'phase':'waiting_budget','method':method,'free_mib':free,'required_mib':policy['minimum_free_mib'],'time':time.time()});time.sleep(60)
def queue_record(job_id,**fields):
 p=ROOT/'queue_state/state.json';d=json.loads(p.read_text()) if p.exists() else {'jobs':{}};d['jobs'].setdefault(job_id,{}).update(fields);atomic(p,d)
def run(method,release):
 d=ROOT/'jobs'/method;d.mkdir(parents=True,exist_ok=True)
 job=next(j for j in json.loads((ROOT/'jobs.json').read_text())['jobs'] if j['metadata']['method']==method);job_id=job['id']
 assert not (d/'SUBMISSION_INTENT.json').exists(),'single attempt already exists; inspect exact API identity'
 assert not service.alive(service.read_record()),'existing model service requires identity reconciliation'
 wait_budget(method);check_assets(release);record=None;status={'phase':'starting','method':method,'time':time.time()};atomic(ROOT/'STATUS.json',status)
 try:
  service.start();record=service.read_record();assert service.alive(record)
  q=api('queue');assert not q.get('queue_running') and not q.get('queue_pending')
  graph=json.loads((ROOT/'graphs'/(method+'_graph.json')).read_text());info=api('object_info')
  for node in graph.values():assert node['class_type'] in info,node['class_type']
  atomic(d/'API_SCHEMA_VERIFIED.json',{'time':time.time(),'node_types':[n['class_type'] for n in graph.values()]})
  atomic(d/'SUBMISSION_INTENT.json',{'time':time.time(),'method':method,'graph_sha256':sha(ROOT/'graphs'/(method+'_graph.json')),'maximum_attempts':1})
  res=api('prompt',{'prompt':graph,'client_id':'h3-live-phase-pair-'+method});assert res.get('prompt_id') and not res.get('node_errors'),res
  pid=res['prompt_id'];atomic(d/'SUBMITTED.json',dict(res,time=time.time(),service=record));queue_record(job_id,status='submitted',attempt_id=job_id,prompt_id=pid,metadata=job['metadata']);status.update(phase='running',prompt_id=pid,service=record);atomic(ROOT/'STATUS.json',status)
  deadline=time.monotonic()+7200
  while time.monotonic()<deadline:
   assert service.alive(record),'model service exited during live trajectory'
   h=api('history/'+pid)
   if pid in h:
    h=h[pid];atomic(d/'HISTORY.json',h)
    if h.get('status',{}).get('completed'):
     assert h['status']['status_str']=='success',h['status']
     gate=bind(ROOT,method,h,release['assets']);gate['history_sha256']=sha(d/'HISTORY.json');gate['science_ready_sha256']=release['science_ready_sha256'];gate['signoff_sha256']=release['signoff_sha256'];gate['finished']=time.time()
     peaks=[]
     for p in (ROOT/'audit/memory').glob('*.json'):
      m=json.loads(p.read_text())
      if str(record['pid']) in p.stem:peaks.append({'path':str(p),'sha256':sha(p),'data':m})
     assert peaks,'own memory peak audit missing'
     gate['memory_peak_records']=peaks;atomic(d/'TRAJECTORY_GATE.json',gate)
     result={'job_id':job_id,'attempt_id':job_id,'status':'completed','metadata':job['metadata'],'files':[{'path':gate['actual_video_file'],'sha256':gate['actual_video_sha256'],'bytes':gate['actual_video_bytes']}],'timing':{'sampling_seconds':gate['sampling_seconds'],'mean_sampling_step_seconds':gate['mean_sampling_step_seconds'],'measurement_basis':'actual sampler wrapper including passive copies/writes; no extra model forwards'},'trajectory_gate':str(d/'TRAJECTORY_GATE.json'),'trajectory_gate_sha256':sha(d/'TRAJECTORY_GATE.json')}
     atomic(ROOT/'queue_state/results'/(job_id+'.json'),result);queue_record(job_id,status='completed',result=result)
     status.update(phase='trajectory_verified',gate=str(d/'TRAJECTORY_GATE.json'),finished=time.time());atomic(ROOT/'STATUS.json',status);return
    if h.get('status',{}).get('status_str')=='error':raise RuntimeError('Comfy trajectory failed; see exact HISTORY.json')
   status.update(last_checked=time.time());atomic(ROOT/'STATUS.json',status);time.sleep(15)
  raise TimeoutError('bounded two-hour trajectory deadline exceeded')
 except BaseException as e:
  queue_record(job_id,status='failed',error=type(e).__name__+': '+str(e));status.update(phase='failed',error=type(e).__name__+': '+str(e),finished=time.time());atomic(ROOT/'STATUS.json',status);traceback.print_exc();raise
 finally:
  if record is None:record=service.read_record()
  result=service.stop(record);atomic(d/'SERVICE_CLEANUP.json',dict(result,time=time.time()));assert result['stopped'],'own service still alive; next trajectory prohibited'
def main():
 with (ROOT/'live_pair.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  release=json.loads((ROOT/'LAUNCH_RELEASE.json').read_text());assert release['scope']=='only_live0358_native_and_global_weak';check_assets(release)
  for method in ['native','global_weak']:
   run(method,release)
  atomic(ROOT/'STATUS.json',{'phase':'complete','cohort':'phase_calibration_pair','time':time.time(),'methods':['native','global_weak']})
if __name__=='__main__':main()

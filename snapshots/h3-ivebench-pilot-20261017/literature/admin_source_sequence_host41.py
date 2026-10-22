"""Root-delegated admission for the four frozen remaining SOURCE cases only."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time

ROOT=Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017')
FREEZE='d46b5c807c56aeb39e219e71271c7e5f050873ee74c5fe342988a3c1cb63dd45'
MANIFEST=Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017/analysis/postrun/SOURCE_METRIC_MANIFEST.json')
MANIFEST_SHA='169056e0fb4616e076f7a6c7b35d57d115eed3541971d00d0213e2a6bac0b472'
GPU='GPU-REDACTED'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
CASES=['short_0230','short_0263','short_0352','short_0370']
CHILDREN={}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def identity(pid):
 p=Path('/proc')/str(pid)
 return {'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':sha(p/'cmdline')}

def verify_freeze():
 p=ROOT/'RUNTIME_FREEZE_HOST41.json';assert sha(p)==FREEZE
 d=read(p)
 assert sha(MANIFEST)==MANIFEST_SHA
 assert all(sha(ROOT/x['file'])==x['sha256'] for x in d['files'])
 assert sha(ROOT/d['checkpoint']['file'])==d['checkpoint']['sha256']
 sys.path.insert(0,str(ROOT/'metric_runtime'))
 from ive_mf_adapter import verify_vendor
 verify_vendor()

def launch_or_load(pair):
 key='source_'+pair.replace('_','')+'_attempt1';control=ROOT/'gates'/key
 arguments=['--input-manifest',str(MANIFEST),'--selection',str(ROOT/'PILOT_5_MANIFEST.json'),'--pair',pair,'--method','source','--gpu-uuid',GPU,'--output',str(ROOT/'tracks/source'/pair)]
 if not control.exists():
  log=ROOT/'processes'/(key+'.log');assert not log.exists()
  command=[PYTHON,str(ROOT/'metric_runtime/launch_tracking_gate.py'),'--control',str(control),'--']+arguments
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=GPU,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TMPDIR=str(ROOT/'temp'),TMP=str(ROOT/'temp'),TEMP=str(ROOT/'temp'))
  with log.open('w') as handle:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT,env=env,start_new_session=True)
  CHILDREN[child.pid]=child
 deadline=time.monotonic()+5
 while not (control/'ready.json').exists() and time.monotonic()<deadline:time.sleep(.05)
 ready=read(control/'ready.json');assert ready['arguments']==arguments and ready['gpu_uuid']==GPU and ready['CUDA_started'] is False
 assert identity(ready['pid'])==ready['identity'] and ready['identity']['uid']==1004
 assert all(sha(x['file'])==x['sha256'] for x in ready['bindings'])
 return control,ready

def main():
 authority={'origin':'root collaboration delegation recorded by child','scope':'remaining four SOURCE-only cases, sequential, same sealed runtime and GPU2; generated runs and new GPUs require root review','cases':CASES,'runtime_freeze_sha256':FREEZE,'source_manifest_sha256':MANIFEST_SHA,'gpu_uuid':GPU,'previous_short0210_pid':27375,'previous_short0210_passed':True}
 auth=ROOT/'ROOT_SOURCE_SEQUENCE_AUTHORIZATION.json'
 if auth.exists():assert read(auth)==authority
 else:write(auth,authority)
 assert not Path('/proc/27375').exists()
 rows=[]
 for pair in CASES:
  report_path=ROOT/'tracks/source'/pair/'REPORT.json'
  if report_path.exists():
   report=read(report_path);assert report['passed'] and report['pair_id']==pair and report['method']=='source' and report['input_manifest']['sha256']==MANIFEST_SHA
   assert not (Path('/proc')/str(report['pid'])).exists()
   assert sha(report_path.parent/'tracks.npz')==report['tracks_sha256']
   row={k:report[k] for k in ['pair_id','pid','tracking_seconds','wall_seconds','peak_allocated_bytes','peak_reserved_bytes','tracks_sha256','tracks_shape']};row.update(process_absent=True,report_sha256=sha(report_path),already_completed_before_resume=True);rows.append(row)
   print(json.dumps({'event':'verified_prior_completion',**row}),flush=True);continue
  verify_freeze();control,ready=launch_or_load(pair)
  from run_tracks import check_gpu
  os.environ['CUDA_VISIBLE_DEVICES']=GPU
  admission=check_gpu(GPU)
  write(control/'delegated_admission.json',{'authorization_file':str(auth),'authorization_sha256':sha(auth),'ready_sha256':sha(control/'ready.json'),'ready_identity_verified':True,'runtime_freeze_sha256':FREEZE,'resource_check':admission})
  go=control/'go.json'
  if go.exists():assert read(go)==ready
  else:
   tmp=control/'go.tmp';write(tmp,ready);tmp.replace(go)
  print(json.dumps({'event':'admitted','pair':pair,'pid':ready['pid']}),flush=True)
  deadline=time.monotonic()+180
  while time.monotonic()<deadline:
   if ready['pid'] in CHILDREN:CHILDREN[ready['pid']].poll()
   if report_path.exists() and not (Path('/proc')/str(ready['pid'])).exists():break
   time.sleep(.25)
  assert not (Path('/proc')/str(ready['pid'])).exists(),'tracking process still active after180 seconds'
  report=read(report_path);assert report['passed'] and report['pair_id']==pair and report['method']=='source' and report['pid']==ready['pid'] and report['input_manifest']['sha256']==MANIFEST_SHA
  assert sha(report_path.parent/'tracks.npz')==report['tracks_sha256']
  released=check_gpu(GPU)
  row={k:report[k] for k in ['pair_id','pid','tracking_seconds','wall_seconds','peak_allocated_bytes','peak_reserved_bytes','tracks_sha256','tracks_shape']};row.update(process_absent=True,selected_memory_MiB_after_exit=released['selected_memory_MiB'],report_sha256=sha(report_path));rows.append(row)
  write(ROOT/'SOURCE_SEQUENCE_RECEIPTS.json',{'complete':len(rows)==4,'receipts':rows});print(json.dumps({'event':'completed',**row}),flush=True)

if __name__=='__main__':main()
